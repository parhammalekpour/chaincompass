"""Verify answer numbers against this turn's tool results.

Persian and Arabic-Indic digits are normalized first. ISO dates, list ordinals,
``/100``, day-window labels (30, 90, 365, 1095), and percentile labels (p10,
p50, p90) are structural and ignored. Every other numeric token must equal a
tool number or equal that number rounded half-up to the answer's displayed
decimal places. A token followed by a percent marker may also match a tool
number multiplied by 100. Values stay Decimal; floats are not used here.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_NUMBER = re.compile(
    r"(?<![\w])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w])"
)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_ORDINAL = re.compile(r"(?m)^\s*\d{1,2}[.)]\s+")
_PERCENTILE = re.compile(r"(?i)\bp(?:10|50|90)\b")
_WINDOW = re.compile(r"(?i)(?<!\w)(?:30|90|365|1095)[ -]days?\b")
_SLASH_HUNDRED = re.compile(r"/100\b")


@dataclass(frozen=True)
class UngroundedNumber:
    value: str
    start: int
    end: int


def normalize_digits(value: str) -> str:
    return (
        value.translate(_DIGIT_TRANSLATION)
        .replace("\u066b", ".")
        .replace("\u066c", ",")
    )


def _without_structural_numbers(value: str) -> str:
    normalized = normalize_digits(value)
    for pattern in (
        _ISO_DATE,
        _ORDINAL,
        _PERCENTILE,
        _WINDOW,
        _SLASH_HUNDRED,
    ):
        normalized = pattern.sub(lambda match: " " * len(match.group()), normalized)
    return normalized


def _source_numbers(value: object) -> list[Decimal]:
    found: list[Decimal] = []
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, Decimal):
        if value.is_finite():
            return [value]
        return found
    if isinstance(value, int):
        return [Decimal(value)]
    if isinstance(value, float):
        if value == value and abs(value) != float("inf"):
            return [Decimal(str(value))]
        return found
    if isinstance(value, str):
        candidates = _NUMBER.finditer(_without_structural_numbers(value))
        for candidate in candidates:
            try:
                number = Decimal(candidate.group().replace(",", ""))
            except InvalidOperation:
                continue
            if number.is_finite():
                found.append(number)
        return found
    if isinstance(value, Mapping):
        for nested in value.values():
            found.extend(_source_numbers(nested))
        return found
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for nested in value:
            found.extend(_source_numbers(nested))
    return found


def _matches_source(
    answer_number: Decimal,
    decimal_places: int,
    is_percentage: bool,
    source_numbers: Sequence[Decimal],
) -> bool:
    quantum = Decimal(1).scaleb(-decimal_places)
    for source in source_numbers:
        candidates = (source, source * Decimal(100)) if is_percentage else (source,)
        for candidate in candidates:
            if answer_number == candidate or answer_number == candidate.quantize(
                quantum,
                rounding=ROUND_HALF_UP,
            ):
                return True
    return False


def find_ungrounded_numbers(
    answer: str,
    tool_results: Sequence[object],
) -> list[UngroundedNumber]:
    normalized = normalize_digits(answer)
    searchable = _without_structural_numbers(normalized)
    source_numbers = [
        number for result in tool_results for number in _source_numbers(result)
    ]
    findings: list[UngroundedNumber] = []
    for match in _NUMBER.finditer(searchable):
        token = match.group().replace(",", "")
        try:
            answer_number = Decimal(token)
        except InvalidOperation:
            continue
        suffix = normalized[match.end() : match.end() + 16]
        is_percentage = bool(
            re.match(r"\s*(?:%|٪|percent\b|درصد)", suffix, flags=re.IGNORECASE)
        )
        decimal_places = len(token.partition(".")[2])
        if not _matches_source(
            answer_number,
            decimal_places,
            is_percentage,
            source_numbers,
        ):
            findings.append(
                UngroundedNumber(
                    value=match.group(), start=match.start(), end=match.end()
                )
            )
    return findings
