from orchestrator.task_logging import TaskLog

class Context:
  def __init__(self, log: TaskLog):
    self.log = log
    self.prompt_context :dict[str, str] = {}
    self.step = 0
    self.commit_message = None
    self.new_content = None
    self.review_finished = False

  def write_text(self, filename: str, content: str):
    self.log.write_text(f"{self.step}_{filename}", content)
    self.step += 1

  def write_json(self, filename: str, content):
    self.log.write_json(f"{self.step}_{filename}", content)
    self.step += 1

  def set_commit_candidate(self, message: str, new_content: list[dict[str, str]]):
    self.commit_message = message
    self.new_content = new_content


