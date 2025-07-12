import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal

from pydantic import BaseModel
from pydantic_ai import Agent, ModelRetry, RunContext

from opsmith.utils import generate_secret_string


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
        provider="google-gla", model="gemini-2.5-pro-preview-06-05", api_key_prefix="GEMINI"
    ),
    ModelConfig(provider="google-gla", model="gemini-2.5-pro", api_key_prefix="GEMINI"),
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

    @agent.tool()
    def generate_secret(ctx: RunContext[AgentDeps], length: int = 32) -> str:
        """
        Generates a secure random string of a specified length.
        Useful for creating passwords, API keys, or other secrets.

        Args:
            ctx: The run context object.
            length: The desired length of the secret string. Defaults to 32.

        Returns:
            A secure random string.
        """
        return generate_secret_string(length)

    return agent
