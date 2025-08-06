import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from rich import print

from opsmith.infra_provisioners.base_provisioner import BaseInfrastructureProvisioner


class AnsibleProvisioner(BaseInfrastructureProvisioner):
    """A wrapper for running ansible-playbook commands."""

    def __init__(self, working_dir: Path):
        super().__init__(
            working_dir=working_dir, command_name="Ansible", executable="ansible-playbook"
        )
        ansible_cfg_path = self.working_dir / "ansible.cfg"
        with open(ansible_cfg_path, "w", encoding="utf-8") as f:
            f.write("[defaults]\n")
            f.write("host_key_checking = False\n")
            f.write("deprecation_warnings = False\n")

    def run_playbook(
        self,
        playbook_name: str,
        extra_vars: Dict[str, Union[str, List[str]]],
        inventory: Optional[str] = None,
        user: Optional[str] = None,
    ) -> Dict[str, str]:
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
        if inventory:
            # The comma is important for a single host inventory
            command.extend(["-i", f"{inventory},"])
        elif (self.working_dir / "inventory.yml").exists():
            command.extend(["-i", "inventory.yml"])

        if user:
            command.extend(["--user", user])

        if extra_vars:
            command.extend(["--extra-vars", json.dumps(extra_vars)])

        return self._run_command(command)
