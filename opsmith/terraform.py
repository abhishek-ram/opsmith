import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from rich import print


class TerraformRunner:
    """A wrapper for running TerraformRunner commands."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.working_dir.mkdir(parents=True, exist_ok=True)

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

    def _run_command(self, command: list[str]):
        """Runs a TerraformRunner command and streams its output."""
        print(
            f"\n[bold]Running 'terraform {' '.join(command[1:])}' in {self.working_dir}...[/bold]"
        )
        try:
            process = subprocess.Popen(
                command,
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
            )
            for line in iter(process.stdout.readline, ""):
                print(f"[grey50]{line.strip()}[/grey50]")
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command)
        except FileNotFoundError:
            print(
                "[bold red]Error: 'terraform' command not found. Please ensure TerraformRunner is"
                " installed and in your PATH.[/bold red]"
            )
            raise
        except subprocess.CalledProcessError as e:
            print(
                f"[bold red]TerraformRunner command failed with exit code {e.returncode}.[/bold"
                " red]"
            )
            raise

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
