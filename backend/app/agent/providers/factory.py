from app.agent.providers.base import LLMProvider
from app.agent.providers.fake import FakeProvider
from app.agent.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import settings


def create_configured_provider() -> LLMProvider | None:
    if settings.llm_provider == "none":
        return None
    if settings.llm_provider == "fake":
        return FakeProvider(())
    if (
        not settings.llm_base_url
        or not settings.llm_api_key
        or settings.llm_api_key.lower().startswith("placeholder_")
        or not settings.llm_model
    ):
        return None
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )
