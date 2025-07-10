import json
from pathlib import Path
from typing import Dict

from rich import print

from opsmith.infra_provisioners.base_provisioner import BaseInfrastructureProvisioner


class AnsibleProvisioner(BaseInfrastructureProvisioner):
    """A wrapper for running ansible-playbook commands."""

    def __init__(self, working_dir: Path):
        super().__init__(
            working_dir=working_dir, command_name="Ansible", executable="ansible-playbook"
        )

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
