import re
import secrets
import shutil
import string
import subprocess
from typing import List

from rich.console import Console
from rich.status import Status
from rich.text import Text


def get_missing_external_dependencies(dependencies: List[str]) -> List[str]:
    """
    Checks if a list of external command-line tools are installed and operational.
    For Docker, it checks if the daemon is running. For Terraform, it checks if it's executable.

    :param dependencies: A list of command names to check (e.g., ['docker', 'terraform']).
    :return: A list of dependency names that were not found or are not operational.
    """
    missing_deps = []
    for dep in dependencies:
        command = None
        if dep == "docker":
            command = ["docker", "info"]
        elif dep == "terraform":
            command = ["terraform", "version"]

        if command:
            try:
                subprocess.run(command, check=True, capture_output=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                missing_deps.append(dep)
        else:
            if not shutil.which(dep):
                missing_deps.append(dep)
    return missing_deps


def slugify(value: str) -> str:
    """
    Converts a given string into a slug format. The slug format is typically
    used for URLs, where spaces are replaced with hyphens and all characters
    are converted to lowercase.

    :param value: The string to be converted into slug format.
    :type value: str
    :return: A slugified version of the input string.
    :rtype: str
    """
    return re.sub(r"[^a-z0-9-]", "", value.lower().replace(" ", "-"))


def generate_secret_string(length: int = 32) -> str:
    """
    Generates a secure random string.

    :param length: The length of the secret string to generate.
    :return: A secure random string.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_logo() -> Text:
    """
    Builds and returns an ASCII art logo styled with specific colors and text formats.
    The function creates a stylized representation of a logo using the ``Text`` object.
    Each line of the logo is appended to the text object with a distinct style, alternating
    between bold cyan and bold blue.

    :return: Styled ASCII art logo representation.
    :rtype: Text
    """
    ascii_art_logo = Text()
    ascii_art_logo.append(
        "\n ██████  ██████  ███████ ███    ███ ██ ████████ ██   ██\n", style="bold cyan"
    )
    ascii_art_logo.append(
        "██    ██ ██   ██ ██      ████  ████ ██    ██    ██   ██\n", style="bold blue"
    )
    ascii_art_logo.append(
        "██    ██ ██████  ███████ ██ ████ ██ ██    ██    ███████\n", style="bold cyan"
    )
    ascii_art_logo.append(
        "██    ██ ██           ██ ██  ██  ██ ██    ██    ██   ██\n", style="bold blue"
    )
    ascii_art_logo.append(
        " ██████  ██      ███████ ██      ██ ██    ██    ██   ██\n\n", style="bold cyan"
    )
    return ascii_art_logo


class WaitingSpinner:
    """A wrapper for rich.console.Status that can be used as a context manager."""

    def __init__(self, text: str = "Waiting..."):
        self.console = Console()
        self.status: Status = self.console.status(text)

    def start(self):
        """Start the spinner."""
        self.status.start()

    def stop(self):
        """Stop the spinner."""
        self.status.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
