import os
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent


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


def build_agent(model_config: ModelConfig, instrument: bool = False) -> Agent:
    agent = Agent(
        model=model_config.model_name_abs,
        # instructions=SYSTEM_PROMPT,
        instrument=instrument,
    )
    return agent
