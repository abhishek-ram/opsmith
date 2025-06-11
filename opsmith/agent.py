import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext


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
    ModelConfig(provider="anthropic", model="claude-3-7-sonnet-latest", api_key_prefix="ANTHROPIC"),
    ModelConfig(provider="anthropic", model="claude-4-0-sonnet-latest", api_key_prefix="ANTHROPIC"),
    ModelConfig(
        provider="google-gla", model="gemini-2.5-pro-preview-05-06", api_key_prefix="GEMINI"
    ),
]

AVAILABLE_MODELS_XREF = {model.model_name_abs: model for model in AVAILABLE_MODELS}


@dataclass
class AgentDeps:
    src_dir: Path


def build_agent(model_config: ModelConfig, instrument: bool = False) -> Agent:
    agent = Agent(
        model=model_config.model_name_abs,
        # instructions=SYSTEM_PROMPT,
        instrument=instrument,
        deps_type=AgentDeps,
    )

    @agent.tool
    def run(ctx: RunContext[AgentDeps], filename: str) -> str:
        """
        Reads and returns the content of a specified file from the repository.
        Use this to understand file structures, dependencies, or specific configurations.
        Provide the relative file path from the repository root.

        Args:
            ctx: The run context object containing the dependencies of the agent.
            filename: The relative path to the file from the repository root.

        Returns:
            The content of the file as a string, or an error message if the file cannot be read.
        """
        if Path(filename).is_absolute():
            return "Error: Absolute file paths are not allowed. Please provide a relative path."

        absolute_file_path = ctx.deps.src_dir.joinpath(filename).resolve()

        if not str(absolute_file_path).startswith(str(ctx.deps.src_dir)):
            return f"Error: Access denied. File '{filename}' is outside the repository root."

        if not absolute_file_path.is_file():
            return f"Error: File '{filename}' not found or is not a regular file."

        with open(absolute_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return content

    return agent
