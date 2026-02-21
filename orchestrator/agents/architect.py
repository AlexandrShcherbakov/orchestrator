from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any
import yaml
from orchestrator.llm import LLM
from orchestrator.task_logging import TaskLog

@dataclass(frozen=True)
class BootstrapResult:
  updated_files: list[str]
  problems: list[str]

@dataclass(frozen=True)
class ArchitectContext:
  """Контекст для работы архитектора с расширенной документацией."""
  docs_content: Dict[str, str]  # Имя файла -> содержимое
  repo_path: str
  total_docs: int

def create_architect_context(docs_content: Dict[str, str], repo: Path) -> ArchitectContext:
  """Создает контекст архитектора с собранной документацией."""
  return ArchitectContext(
    docs_content=docs_content,
    repo_path=str(repo),
    total_docs=len(docs_content)
  )

@dataclass(frozen=True)
class ArchitectResult:
  """Результат работы архитектора с полным контекстом."""
  proposal_yaml: str
  questions: list[str]
  answers: list[str]
  round_count: int

SYSTEM = """You are ArchitectBootstrap.
Rules:
- Be concise.
- Output MUST be valid YAML (no markdown, no code fences, no ```).
- You can only propose changes under docs/.
- Create actionable tasks for docs/tasks/backlog.yaml.
- If you need clarification, use 'questions' key with list of specific questions.
- If you can make concrete proposal, use 'proposed_changes' and 'tasks' keys.
"""

def ask_user_questions(questions: list[str]) -> list[str]:
  """Задает вопросы пользователю и собирает ответы."""
  answers = []

  print("\n" + "=" * 50)
  print("ARCHITECT HAS QUESTIONS FOR YOU")
  print("=" * 50)

  for i, question in enumerate(questions, 1):
    print(f"\nQ{i}: {question}")
    answer = input("A: ").strip()
    answers.append(answer)

  return answers

def run_architect_with_context(architect_context: ArchitectContext, user_input: Dict[str, str], llm: LLM, log: TaskLog) -> ArchitectResult:
  """Запускает архитектора с полным контекстом и описанием задачи пользователя."""

  # Собираем весь контекст документации в один текст
  docs_summary = "\n\n".join([
    f"=== {file_path} ===\n{content}"
    for file_path, content in architect_context.docs_content.items()
  ])

  task_description = user_input.get('task_description', '')

  questions_and_answers = []
  round_count = 0

  while True:
    round_count += 1

    # Формируем промпт с историей Q&A
    qa_history = ""
    if questions_and_answers:
      qa_history = "\n\nPrevious Q&A from this session:\n"
      for q, a in questions_and_answers:
        qa_history += f"Q: {q}\nA: {a}\n\n"

    user_prompt = f"""Current project documentation:
{docs_summary}

User task description:
{task_description}{qa_history}

Your task:
1) Analyze the user's task in context of existing documentation
2) If you need clarification, ask specific questions using 'questions' key
3) If ready to propose changes, use 'proposed_changes' and 'tasks' keys
4) Create concrete tasks for docs/tasks/backlog.yaml with id, title, description, deps, status, type
5) Propose any needed documentation updates in docs/

Return YAML with either:
- questions: [list of specific questions]
OR
- proposed_changes: [{path: docs/..., content: "..."}]
- tasks: [{id: "TASK-001", title: "...", description: "...", deps: [], status: "ready", type: "feature"}]
- problems: [list of any blocking issues]
"""

    output = llm.text(SYSTEM, user_prompt)
    log.write_text(f"architect_round_{round_count}.yaml", output)

    try:
      response_data = yaml.safe_load(output) or {}
    except Exception as e:
      log.write_text(f"architect_round_{round_count}_error.txt", str(e))
      print(f"[ERROR] Invalid YAML response in round {round_count}: {e}")
      continue

    # Проверяем есть ли вопросы
    questions = response_data.get("questions", [])
    if questions:
      print(f"\n[ROUND {round_count}] Architect has {len(questions)} question(s)")
      answers = ask_user_questions(questions)

      # Добавляем Q&A к истории
      for q, a in zip(questions, answers):
        questions_and_answers.append((q, a))

      continue

    # Если вопросов нет - это финальное предложение
    log.write_text("architect_final_proposal.yaml", output)

    all_questions = [qa[0] for qa in questions_and_answers]
    all_answers = [qa[1] for qa in questions_and_answers]

    return ArchitectResult(
      proposal_yaml=output,
      questions=all_questions,
      answers=all_answers,
      round_count=round_count
    )
