import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from rich import print

from opsmith.infra_provisioners.base_provisioner import BaseInfrastructureProvisioner


class TerraformProvisioner(BaseInfrastructureProvisioner):
    """A wrapper for running TerraformProvisioner commands."""

    def __init__(self, working_dir: Path):
        super().__init__(
            working_dir=working_dir, command_name="TerraformProvisioner", executable="terraform"
        )

    def init_and_apply(self, variables: Dict[str, str], env_vars: Optional[Dict[str, str]] = None):
        """
        Initializes and applies the terraform configuration.
        """
        self._run_command(["terraform", "init", "-no-color"])
        command = ["terraform", "apply", "-auto-approve", "-no-color"]
        for key, value in variables.items():
            command.extend(["-var", f"{key}={value}"])

        tf_env_vars = {}
        for key, value in env_vars.items() or {}:
            tf_env_vars[f"TF_VAR_{key}"] = str(value)

        self._run_command(command, env=tf_env_vars)

    def get_output(self) -> Dict[str, Any]:
        """Retrieves TerraformProvisioner outputs from the working directory."""
        try:
            result = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
            outputs = json.loads(result.stdout)
            return {key: value["value"] for key, value in outputs.items()}
        except FileNotFoundError:
            print(
                "[bold red]Error: 'terraform' command not found. Please ensure TerraformProvisioner"
                " is installed and in your PATH.[/bold red]"
            )
            raise
        except subprocess.CalledProcessError as e:
            print(
                "[bold red]Failed to get TerraformProvisioner outputs. Exit code:"
                f" {e.returncode}[/bold red]\n{e.stderr}"
            )
            raise
        except json.JSONDecodeError:
            print("[bold red]Failed to parse TerraformProvisioner output as JSON.[/bold red]")
            raise
