import json
import os
import shutil
import subprocess
import tempfile
import uuid  # Added for unique naming
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext


class ModelConfig(BaseModel):
    provider: Literal["openai", "anthropic", "google-gla"]
    model: str
    api_key_prefix: str

    @property
    def model_name_abs(self):
        return f"{self.provider}:{self.model}"

    @property
    def api_key_env_var(self):
        return f"{self.api_key_prefix}_API_KEY"

    def ensure_auth(self, api_key: str):
        os.environ[self.api_key_env_var] = api_key.strip()


AVAILABLE_MODELS = [
    ModelConfig(provider="openai", model="gpt-4.1", api_key_prefix="OPENAI"),
    ModelConfig(
        provider="anthropic", model="claude-3-7-sonnet-20250219", api_key_prefix="ANTHROPIC"
    ),
    ModelConfig(provider="anthropic", model="claude-sonnet-4-20250514", api_key_prefix="ANTHROPIC"),
    ModelConfig(
        provider="google-gla", model="gemini-2.5-pro-preview-05-06", api_key_prefix="GEMINI"
    ),
    ModelConfig(
        provider="google-gla", model="gemini-2.5-pro-preview-06-05", api_key_prefix="GEMINI"
    ),
]

AVAILABLE_MODELS_XREF = {model.model_name_abs: model for model in AVAILABLE_MODELS}


@dataclass
class AgentDeps:
    src_dir: Path


def is_duplicate_tool_call(ctx: RunContext[AgentDeps], tool_name: str) -> bool:
    """"""
    tool_calls = set()
    message_parts = [item for message in ctx.messages for item in message.parts]
    for part in message_parts:
        if part.part_kind == "tool-call" and part.tool_name == tool_name:
            if isinstance(part.args, dict):
                tool_args = json.dumps(part.args, sort_keys=True)
            else:
                tool_args = part.args
            if tool_args in tool_calls:
                return True
            else:
                # logger.debug(f"Tool {tool_def.name} called with arguments: {tool_args}")
                tool_calls.add(tool_args)

    return False


def build_agent(model_config: ModelConfig, instrument: bool = False) -> Agent:
    agent = Agent(
        model=model_config.model_name_abs,
        # instructions=SYSTEM_PROMPT,
        instrument=instrument,
        deps_type=AgentDeps,
    )

    @agent.tool(retries=5)
    def read_file_content(ctx: RunContext[AgentDeps], filenames: List[str]) -> List[str]:
        """
        Reads and returns the content of specified files from the repository.
        Use this to understand file structures, dependencies, or specific configurations.
        Provide the relative file paths from the repository root.

        Args:
            ctx: The run context object containing the dependencies of the agent.
            filenames: A list of relative paths to the files from the repository root.

        Returns:
            A list of strings, where each string is the content of the corresponding file.
            The order of contents in the list matches the order of filenames in the input.
        """
        if is_duplicate_tool_call(ctx, "read_file_content"):
            raise ModelRetry(
                "The tool 'read_file_content' has already been called with the exact same list of "
                "files in this conversation."
            )

        contents = []
        for filename in filenames:
            if Path(filename).is_absolute():
                raise ModelRetry(
                    f"Absolute file paths are not allowed for '{filename}'. Please provide a"
                    " relative path."
                )

            absolute_file_path = ctx.deps.src_dir.joinpath(filename).resolve()

            if not str(absolute_file_path).startswith(str(ctx.deps.src_dir)):
                raise ModelRetry(
                    f"Access denied. File '{filename}' is outside the repository root."
                )

            if not absolute_file_path.is_file():
                raise ModelRetry(f"File '{filename}' not found or is not a regular file.")

            with open(absolute_file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            contents.append(content)
        return contents

    @agent.tool(retries=3)
    def build_dockerfile(
        ctx: RunContext[AgentDeps],
        dockerfile_content: str,
    ) -> str:
        """
        Writes the provided Dockerfile content to a temporary file, then attempts to build a Docker image
        using that Dockerfile and the repository root as the build context.
        If the build is successful, it attempts to run the built image with a short timeout.
        Returns the combined output (stdout and stderr) of the 'docker build' and 'docker run' commands.

        Use this tool to validate a generated Dockerfile.
        - If the build fails, analyze the build output, revise the Dockerfile content, and call this tool again.
        - If the build succeeds but the image run fails due to issues like missing packages or invalid commands
          (ignoring errors related to missing environment variables or connection issues),
          analyze the run output, revise the Dockerfile, and call this tool again.

        Args:
            ctx: The run context object.
            dockerfile_content: The string content of the Dockerfile to be built and run.

        Returns:
            A string containing the combined stdout and stderr from the 'docker build'
            and 'docker run' commands. If 'docker' command is not found, an error message is returned.
        """
        repo_root = ctx.deps.src_dir.resolve()
        image_tag = f"opsmith-build-test-{uuid.uuid4()}"
        build_output_str = ""

        # Check if docker command is available
        if not shutil.which("docker"):
            raise ModelRetry(
                "Error: Docker command not found. Please ensure Docker is installed and in your"
                " PATH."
            )

        try:
            # Create temporary directory for Dockerfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dockerfile = Path(temp_dir) / "Dockerfile"
                # Write Dockerfile content
                with open(temp_dockerfile, "w", encoding="utf-8") as f:
                    f.write(dockerfile_content)

                # Execute docker build command
                build_process = subprocess.run(
                    [
                        "docker",
                        "build",
                        "-f",
                        str(temp_dockerfile),
                        "-t",
                        image_tag,
                        str(repo_root),
                    ],
                    capture_output=True,
                    text=True,
                )
                build_output_str = (
                    f"Build Output (stdout):\n{build_process.stdout}\nBuild Output"
                    f" (stderr):\n{build_process.stderr}"
                )

                if build_process.returncode != 0:
                    # Build failed, instruct LLM to retry with build output
                    raise ModelRetry(
                        "Dockerfile build failed. Analyze the following output and revise the"
                        f" Dockerfile:\n{build_output_str}"
                    )

            # Build successful, now try to run the image
            # Using --rm to automatically remove the container when it exits.
            run_process = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    image_tag,
                ],  # Removed explicit container name as --rm handles it
                capture_output=True,
                text=True,
                timeout=30,  # Timeout for the run command to prevent indefinite hangs
            )
            run_output_str = (
                f"Run Output (stdout):\n{run_process.stdout}\nRun Output"
                f" (stderr):\n{run_process.stderr}"
            )

            if run_process.returncode != 0:
                # Run failed. Raise ModelRetry with the run output for the LLM to analyze.
                # The LLM will decide if the error is due to the Dockerfile or an ignorable runtime issue.
                raise ModelRetry(
                    "Dockerfile built successfully, but running the image failed. Analyze the"
                    " following run output to determine if the Dockerfile needs revision (e.g.,"
                    " for missing packages, command errors) or if the error is ignorable (e.g.,"
                    " missing environment variables, connection issues).\n\nRun"
                    f" Output:\n{run_output_str}\n\nOriginal Build Output was:\n{build_output_str}"
                )
        finally:
            # Clean up image
            if image_tag:  # ensure image_tag was set before trying to remove
                cleanup_image_process = subprocess.run(
                    ["docker", "rmi", "-f", image_tag], capture_output=True, text=True
                )
                if (
                    cleanup_image_process.returncode != 0
                    and "no such image" not in cleanup_image_process.stderr.lower()
                ):
                    # Log or handle image removal failure if necessary, but don't fail the tool for this
                    # This could happen if the build failed before the image was tagged,
                    # or if another process removed it.
                    print(
                        f"Warning: Failed to remove Docker image {image_tag}:"
                        f" {cleanup_image_process.stderr.strip()}"
                    )

        return f"{build_output_str}\n\n{run_output_str}".strip()

    return agent
