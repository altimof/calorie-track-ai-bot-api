import uuid


def parse_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a UUID string, or return None if it is not one.

    uuid.UUID accepts forms Postgres rejects (e.g. 'urn:uuid:...'), so pass the
    parsed value (or str() of it, which is canonical) to SQL, not the raw string.
    """
    try:
        return uuid.UUID(value)  # type: ignore[arg-type]
    except (ValueError, TypeError, AttributeError):
        return None
