import os
from typing import Annotated, Optional

import logfire
import typer
from rich import print

from opsmith.agent import AVAILABLE_MODELS_XREF, ModelConfig
from opsmith.analyser import AnalyseRepo
from opsmith.repo_map import RepoMap

app = typer.Typer()


def parse_model_arg(model: str) -> ModelConfig:
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
            parser=parse_model_arg,
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
    logfire_token: Optional[str] = typer.Option(
        default=None,
        help=(
            "Logfire token to be used for logging. If not provided, logs will not be sent to"
            " Logfire."
        ),
    ),
    src_dir: Optional[str] = typer.Option(
        default=None,
        help="Source directory to be used by the command. Defaults to current working directory.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output for repo map generation."
    ),
):
    """
    AI Devops engineer in your terminal.
    """
    if logfire_token:
        logfire.configure(token=logfire_token)


@app.command()
def analyse(ctx: typer.Context):
    """
    Analyses the codebase to determine its deployment configuration.
    Identifies services, their languages, types, and frameworks.
    """
    print("Analysing your codebase now...")
    analyser = AnalyseRepo(
        model_config=ctx.parent.params["model"],
        src_dir=ctx.parent.params["src_dir"] or os.getcwd(),
        verbose=ctx.parent.params["verbose"],
        instrument=bool(ctx.parent.params.get("logfire_token")),
    )
    deployment_config = analyser.analyse()

    if deployment_config.services:
        print("\n[bold green]Identified Deployment Strategy:[/bold green]")
        for i, service in enumerate(deployment_config.services):
            print(f"\n[bold cyan]Service {i + 1}:[/bold cyan]")
            print(f"  Language: {service.language}")
            if service.language_version:
                print(f"  Language Version: {service.language_version}")
            print(f"  Service Type: {service.service_type}")
            if service.framework:
                print(f"  Framework: {service.framework}")
            if service.build_tool:
                print(f"  Build Tool: {service.build_tool}")
    else:
        print(
            "\n[bold yellow]Could not determine deployment strategy or no services found.[/bold"
            " yellow]"
        )


@app.command()
def repomap(ctx: typer.Context):
    """
    Generates a map of the repository, showing important files and code elements.
    """
    print("Generating repo map now...")
    if ctx.parent.params["src_dir"]:
        current_dir_str = ctx.parent.params["src_dir"]
    else:
        current_dir_str = os.getcwd()

    repo_mapper = RepoMap(
        src_dir=current_dir_str,
        verbose=ctx.parent.params["verbose"],
    )
    repo_map_str = repo_mapper.get_repo_map()

    if repo_map_str:
        typer.echo(repo_map_str)
    else:
        typer.echo("No git-tracked files found in this repository or failed to generate map.")
