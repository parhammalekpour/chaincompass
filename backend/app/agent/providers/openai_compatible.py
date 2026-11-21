from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.agent.providers.base import (
    ChatMessage,
    ProviderError,
    ProviderResponse,
    ProviderUsage,
    ToolCall,
)

MAX_PROVIDER_TIMEOUT = 60.0


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url or not api_key or not model:
            raise ValueError("LLM provider configuration is incomplete")
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        tools: Sequence[Mapping[str, object]],
        *,
        timeout: float,
    ) -> ProviderResponse:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": list(messages),
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        request_timeout = min(timeout, MAX_PROVIDER_TIMEOUT)
        for attempt in range(2):
            try:
                response = await self._client.post(
                    self._url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=request_timeout,
                )
            except httpx.TimeoutException:
                if attempt == 0:
                    continue
                raise ProviderError("provider_timeout") from None
            except httpx.HTTPError:
                raise ProviderError("provider_unavailable") from None

            if response.status_code >= 500 and attempt == 0:
                continue
            if not 200 <= response.status_code < 300:
                raise ProviderError("provider_rejected_request")
            return _parse_response(response)
        raise ProviderError("provider_unavailable")


def _parse_response(response: httpx.Response) -> ProviderResponse:
    try:
        payload: Any = response.json()
        choice = payload["choices"][0]
        message = choice["message"]
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise TypeError
        raw_calls = message.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            raise TypeError
        tool_calls: list[ToolCall] = []
        for raw in raw_calls:
            function = raw["function"]
            arguments = function["arguments"]
            if not isinstance(arguments, (str, dict)):
                raise TypeError
            tool_calls.append(
                ToolCall(
                    id=str(raw["id"]),
                    name=str(function["name"]),
                    arguments=arguments,
                )
            )
        raw_usage = payload.get("usage")
        usage = (
            ProviderUsage(
                prompt_tokens=_optional_int(raw_usage.get("prompt_tokens")),
                completion_tokens=_optional_int(raw_usage.get("completion_tokens")),
            )
            if isinstance(raw_usage, dict)
            else None
        )
        finish_reason = choice.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise TypeError
    except (IndexError, KeyError, TypeError, ValueError):
        raise ProviderError("provider_invalid_response") from None
    return ProviderResponse(
        content=content,
        tool_calls=tuple(tool_calls),
        usage=usage,
        finish_reason=finish_reason,
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError
    return value
