"""First line of defence: reject anything that looks like code / injection before it is parsed.

The plan itself can never execute anything (it is plain data), but we still refuse
payloads that try to smuggle code, shell commands, SQL or network access through it.
"""
import re
from typing import Any

from ..schemas.plan import PLAN_FIELDS


class PlanSecurityError(Exception):
    """Raised when a plan or question contains a blocked construct."""


FORBIDDEN_KEYS = {
    "code", "python", "script", "exec", "eval", "command", "cmd", "shell", "sql", "query",
    "import", "expression", "lambda", "function", "payload", "url", "path", "file",
}

BLOCKED_PATTERNS = [
    (re.compile(r"__\w+__"), "dunder access"),
    (re.compile(r"\b(exec|eval|compile|open|getattr|setattr|globals|locals|breakpoint|input)\s*\(", re.I), "code execution"),
    (re.compile(r"\bimport\s+(os|sys|subprocess|socket|shutil|pathlib|requests|urllib|builtins|ctypes|importlib)\b", re.I), "import statement"),
    (re.compile(r"\b(os|sys|subprocess|shutil|socket|pathlib)\s*\.\s*\w+", re.I), "system module access"),
    (re.compile(r"\b(rm\s+-rf|chmod|wget|curl|powershell|cmd\.exe|/bin/(ba)?sh)\b", re.I), "shell command"),
    (re.compile(r";\s*(drop|delete|insert|update|alter|truncate)\b", re.I), "SQL statement"),
    (re.compile(r"\b(union\s+select|drop\s+table|insert\s+into|delete\s+from)\b", re.I), "SQL statement"),
    (re.compile(r"\b(read_csv|to_csv|read_sql|read_pickle|to_pickle|read_html)\b", re.I), "filesystem access"),
    (re.compile(r"https?://", re.I), "network access"),
    (re.compile(r"`|\$\("), "shell substitution"),
]

MAX_STRING_LENGTH = 1000
MAX_DEPTH = 6


def find_violation(text: str) -> str | None:
    if len(text) > MAX_STRING_LENGTH:
        return "oversized value"
    for pattern, label in BLOCKED_PATTERNS:
        if pattern.search(text):
            return label
    return None


def guard_question(question: str) -> None:
    violation = find_violation(question)
    if violation:
        raise PlanSecurityError(
            f"Your question was blocked because it contains a disallowed construct ({violation}). "
            "ChatCSV AI only runs predefined, safe analysis operations on your dataset."
        )


def guard_raw_plan(raw: Any, depth: int = 0, top_level: bool = True) -> None:
    """Walk the raw (untrusted) plan dict and reject blocked keys / values."""
    if depth > MAX_DEPTH:
        raise PlanSecurityError("The AI plan is nested too deeply and was rejected.")
    if isinstance(raw, dict):
        for key, value in raw.items():
            lowered = str(key).strip().lower()
            if lowered in FORBIDDEN_KEYS and lowered not in PLAN_FIELDS:
                raise PlanSecurityError(f"The AI plan contained a forbidden field '{key}' and was rejected.")
            guard_raw_plan(value, depth + 1, False)
    elif isinstance(raw, list):
        if len(raw) > 500:
            raise PlanSecurityError("The AI plan contained an oversized list and was rejected.")
        for item in raw:
            guard_raw_plan(item, depth + 1, False)
    elif isinstance(raw, str):
        violation = find_violation(raw)
        if violation:
            raise PlanSecurityError(f"The AI plan was rejected for safety reasons ({violation}).")
