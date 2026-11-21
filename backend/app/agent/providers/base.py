from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

JsonObject = dict[str, object]
ChatMessage = dict[str, object]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str | JsonObject


@dataclass(frozen=True)
class ProviderUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True)
class ProviderResponse:
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: ProviderUsage | None = None
    finish_reason: str | None = None


class ProviderError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LLMProvider(Protocol):
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[Mapping[str, object]],
        *,
        timeout: float,
    ) -> ProviderResponse: ...
