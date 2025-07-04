import subprocess
from pathlib import Path
from typing import List

from rich import print


class CommandRunner:
    """A base class for running external commands."""

    def __init__(self, working_dir: Path, command_name: str, executable: str):
        self.working_dir = working_dir
        self.command_name = command_name
        self.executable = executable
        self.working_dir.mkdir(parents=True, exist_ok=True)

    def _run_command(self, command: List[str]):
        """Runs a command and streams its output."""
        display_cmd = " ".join(map(str, command))
        print(f"\n[bold]Running `{display_cmd}` in {self.working_dir}...[/bold]")

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
                f"[bold red]Error: '{self.executable}' command not found. Please ensure"
                f" {self.command_name} is installed and in your PATH.[/bold red]"
            )
            raise
        except subprocess.CalledProcessError as e:
            print(
                f"[bold red]{self.command_name} command failed with exit code {e.returncode}.[/bold"
                " red]"
            )
            raise
