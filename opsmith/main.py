import os
from typing import Annotated, Optional

import google.auth
import inquirer
import logfire
import typer
import yaml
from rich import print

from opsmith.agent import AVAILABLE_MODELS_XREF, ModelConfig
from opsmith.cloud_providers import CLOUD_PROVIDER_REGISTRY
from opsmith.cloud_providers.base import CloudCredentialsError, CloudProviderEnum
from opsmith.deployer import Deployer, DeploymentConfig  # Import the new Deployer class
from opsmith.repo_map import RepoMap
from opsmith.scanner import RepoScanner
from opsmith.settings import settings

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
def scan(ctx: typer.Context):
    """
    Scans the codebase to determine its deployment configuration.
    Identifies services, their languages, types, and frameworks.
    """
    deployer = Deployer()
    deployment_config = deployer.get_deployment_config()
    if not deployment_config:
        print("No existing deployment configuration found. Starting analysis...")

        questions = [
            inquirer.List(
                "cloud_provider",
                message="Select the cloud provider for deployment",
                choices=[provider.value for provider in CloudProviderEnum],
            ),
        ]
        answers = inquirer.prompt(questions)
        if not answers:
            print("[bold red]Cloud provider selection is required. Aborting.[/bold red]")
            raise typer.Exit(code=1)

        selected_provider_value = answers["cloud_provider"]
        selected_provider_enum = CloudProviderEnum(selected_provider_value)

        print(f"Initializing {selected_provider_enum.name} provider...")
        provider_class = CLOUD_PROVIDER_REGISTRY[selected_provider_enum]

        try:
            # Instantiation might raise CloudCredentialsError (e.g. GCPProvider.__init__)
            provider_instance = provider_class()
            cloud_details = provider_instance.get_account_details()
        except CloudCredentialsError as e:
            print(f"[bold red]Cloud provider authentication/configuration error:\n{e}[/bold red]")
            raise typer.Exit(code=1)
        except Exception as e:  # Catch other unexpected errors
            print(
                "[bold red]An unexpected error occurred while initializing cloud provider or"
                f" fetching details: {e}. Aborting.[/bold red]"
            )
            raise typer.Exit(code=1)

        print("Analysing your codebase now...")
        analyser = RepoScanner(
            model_config=ctx.parent.params["model"],
            src_dir=ctx.parent.params["src_dir"] or os.getcwd(),
            verbose=ctx.parent.params["verbose"],
            instrument=bool(ctx.parent.params.get("logfire_token")),
        )
        service_list_obj = analyser.scan()  # Returns ServiceList (RootModel)

        new_deployment_config = DeploymentConfig(
            cloud_provider=cloud_details,
            services=service_list_obj.services,  # Access the list via .services
        )

        # Save the deployment configuration using the Deployer
        deployer.save_deployment_config(new_deployment_config)

        print("\n[bold green]Identified Deployment Configuration:[/bold green]")
        print(yaml.dump(new_deployment_config.model_dump(mode="json")))
    else:
        print(
            "\n[bold yellow]Existing deployment configuration found. To re-scan, delete the"
            f" existing file at {deployer.config_file_path} and run scan again.[/bold yellow]"
        )
        print("\n[bold green]Current Deployment Configuration:[/bold green]")
        print(yaml.dump(deployment_config.model_dump(mode="json")))


@app.command()
def deploy(ctx: typer.Context):
    """"""
    print(google.auth.default())
    questions = [
        inquirer.List(
            "size",
            message="What size do you need?",
            choices=["Jumbo", "Large", "Standard", "Medium", "Small", "Micro"],
        ),
    ]
    inquirer.prompt(questions)
    print(settings.deployments_dir)


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
