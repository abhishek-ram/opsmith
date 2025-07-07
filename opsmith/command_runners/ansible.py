import json
import shutil
from pathlib import Path
from typing import Dict

from rich import print

from opsmith.command_runners.base_runner import CommandRunner


class AnsibleRunner(CommandRunner):
    """A wrapper for running ansible-playbook commands."""

    def __init__(self, working_dir: Path):
        super().__init__(
            working_dir=working_dir, command_name="Ansible", executable="ansible-playbook"
        )

    def copy_template(self, template_name: str, provider: str, variables: Dict[str, str]):
        """
        Copies Ansible playbook to the working directory.
        """
        template_dir = Path(__file__).parent.parent / "templates" / template_name / provider
        if not template_dir.exists() or not template_dir.is_dir():
            print(
                f"[bold red]Ansible playbook template for {provider} not found at"
                f" {template_dir}.[/bold red]"
            )
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        shutil.copytree(template_dir, self.working_dir, dirs_exist_ok=True)
        print(f"[green]Ansible playbook copied to: {self.working_dir}[/green]")

    def run_playbook(self, playbook_name: str, extra_vars: Dict[str, str]):
        """
        Runs an ansible playbook.
        """
        playbook_path = self.working_dir / playbook_name
        if not playbook_path.exists():
            print(
                f"[bold red]Playbook '{playbook_name}' not found in {self.working_dir}[/bold red]"
            )
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        command = ["ansible-playbook", str(playbook_path)]
        if extra_vars:
            command.extend(["--extra-vars", json.dumps(extra_vars)])

        self._run_command(command)
