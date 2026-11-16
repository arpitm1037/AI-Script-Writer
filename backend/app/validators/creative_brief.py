"""Semantic validation and normalization for creative-brief payloads."""

from fastapi import HTTPException, status

# Allowed enum values
GENRES = {"Horror", "Comedy", "Drama"}
OUTPUT_FORMATS = {"YouTube / Long-form", "Short Film / Screenplay", "Advertisement"}
DETAIL_LEVELS = {"Concise", "Standard", "Detailed"}

# Fields that must be present and non-empty when creating a brief.
REQUIRED_ON_CREATE = [
    "genre",
    "output_format",
    "language",
    "tone",
    "target_audience",
    "duration",
    "characters",
    "setting",
    "key_points",
    "detail_level",
]

# Reasonable maximum lengths for free-text fields.
MAX_LENGTHS = {
    "topic": 2000,
    "genre": 50,
    "output_format": 60,
    "language": 60,
    "tone": 200,
    "target_audience": 200,
    "duration": 100,
    "characters": 2000,
    "setting": 1000,
    "key_points": 2000,
    "detail_level": 30,
    "special_instructions": 5000,
}


def _error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=message
    )


def _require_text(data: dict, field: str, label: str) -> None:
    """Require the field to exist and not be empty or only whitespace."""
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise _error(f"{label} is required and cannot be empty.")
    data[field] = value.strip()


def _check_enum(data: dict, field: str, allowed: set[str], label: str) -> None:
    value = data.get(field)
    if value not in allowed:
        raise _error(
            f"{label} must be one of: {', '.join(sorted(allowed))}."
        )


def _check_length(data: dict, field: str) -> None:
    value = data.get(field)
    limit = MAX_LENGTHS.get(field)
    if isinstance(value, str) and limit and len(value) > limit:
        raise _error(f"{field.replace('_', ' ').title()} is too long (max {limit} characters).")


def validate_create(data: dict) -> dict:
    """Validate a create payload. Returns cleaned, whitespace-trimmed data."""
    payload = dict(data)

    _require_text(payload, "topic", "Topic")
    _check_length(payload, "topic")

    for field in REQUIRED_ON_CREATE:
        _require_text(payload, field, field.replace("_", " ").title())
        _check_length(payload, field)

    _check_enum(payload, "genre", GENRES, "Genre")
    _check_enum(payload, "output_format", OUTPUT_FORMATS, "Output format")
    _check_enum(payload, "detail_level", DETAIL_LEVELS, "Detail level")

    if payload.get("special_instructions"):
        payload["special_instructions"] = payload["special_instructions"].strip()
        _check_length(payload, "special_instructions")

    return payload


def validate_update(data: dict) -> dict:
    """Validate an update payload (only provided fields). Returns cleaned data."""
    payload = {}

    for field, value in data.items():
        if value is None:
            continue

        if not isinstance(value, str) or not value.strip():
            raise _error(
                f"{field.replace('_', ' ').title()} cannot be empty."
            )

        payload[field] = value.strip()
        _check_length(payload, field)

    if "genre" in payload:
        _check_enum(payload, "genre", GENRES, "Genre")
    if "output_format" in payload:
        _check_enum(payload, "output_format", OUTPUT_FORMATS, "Output format")
    if "detail_level" in payload:
        _check_enum(payload, "detail_level", DETAIL_LEVELS, "Detail level")

    return payload