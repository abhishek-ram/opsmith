# Engineering Conventions

## Conventions
> When writing code follow these conventions

- Write simple verbose code over terse, compact, dense code
- Use types everywhere possible.
- Add logs where applicable so that debugging becomes easy
- Add docstring to functions that describe its use
- Add try/except blocks sparingly, only where it is essential
- Use pytest to write tests
- Add docstring to each test case that describes its flow clearly
- Tests should mock out external calls and command calls
- Do not assert on logs in tests as that is not a best practice

## Project Structure

- `opsmith/` - Source code for this CLI tool
  - `cloud_providers/` - Cloud provider implementations (e.g., AWS, GCP).
  - `deployment_strategies/` - Application deployment strategies (e.g., monolithic).
  - `infra_provisioners/` - Wrappers for infrastructure tools (e.g., Terraform, Ansible).
  - `templates/` - Infrastructure-as-code templates (e.g., Terraform modules, Ansible Playbooks).
  - `tests/` - Tests for all the components
  - `agent.py` - AI agent logic.
  - `exceptions.py` - Custom exceptions used by Opsmith
  - `git_repo.py` - Connector for a git repo
  - `main.py` - CLI command definitions (Typer).
  - `models.py` - List of available LLMs
  - `prompts.py` - Prompts used to interact with the LLM
  - `repo_map.py` - Generates a ,ap of the files in the repository
  - `service_detector.py` - Logic to detect services in a repository.
  - `settings.py` - Configurations for Opsmith 
  - `types.py` - Core Pydantic data models for configuration and state.
  - `utils.py` - Shared utility functions.

