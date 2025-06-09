import os

import typer

from opsmith.repo_map import RepoMap

app = typer.Typer()


@app.callback()
def main():
    """
    AI Devops engineer in your terminal.
    """


@app.command()
def analyse():
    typer.echo("Analysing your codebase now")


@app.command()
def repomap(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output for repo map generation."
    ),
):
    """
    Generates a map of the repository, showing important files and code elements.
    """
    current_dir_str = os.getcwd()

    repo_mapper = RepoMap(
        root=current_dir_str,
        verbose=verbose,
    )
    repo_map_str = repo_mapper.get_repo_map()

    if repo_map_str:
        typer.echo(repo_map_str)
    else:
        typer.echo("No git-tracked files found in this repository or failed to generate map.")
