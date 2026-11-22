"""Post-12A5 characterization of current behavior, not desired behavior."""

import pytest

from app.agent.guardrails import check_output

TOOL_RESULTS = [
    {"as_of": "2026-11-19", "score": "34.70"},
    {"as_of": "2026-11-19", "score": "41.57"},
]


@pytest.mark.parametrize(
    ("text", "rejected_tokens"),
    [
        pytest.param(
            "As of 2026-11-19, ETH scores 34.70.",
            (),
            id="case-1",
        ),
        pytest.param(
            "As of November 19, ETH scores 34.70.",
            (),
            id="case-2",
        ),
        pytest.param(
            "As of 19 November 2026, ETH scores 34.70.",
            (),
            id="case-3",
        ),
        pytest.param(
            "As of Nov 19, 2026, ETH scores 34.70.",
            (),
            id="case-4",
        ),
        pytest.param(
            "از 19 نوامبر، امتیاز ETH برابر با 34.70 است.",
            (),
            id="case-5",
        ),
        pytest.param(
            "As of November 20, ETH scores 34.70.",
            ("20",),
            id="case-6",
        ),
        pytest.param(
            "ETH has 19 flags.",
            ("19",),
            id="case-7",
        ),
        pytest.param(
            "ETH fell 19% in 90 days.",
            ("19",),
            id="case-8",
        ),
    ],
)
def test_grounding_date_characterization(
    text: str,
    rejected_tokens: tuple[str, ...],
) -> None:
    result = check_output(text, TOOL_RESULTS)

    assert tuple(number.value for number in result.ungrounded_numbers) == (
        rejected_tokens
    )
    assert result.passed is (not rejected_tokens)
