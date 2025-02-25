import os
import platform
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Union

try:
    import chromadb

    CHROMA_INSTALLED = True
except ModuleNotFoundError:
    CHROMA_INSTALLED = False


if platform.system() == "Windows":
    DEFAULT_DB_CONNECTION_URL = "sqlite+aiosqlite:///$MARVIN_HOME/marvin.sqlite"
else:
    DEFAULT_DB_CONNECTION_URL = "sqlite+aiosqlite:////$MARVIN_HOME/marvin.sqlite"

from pydantic import BaseSettings, Field, SecretStr, root_validator, validator
from rich import print
from rich.text import Text

import marvin

# a configurable env file location
ENV_FILE = Path(os.getenv("MARVIN_ENV_FILE", "~/.marvin/.env")).expanduser()
ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
ENV_FILE.touch(exist_ok=True)


class LLMBackend(str, Enum):
    OpenAI = "OpenAI"
    AzureOpenAI = "AzureOpenAI"
    OpenAIChat = "OpenAIChat"
    AzureOpenAIChat = "AzureOpenAIChat"
    Anthropic = "Anthropic"
    HuggingFaceHub = "HuggingFaceHub"


def infer_llm_backend(model: str = None) -> LLMBackend:
    """
    Infer backends for common models. This list does NOT have to be complete, as
    it is purely a convenience.
    """
    if model.startswith("gpt-3") or model.startswith("gpt-4"):
        return LLMBackend.OpenAIChat
    elif (
        model.startswith("text-davinci")
        or model.startswith("text-curie")
        or model.startswith("text-babbage")
        or model.startswith("text-ada")
    ):
        return LLMBackend.OpenAI
    elif model.startswith("claude"):
        return LLMBackend.Anthropic
    else:
        raise ValueError(
            "No LLM backend provided and could not infer one from `llm_model`."
        )


if CHROMA_INSTALLED:

    class ChromaSettings(chromadb.config.Settings):
        class Config:
            env_file = ".env", str(ENV_FILE)
            env_prefix = "MARVIN_"

        chroma_db_impl: Literal["duckdb", "duckdb+parquet", "clickhouse"] = (
            "duckdb+parquet"
        )
        chroma_server_host: str = "localhost"
        chroma_server_http_port: int = 8000
        # relative paths will be prefixed with the marvin home directory
        persist_directory: str = "chroma"

else:

    class ChromaSettings(BaseSettings):
        pass


class Settings(BaseSettings):
    """Marvin settings"""

    class Config:
        env_file = ".env", str(ENV_FILE)
        env_prefix = "MARVIN_"
        validate_assignment = True

    def export_to_env_file(self, f: str = None):
        with open(f or self.Config.env_file[0], "w") as env_file:
            for field_name, value in self.dict().items():
                env_key = f"{self.Config.env_prefix}{field_name.upper()}"
                env_value = (
                    str(value)
                    if not isinstance(value, SecretStr)
                    else value.get_secret_value()
                )
                env_file.write(f"{env_key}={env_value}\n")

    home: Path = Path("~/.marvin").expanduser()
    test_mode: bool = False

    # LOGGING
    verbose: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_console_width: Optional[int] = Field(
        None,
        description=(
            "Marvin will auto-detect the console width when possible, but in deployed"
            " settings logs will assume a console width of 80 characters unless"
            " specified here."
        ),
    )
    rich_tracebacks: bool = Field(False, description="Enable rich traceback formatting")

    # LLMS
    llm_model: str = Field(
        "gpt-3.5-turbo", description="An LLM model name compatible with the backend"
    )
    llm_backend: LLMBackend = Field(
        None,
        description=(
            "A compatible LLM backend. In some cases, can be inferred from the"
            " llm_model."
        ),
    )
    llm_max_tokens: int = 1250
    llm_temperature: float = 0.8
    llm_request_timeout_seconds: Union[float, list[float]] = 600.0
    llm_extra_kwargs: dict = Field(
        default_factory=dict,
        description=(
            "Additional kwargs to pass to the LLM backend. Only use for kwargs that"
            " aren't directly exposed."
        ),
    )
    llm_model_for_response_format: str = Field(
        None,
        description=(
            "An LLM model name compatible with the backend, solely used for formatting"
            " responses. If not supplied, will be the same as the `llm_model` (except"
            " GPT-3.5 will be used for GPT-4.)"
        ),
    )

    # EMBEDDINGS
    # specify the path to the embeddings cache, relative to the home dir
    embeddings_cache_path: Path = Path("cache/embeddings.sqlite")
    embeddings_cache_warn_size: int = 4000000000  # 4GB

    # OPENAI
    openai_api_key: SecretStr = Field(
        None,
        # for third-party LLM services we check global env vars as well
        env=["MARVIN_OPENAI_API_KEY", "OPENAI_API_KEY"],
    )
    openai_organization: str = Field(None)
    openai_api_base: str = None

    # ANTHROPIC
    anthropic_api_key: SecretStr = Field(
        None,
        # for third-party LLM services we check global env vars as well
        env=["MARVIN_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
    )

    # HUGGINGFACE HUB
    huggingfacehub_api_token: SecretStr = Field(
        None,
        # for third-party LLM services we check global env vars as well
        env=["MARVIN_HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACEHUB_API_TOKEN"],
    )

    # CHROMA
    chroma: ChromaSettings = Field(default_factory=ChromaSettings)

    # DISCOURSE
    discourse_api_key: SecretStr = Field(default=SecretStr(""))
    discourse_api_username: str = Field("nate")
    discourse_url: str = Field("https://discourse.prefect.io")
    discourse_help_category_id: int = 27

    # DOCUMENTS
    default_topic = "marvin"
    default_n_keywords: int = 15

    # DATABASE
    database_echo: bool = False
    database_connection_url: SecretStr = DEFAULT_DB_CONNECTION_URL
    database_check_migration_version_on_startup: bool = True

    # GITHUB
    github_token: SecretStr = Field(default=SecretStr(""))

    # REDIS
    redis_connection_url: SecretStr = None

    # BOTS
    bot_create_profile_picture: bool = Field(
        False,
        description=(
            "if True, a profile picture will be generated for new bots when they are"
            " saved in the database."
        ),
    )
    bot_max_iterations: int = 10
    bot_load_default_plugins: bool = Field(
        True,
        description=(
            "If True, bots will load a default set of plugins if none are provided."
        ),
    )

    # SLACK
    slack_bot_name: str = Field(
        "Marvin",
        description=(
            "The bot name to use to respond to Slack messages. The bot must be created"
            " and saved first."
        ),
    )
    slack_api_token: SecretStr = Field(
        None, description="The Slack API token to use to respond to Slack messages."
    )
    slack_bot_admin_user: str = Field(
        "!here",
        description="The Slack user to notify when slack bot is improperly configured.",
    )

    slack_bot_authorized_QA_users: str = Field(
        "", env=["MARVIN_SLACK_BOT_AUTHORIZED_QA_USERS"]
    )

    QA_slack_bot_responses: bool = Field(
        False,
        description="If True, slack bot responses will be intercepted in a QA channel.",
    )
    slack_bot_QA_channel: str = Field(
        None,
        description="The ID of the Slack channel to use for QA'ing slackbot answers.",
    )
    feedback_mechanism: Literal["create_chroma_document", "create_discourse_topic"] = (
        Field(
            "create_discourse_topic", description="Where to save feedback from Slack."
        )
    )

    # STACKEXCHANGE
    stackexchange_api_key: SecretStr = Field(None)

    # API
    api_base_url: str = "http://127.0.0.1"
    api_port: int = 4200
    api_reload: bool = Field(
        False,
        description=(
            "If true, the API will reload on file changes. Use only for development."
        ),
    )

    @root_validator
    def initial_setup(cls, values):
        values["home"].mkdir(parents=True, exist_ok=True)

        # prefix HOME to embeddings cache path
        if not values["embeddings_cache_path"].is_absolute():
            values["embeddings_cache_path"] = (
                values["home"] / values["embeddings_cache_path"]
            )
        values["embeddings_cache_path"].parent.mkdir(parents=True, exist_ok=True)

        if CHROMA_INSTALLED:
            # prefix HOME to chroma path
            chroma_persist_directory = Path(values["chroma"]["persist_directory"])
            if not chroma_persist_directory.is_absolute():
                chroma_persist_directory = values["home"] / chroma_persist_directory
                values["chroma"] = ChromaSettings(
                    **values["chroma"].dict(exclude={"persist_directory"}),
                    persist_directory=str(chroma_persist_directory),
                )

        # interpolate HOME into database connection URL
        values["database_connection_url"] = SecretStr(
            values["database_connection_url"]
            .get_secret_value()
            .replace("$MARVIN_HOME", str(values["home"]))
        )

        # print if verbose = True
        if values["verbose"]:
            print(Text("Verbose mode enabled", style="green"))

        return values

    @validator("llm_backend", pre=True, always=True)
    def infer_llm_backend(cls, v, values):
        if v is None:
            return infer_llm_backend(values["llm_model"])
        return v

    @validator("llm_model_for_response_format", pre=True, always=True)
    def infer_llm_model_for_response_format(cls, v, values):
        if v is None:
            if values["llm_model"].startswith("gpt-4"):
                v = "gpt-3.5-turbo"
            else:
                v = values["llm_model"]
        return v

    @validator("openai_organization")
    def set_openai_organization(cls, v):
        if v:
            import openai

            openai.organization = v
        return v

    @validator("openai_api_key")
    def warn_if_missing_api_keys(cls, v, field):
        if not v:
            print(
                Text(
                    f"WARNING: `{field.name}` is not set. Some features may not work.",
                    style="red",
                )
            )
        return v

    @root_validator
    def test_mode_settings(cls, values):
        if values["test_mode"]:
            values["log_level"] = "DEBUG"
            values["verbose"] = True
            # don't generate profile pictures
            values["bot_create_profile_picture"] = False
            # don't load default plugins
            values["bot_load_default_plugins"] = False
            # remove all model variance
            values["llm_temperature"] = 0.0
            # use 3.5 by default
            values["llm_model"] = "gpt-3.5-turbo"
            values["llm_backend"] = LLMBackend.OpenAIChat
            # don't check migration version
            values["database_check_migration_version_on_startup"] = False

        return values

    def __setattr__(self, name, value):
        result = super().__setattr__(name, value)
        # update log level on assignment
        if name == "log_level":
            marvin.utilities.logging.setup_logging()
        return result


settings = Settings()


@contextmanager
def temporary_settings(**kwargs):
    old_settings = settings.dict()
    settings.__dict__.update(kwargs)
    try:
        yield
    finally:
        settings.__dict__.clear()
        settings.__dict__.update(old_settings)
