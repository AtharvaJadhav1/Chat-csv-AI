from typing import Any


def fmt_num(value: Any, digits: int = 2) -> str:
    """Human friendly number: integers without decimals, floats rounded."""
    if value is None:
        return "n/a"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f) and abs(f) < 1e15:
        return f"{int(f):,}" if abs(f) >= 10_000 else str(int(f))
    return f"{f:,.{digits}f}" if abs(f) >= 10_000 else f"{f:.{digits}f}"


def humanize(name: str) -> str:
    return name.replace("_", " ").strip()


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)
