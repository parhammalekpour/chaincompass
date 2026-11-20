from datetime import UTC, datetime

import httpx
import pytest

from app.ingestion.rpc import RpcEndpoints, RpcProbeClient


@pytest.mark.asyncio
async def test_rpc_probe_parses_all_chain_responses() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    block_timestamp = int(now.timestamp()) - 17

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="900001", request=request)
        payload = request.read()
        import json

        body = json.loads(payload)
        method = body["method"]
        if method == "eth_getBlockByNumber":
            result = {
                "number": "0x1234",
                "timestamp": hex(block_timestamp),
            }
        elif method == "getSlot":
            result = 7654321
        elif method == "getBlockTime":
            result = block_timestamp
        else:
            return httpx.Response(400, request=request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    endpoints = RpcEndpoints(
        btc_tip="http://test/btc",
        eth="http://test/eth",
        sol="http://test/sol",
        bnb="http://test/bnb",
    )
    client = RpcProbeClient(
        endpoints=endpoints,
        transport=httpx.MockTransport(handler),
        now=lambda: now,
    )
    try:
        results = [await client.probe(chain) for chain in ("btc", "eth", "sol", "bnb")]
    finally:
        await client.close()

    assert [(row.chain_id, row.ok) for row in results] == [
        ("btc", True),
        ("eth", True),
        ("sol", True),
        ("bnb", True),
    ]
    assert results[0].block_height == 900001
    assert results[1].block_height == results[3].block_height == 0x1234
    assert results[2].block_height == 7654321
    assert results[1].block_age_seconds == results[2].block_age_seconds == 17


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error_code"),
    [(429, "http_429"), (503, "http_503")],
)
async def test_rpc_probe_reports_http_errors_without_exposing_response(
    status_code: int,
    error_code: str,
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="sensitive response", request=request)

    client = RpcProbeClient(
        endpoints=RpcEndpoints(
            "http://test/btc", "http://test/eth", "http://test/sol", "http://test/bnb"
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.probe("eth")
    finally:
        await client.close()
    assert not result.ok
    assert result.error_code == error_code


@pytest.mark.asyncio
async def test_rpc_probe_marks_invalid_payload_and_timeout() -> None:
    async def invalid_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "error": {"message": "secret"}},
            request=request,
        )

    client = RpcProbeClient(
        endpoints=RpcEndpoints(
            "http://test/btc", "http://test/eth", "http://test/sol", "http://test/bnb"
        ),
        transport=httpx.MockTransport(invalid_handler),
    )
    try:
        invalid = await client.probe("eth")
    finally:
        await client.close()
    assert invalid.error_code == "rpc_error"

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    client = RpcProbeClient(
        endpoints=RpcEndpoints(
            "http://test/btc", "http://test/eth", "http://test/sol", "http://test/bnb"
        ),
        transport=httpx.MockTransport(timeout_handler),
    )
    try:
        timeout = await client.probe("eth")
    finally:
        await client.close()
    assert not timeout.ok
    assert timeout.error_code == "timeout"


@pytest.mark.asyncio
async def test_rpc_probe_clamps_age_and_keeps_slot_on_block_time_error() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    async def skew_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"number": "0x1", "timestamp": hex(int(now.timestamp()) + 5)},
            },
            request=request,
        )

    client = RpcProbeClient(
        endpoints=RpcEndpoints(
            "http://test/btc", "http://test/eth", "http://test/sol", "http://test/bnb"
        ),
        transport=httpx.MockTransport(skew_handler),
        now=lambda: now,
    )
    try:
        skew = await client.probe("eth")
    finally:
        await client.close()
    assert skew.ok
    assert skew.block_age_seconds == 0
    assert skew.error_code == "clock_skew_clamped"

    async def sol_handler(request: httpx.Request) -> httpx.Response:
        import json

        method = json.loads(request.read())["method"]
        if method == "getSlot":
            result = 100
        else:
            return httpx.Response(429, request=request)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    client = RpcProbeClient(
        endpoints=RpcEndpoints(
            "http://test/btc", "http://test/eth", "http://test/sol", "http://test/bnb"
        ),
        transport=httpx.MockTransport(sol_handler),
        now=lambda: now,
    )
    try:
        sol = await client.probe("sol")
    finally:
        await client.close()
    assert sol.ok
    assert sol.block_height == 100
    assert sol.block_age_seconds is None
    assert sol.error_code == "block_time_unavailable"
