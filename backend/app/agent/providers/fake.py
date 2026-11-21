from collections import deque
from collections.abc import Mapping, Sequence
from copy import deepcopy

from app.agent.providers.base import (
    ChatMessage,
    LLMProvider,
    ProviderError,
    ProviderResponse,
)


class FakeProvider:
    def __init__(self, responses: Sequence[ProviderResponse]) -> None:
        self._responses = deque(responses)
        self.requests: list[tuple[list[ChatMessage], list[dict[str, object]]]] = []

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[Mapping[str, object]],
        *,
        timeout: float,
    ) -> ProviderResponse:
        del timeout
        self.requests.append(
            (
                deepcopy(list(messages)),
                [deepcopy(dict(tool)) for tool in tools],
            )
        )
        if not self._responses:
            raise ProviderError("fake_provider_exhausted")
        return self._responses.popleft()


def create_fake_provider() -> LLMProvider:
    return FakeProvider(())
