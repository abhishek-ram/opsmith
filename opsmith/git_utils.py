from pathlib import Path
from typing import List

import git


def get_git_tracked_files(root_dir: Path) -> List[Path]:
    """
    Returns a list of all git-tracked files in the repository as absolute paths.
    Uses GitPython.
    Returns an empty list if not a git repository or no files are tracked.
    """
    try:
        # Initialize repo object, searching upwards from root_dir if it's a subdirectory
        repo = git.Repo(str(root_dir), search_parent_directories=True)
        git_root = Path(repo.working_dir)

        # List tracked, cached, and other files (respecting .gitignore)
        # The paths are relative to the git_root.
        tracked_files_str = repo.git.ls_files("-co", "--exclude-standard", ":!opsmith/queries/*")

        if not tracked_files_str:  # Handle case where there are no tracked files
            return []

        relative_paths = tracked_files_str.strip().split("\n")

        # Construct absolute paths and filter out potential empty strings from split
        absolute_paths = [git_root / p for p in relative_paths if p]
        return absolute_paths

    except git.exc.InvalidGitRepositoryError:
        # Not a git repository or git is not found in PATH
        return []
