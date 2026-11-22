"""Verify answer numbers against this turn's tool results.

Persian and Arabic-Indic digits are normalized first. ISO dates, matching
prose dates, list ordinals, ``/100``, day-window labels (30, 90, 365, 1095),
and percentile labels (p10, p50, p90) are structural and ignored. Every other
numeric token must equal a tool number or equal that number rounded half-up to
the answer's displayed decimal places. A token followed by a percent marker
may also match a tool number multiplied by 100. Values stay Decimal; floats
are not used here.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
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
_MONTH_NUMBERS = {
    name.casefold(): month
    for month, names in (
        (1, ("January", "Jan", "ژانویه")),
        (2, ("February", "Feb", "فوریه")),
        (3, ("March", "Mar", "مارس")),
        (4, ("April", "Apr", "آوریل", "اپریل", "آپریل")),
        (5, ("May", "می", "مه")),
        (6, ("June", "Jun", "ژوئن", "ژون")),
        (7, ("July", "Jul", "ژوئیه", "جولای", "ژولای")),
        (8, ("August", "Aug", "اوت", "آگوست", "آگست")),
        (9, ("September", "Sep", "Sept", "سپتامبر", "سپتمبر")),
        (10, ("October", "Oct", "اکتبر")),
        (11, ("November", "Nov", "نوامبر")),
        (12, ("December", "Dec", "دسامبر")),
    )
    for name in names
}
_MONTH_PATTERN = (
    "(?:"
    + "|".join(
        re.escape(name) for name in sorted(_MONTH_NUMBERS, key=len, reverse=True)
    )
    + ")"
)
_PROSE_DATE_PATTERNS = (
    re.compile(
        rf"(?<!\w)(?P<month>{_MONTH_PATTERN})[ \t]+(?P<day>\d{{1,2}})"
        r"(?:[ \t]*[,،][ \t]*|[ \t]+)(?P<year>\d{4})(?!\w)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?<!\w)(?P<day>\d{{1,2}})[ \t]+(?P<month>{_MONTH_PATTERN})"
        r"[ \t]+(?P<year>\d{4})(?!\w)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?<!\w)(?P<month>{_MONTH_PATTERN})[ \t]+(?P<year>\d{{4}})(?!\w)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?<!\w)(?P<month>{_MONTH_PATTERN})[ \t]+(?P<day>\d{{1,2}})"
        r"(?!\w)(?!(?:[ \t]*[,،][ \t]*|[ \t]+)\d)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?<!\w)(?P<day>\d{{1,2}})[ \t]+(?P<month>{_MONTH_PATTERN})"
        r"(?!\w)(?!(?:[ \t]*[,،][ \t]*|[ \t]+)\d)",
        re.IGNORECASE,
    ),
)


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


def _source_dates(value: object) -> set[date]:
    found: set[date] = set()
    if isinstance(value, str):
        normalized = normalize_digits(value)
        for match in _ISO_DATE.finditer(normalized):
            try:
                found.add(date.fromisoformat(match.group()))
            except ValueError:
                continue
        return found
    if isinstance(value, Mapping):
        for nested in value.values():
            found.update(_source_dates(nested))
        return found
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for nested in value:
            found.update(_source_dates(nested))
    return found


def _prose_date_matches(
    match: re.Match[str],
    source_dates: set[date],
) -> bool:
    month = _MONTH_NUMBERS[match.group("month").casefold()]
    day_text = match.groupdict().get("day")
    year_text = match.groupdict().get("year")
    if day_text is not None and year_text is not None:
        try:
            candidate = date(int(year_text), month, int(day_text))
        except ValueError:
            return False
        return candidate in source_dates
    if day_text is not None:
        day = int(day_text)
        return any(item.month == month and item.day == day for item in source_dates)
    if year_text is not None:
        year = int(year_text)
        return any(item.year == year and item.month == month for item in source_dates)
    return False


def _matching_prose_date_spans(
    answer: str,
    source_dates: set[date],
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in _PROSE_DATE_PATTERNS:
        for match in pattern.finditer(answer):
            if any(match.start() < end and start < match.end() for start, end in spans):
                continue
            if _prose_date_matches(match, source_dates):
                spans.append((match.start(), match.end()))
    return spans


def _mask_spans(value: str, spans: Sequence[tuple[int, int]]) -> str:
    characters = list(value)
    for start, end in spans:
        for index in range(start, end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


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
    source_dates = {day for result in tool_results for day in _source_dates(result)}
    searchable = _mask_spans(
        searchable,
        _matching_prose_date_spans(normalized, source_dates),
    )
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
