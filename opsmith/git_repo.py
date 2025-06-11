from pathlib import Path
from typing import List

import git
import typer
from rich import print


class GitRepo:
    def __init__(self, root_dir: Path):
        """
        Initialize a Git repository object for the specified directory, or its parent directories
        if it is a subdirectory, ensuring it belongs to an actual Git repository. If the provided
        directory is not within a Git repository, it exits the program with an error.

        :param root_dir: The root directory or subdirectory intended for Git repository initialization.
        :type root_dir: Path

        :raises git.exc.InvalidGitRepositoryError: If the specified directory or its parent directories
            do not contain a valid Git repository.
        :raises typer.Exit: Exits the program if the directory is not part of a valid Git repository.
        """
        try:
            # Initialize repo object, searching upwards from root_dir if it's a subdirectory
            self.repo = git.Repo(str(root_dir), search_parent_directories=True)

        except git.exc.InvalidGitRepositoryError:
            print("[bold red]Not a git repository or git is not found in PATH[/bold red].")
            raise typer.Exit()

    def get_git_tracked_files(self, src_dirs: List[str]) -> List[Path]:
        """
        Retrieves a list of absolute file paths that are tracked by Git within the
        specified source directories.

        The function searches for files tracked by Git within the provided directories,
        respecting the .gitignore file. If there are no tracked files, an empty list
        is returned. The file paths returned are converted into absolute paths relative
        to the Git repository's root directory.

        :param src_dirs: List of source directories (as strings) to scan for Git-tracked
                         files.
        :type src_dirs: List[str]

        :return: A list of absolute file paths for files tracked by Git within the
                 specified source directories.
        :rtype: List[Path]
        """
        # Searching upwards from root_dir if it's a subdirectory
        git_root = Path(self.repo.working_dir)

        # List tracked, cached, and other files (respecting .gitignore)
        # The paths are relative to the git_root.
        ls_files_args = ["-c", "--exclude-standard"]
        ls_files_args.extend(src_dirs)

        tracked_files_str = self.repo.git.ls_files(*ls_files_args)

        if not tracked_files_str:  # Handle case where there are no tracked files
            return []

        relative_paths = tracked_files_str.strip().split("\n")

        # Construct absolute paths and filter out potential empty strings from split
        absolute_paths = [git_root / p for p in relative_paths if p]
        return absolute_paths
