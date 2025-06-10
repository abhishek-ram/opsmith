import os
from typing import Annotated

import typer
from rich import print

from opsmith.agent import AVAILABLE_MODELS_XREF, ModelConfig
from opsmith.analyser import AnalyseRepo
from opsmith.repo_map import RepoMap

app = typer.Typer()


def get_model_config(model: str) -> ModelConfig:
    """
    Fetches the configuration corresponding to the given model name.

    Attempts to retrieve the configuration for the provided model from
    the mapping of available models. If the model name is not found in
    the mapping, an error is raised indicating that the model is unsupported.

    :param model: The name of the model for which the configuration is required.
    :type model: str

    :return: The configuration corresponding to the provided model name.
    :rtype: ModelConfig

    :raises KeyError: If the given model name is not found in the available models mapping.
    :raises typer.BadParameter: If the provided model name is unsupported.
    """
    try:
        return AVAILABLE_MODELS_XREF[model]
    except KeyError:
        raise typer.BadParameter(
            f"Unsupported model name: {model}, must be one of: {AVAILABLE_MODELS_XREF.keys()}"
        )


def api_key_callback(ctx: typer.Context, value: str):
    """
    This function serves as a callback for validating and processing an API key when
    used in conjunction with a command-line interface. The function checks whether
    the mandatory `--model` option is set before associating it with the provided
    API key. If validation passes, it ensures the API key authentication process
    is triggered for the specified model configuration.

    Raises a BadParameter error if `--model` was not supplied before `--api-key`.

    :param ctx: The Typer context object that contains information about the
        current command execution context, including provided options and other
        runtime parameters.
    :type ctx: typer.Context
    :param value: The API key provided by the user via the `--api-key` option
        during the command-line execution.
    :type value: str
    :return: The validated API key after ensuring it is associated with the
        specified model configuration.
    :rtype: str
    """
    if "model" not in ctx.params:
        raise typer.BadParameter("The --model option must be specified before --api-key.")
    model_config = ctx.params["model"]
    model_config.ensure_auth(value)
    return value


@app.callback()
def main(
    model: Annotated[
        ModelConfig,
        typer.Option(
            parser=get_model_config,
            help="The LLM model to be used for by the AI Agent.",
        ),
    ],
    api_key: Annotated[
        str,
        typer.Option(
            callback=api_key_callback,
            help=(
                "The API KEY to be used for by the AI Agent. This is the API key for the specified"
                " model."
            ),
        ),
    ],
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output for repo map generation."
    ),
):
    """
    AI Devops engineer in your terminal.
    """


@app.command()
def analyse(ctx: typer.Context):
    print("Analysing your codebase now")
    analyser = AnalyseRepo(
        model_config=ctx.parent.params["model"],
        root_dir=os.getcwd(),
        verbose=ctx.parent.params["verbose"],
    )
    analyser.analyse()
    print("Done")


@app.command()
def repomap(ctx: typer.Context):
    """
    Generates a map of the repository, showing important files and code elements.
    """
    current_dir_str = os.getcwd()

    repo_mapper = RepoMap(
        root=current_dir_str,
        verbose=ctx.parent.params["verbose"],
    )
    repo_map_str = repo_mapper.get_repo_map()

    if repo_map_str:
        typer.echo(repo_map_str)
    else:
        typer.echo("No git-tracked files found in this repository or failed to generate map.")
