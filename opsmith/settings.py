from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class OpsmithSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OPSMITH_", yaml_file=".opsmith.conf.yml")

    deployments_dir: str = ".opsmith"
    config_filename: str = "deployments.yml"
    max_dockerfile_gen_attempts: int = 3
    max_docker_compose_gen_attempts: int = 3

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)


settings = OpsmithSettings()
