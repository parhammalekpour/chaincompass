import pytest

from app.agent.grounding import find_ungrounded_numbers
from app.agent.guardrails import check_output

TOOL_RESULTS = [
    {"as_of": "2026-11-19", "score": "34.70"},
    {"as_of": "2026-11-19", "score": "41.57"},
]


@pytest.mark.parametrize(
    ("text", "rejected_tokens"),
    [
        pytest.param(
            "As of November 19, 2026, ETH fell 19%.",
            ("19",),
            id="case-9",
        ),
        pytest.param(
            "In November 2026, ETH scored 34.70.",
            (),
            id="case-10",
        ),
        pytest.param(
            "As of November 19, 2025, ETH scores 34.70.",
            ("19", "2025"),
            id="case-11",
        ),
        pytest.param(
            "As of 31 February 2026, ETH scores 34.70.",
            ("31", "2026"),
            id="case-12",
        ),
        pytest.param(
            "As of 19 November, ETH scores 34.70.",
            (),
            id="case-13",
        ),
        pytest.param(
            "در 19 فروردین، امتیاز ETH برابر با 34.70 است.",
            ("19",),
            id="case-14",
        ),
        pytest.param(
            "As of November 19, ETH has 2026 flags.",
            ("2026",),
            id="case-15",
        ),
    ],
)
def test_grounding_prose_date_edge_cases(
    text: str,
    rejected_tokens: tuple[str, ...],
) -> None:
    result = check_output(text, TOOL_RESULTS)

    assert tuple(number.value for number in result.ungrounded_numbers) == (
        rejected_tokens
    )
    assert result.passed is (not rejected_tokens)


def test_grounding_only_masks_the_matching_date_span() -> None:
    text = "As of November 19, 2026, ETH fell 19%."

    findings = find_ungrounded_numbers(text, TOOL_RESULTS)

    assert len(findings) == 1
    finding = findings[0]
    assert text[finding.start : finding.end] == "19"
    assert text[finding.end : finding.end + 1] == "%"


def test_grounding_recognizes_english_gregorian_month_names() -> None:
    aliases = (
        ("January", "Jan", 1),
        ("February", "Feb", 2),
        ("March", "Mar", 3),
        ("April", "Apr", 4),
        ("May", 5),
        ("June", "Jun", 6),
        ("July", "Jul", 7),
        ("August", "Aug", 8),
        ("September", "Sep", "Sept", 9),
        ("October", "Oct", 10),
        ("November", "Nov", 11),
        ("December", "Dec", 12),
    )
    for entry in aliases:
        month = entry[-1]
        for name in entry[:-1]:
            tool_results = [{"as_of": f"2026-{month:02d}-19", "score": "34.70"}]
            for answer in (
                f"As of {name} 19, 2026, ETH scores 34.70.",
                f"As of 19 {name} 2026, ETH scores 34.70.",
                f"As of {name} 19, ETH scores 34.70.",
                f"As of 19 {name}, ETH scores 34.70.",
                f"As of {name} 2026, ETH scores 34.70.",
            ):
                assert find_ungrounded_numbers(answer, tool_results) == [], name


def test_grounding_recognizes_persian_gregorian_month_names_and_variants() -> None:
    aliases = (
        ("ژانویه", 1),
        ("فوریه", 2),
        ("مارس", 3),
        ("آوریل", "اپریل", "آپریل", 4),
        ("می", "مه", 5),
        ("ژوئن", "ژون", 6),
        ("ژوئیه", "جولای", "ژولای", 7),
        ("اوت", "آگوست", "آگست", 8),
        ("سپتامبر", "سپتمبر", 9),
        ("اکتبر", 10),
        ("نوامبر", 11),
        ("دسامبر", 12),
    )
    for entry in aliases:
        month = entry[-1]
        for name in entry[:-1]:
            tool_results = [{"as_of": f"2026-{month:02d}-19", "score": "34.70"}]
            for answer in (
                f"در {name} 19، امتیاز ETH برابر با 34.70 است.",
                f"در {name} 19، 2026 امتیاز ETH برابر با 34.70 است.",
                f"در 19 {name} 2026، امتیاز ETH برابر با 34.70 است.",
                f"در 19 {name}، امتیاز ETH برابر با 34.70 است.",
                f"در {name} 2026، امتیاز ETH برابر با 34.70 است.",
            ):
                assert find_ungrounded_numbers(answer, tool_results) == [], name


def test_grounding_does_not_recognize_solar_hijri_month_names() -> None:
    months = (
        "فروردین",
        "اردیبهشت",
        "خرداد",
        "تیر",
        "مرداد",
        "شهریور",
        "مهر",
        "آبان",
        "آذر",
        "دی",
        "بهمن",
        "اسفند",
    )
    for month in months:
        answer = f"در 19 {month}، امتیاز ETH برابر با 34.70 است."
        findings = find_ungrounded_numbers(answer, TOOL_RESULTS)
        assert [finding.value for finding in findings] == ["19"], month
