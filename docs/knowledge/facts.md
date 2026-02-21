### Orchestrator (LLM-driven development pipeline)

* Orchestrator is an external Python CLI tool that manages semi-automated development **on top of an existing git repository**.
* Orchestrator is **not part of the project codebase**. It is executed with `--repo` and operates on the target repository as data.
* All project modifications are performed **only through local git branches and commits** created by the orchestrator.
* Pushing to the remote repository (GitHub) and merging to main/master is **performed manually by the user only**.

### Operating model

* Unit of work: **1 task = 1 branch = 1 (squash) commit**.
* Maximum allowed change per task: **≤ 300 lines of diff**.
* Tasks and their dependencies are defined in `docs/tasks/backlog.yaml`.
* Source of truth priority:

  1. Code
  2. Documentation (`docs/`)
  3. Facts (`docs/knowledge/facts.md`)

### Modes of operation

* **`bootstrap`**
  Used by the architect / tech lead to:

  * initialize and update documentation,
  * validate documentation consistency,
  * create and refine the task backlog.
    Bootstrap may create a dedicated `bootstrap/*` branch and is **restricted to modifying documentation only**.

* **`run`**
  Used to execute tasks from the backlog:

  * create a `task/<TASK_ID>` branch,
  * generate tests,
  * implement code changes,
  * run automated checks (format, lint, typecheck, tests, build).

### Safety and control

* Orchestrator enforces strict path restrictions per role (tester, developer, reviewers).
* All automated checks must pass before any commit is created.
* All agent actions are logged step-by-step under `logs/` for full auditability.
* Interactive mode allows the user to inspect each step and explicitly approve progression.

