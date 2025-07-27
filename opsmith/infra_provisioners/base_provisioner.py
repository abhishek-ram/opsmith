import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from rich import print
from rich.markup import escape


class BaseInfrastructureProvisioner:
    """
    Base class for provisioning infrastructure using specific commands or executables.

    Provides functionalities to handle command execution in a specified working directory.
    Ensures necessary directory setup and robust command execution with output streaming.

    :ivar working_dir: Directory where the commands will be executed.
    :type working_dir: Path
    :ivar command_name: Name of the command/tool being executed (for user feedback).
    :type command_name: str
    :ivar executable: Name or path of the executable/tool to be used for command execution.
    :type executable: str
    """

    def __init__(self, working_dir: Path, command_name: str, executable: str):
        self.working_dir = working_dir
        self.command_name = command_name
        self.executable = executable
        self.working_dir.mkdir(parents=True, exist_ok=True)

    def copy_template(self, template_name: str, provider: str):
        """
        Copies templates to the working directory.
        """
        template_dir = Path(__file__).parent.parent / "templates" / template_name / provider
        if not template_dir.exists() or not template_dir.is_dir():
            print(
                f"[bold red]{self.command_name} templates for {provider.upper()} not found at"
                f" {template_dir}.[/bold red]"
            )
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        # Use shutil.copytree to copy the contents of the template directory
        shutil.copytree(template_dir, self.working_dir, dirs_exist_ok=True)

        print(f"[grey50]{self.command_name} files copied to: {self.working_dir}[/grey50]")

    def _run_command(
        self, command: List[str], env: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Runs a command and streams its output."""
        process_env = os.environ.copy()
        process_env.update(env or {})
        outputs = {}
        full_output = []

        try:
            process = subprocess.Popen(
                command,
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                env=process_env,
            )
            for line in iter(process.stdout.readline, ""):
                stripped_line = line.strip()
                full_output.append(stripped_line)
                print(f"[grey50]{escape(stripped_line)}[/grey50]")
                match = re.search(r'"msg":\s*"OPSMITH_OUTPUT_(\w+)=([^"]*)"', stripped_line)
                if match:
                    key = match.group(1).lower()
                    value = match.group(2)
                    outputs[key] = value
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, command, output="\n".join(full_output)
                )
        except FileNotFoundError:
            print(
                f"[bold red]Error: '{self.executable}' command not found. Please ensure"
                f" {self.command_name} is installed and in your PATH.[/bold red]"
            )
            raise
        except subprocess.CalledProcessError as e:
            # The 'output' parameter for CalledProcessError sets the 'stdout' attribute
            print(
                f"[bold red]{self.command_name} command failed with exit code {e.returncode}.[/bold"
                " red]"
            )
            raise
        return outputs
