import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from rich import print

from opsmith.command_runner import CommandRunner


class TerraformRunner(CommandRunner):
    """A wrapper for running TerraformRunner commands."""

    def __init__(self, working_dir: Path):
        super().__init__(
            working_dir=working_dir, command_name="TerraformRunner", executable="terraform"
        )

    def copy_template(self, template_name: str, provider: str, variables: Dict[str, str]):
        """
        Copies TerraformRunner templates to the working directory and creates a .tfvars file.
        """
        template_dir = Path(__file__).parent / "templates" / template_name / provider
        if not template_dir.exists() or not template_dir.is_dir():
            print(
                f"[bold red]TerraformRunner templates for {provider.upper()} not found at"
                f" {template_dir}.[/bold red]"
            )
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        # Use shutil.copytree to copy the contents of the template directory
        shutil.copytree(template_dir, self.working_dir, dirs_exist_ok=True)

        # Create terraform.tfvars file with dynamic values
        tfvars_content = [f'{key} = "{value}"' for key, value in variables.items()]
        tfvars_path = self.working_dir / "terraform.tfvars"
        with open(tfvars_path, "w", encoding="utf-8") as f:
            f.write("\n".join(tfvars_content) + "\n")

        print(f"[green]TerraformRunner files and variables copied to: {self.working_dir}[/green]")

    def init_and_apply(self):
        """
        Initializes and applies the terraform configuration.
        """
        self._run_command(["terraform", "init", "-no-color"])
        self._run_command(["terraform", "apply", "-auto-approve", "-no-color"])

    def get_output(self) -> Dict[str, Any]:
        """Retrieves TerraformRunner outputs from the working directory."""
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
                "[bold red]Error: 'terraform' command not found. Please ensure TerraformRunner is"
                " installed and in your PATH.[/bold red]"
            )
            raise
        except subprocess.CalledProcessError as e:
            print(
                "[bold red]Failed to get TerraformRunner outputs. Exit code:"
                f" {e.returncode}[/bold red]\n{e.stderr}"
            )
            raise
        except json.JSONDecodeError:
            print("[bold red]Failed to parse TerraformRunner output as JSON.[/bold red]")
            raise
