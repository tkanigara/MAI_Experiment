from __future__ import annotations


def require_fields(payload: dict, fields: list[str]) -> None:
    missing = [field for field in fields if not str(payload.get(field) or "").strip()]
    if missing:
        raise ValueError(f"{' and '.join(missing)} are required")
