"""Validators for Mercy rewrites. Their pass rate is a reported eval metric."""
import ast

from app.analyzers.resume_parser import check_bullet


def validate_code(source: str) -> tuple[bool, str]:
    try:
        ast.parse(source)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError line {e.lineno}: {e.msg}"


def validate_bullet(text: str) -> tuple[bool, str]:
    issues = [i for i in check_bullet(text) if i[0] in {"weak_verb", "too_long", "too_short"}]
    return (not issues), "; ".join(i[3] for i in issues)
