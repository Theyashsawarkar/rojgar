"""Small cross-platform terminal styling helpers.

colorama translates ANSI codes into the Win32 console calls legacy
`cmd.exe` needs (modern Windows Terminal/PowerShell already understand
ANSI natively -- colorama.init() is a harmless no-op there); everywhere
else, these are just plain ANSI escapes. Styling turns itself off
automatically when stdout isn't a real terminal (piped/redirected
output shouldn't be full of escape codes) or when NO_COLOR is set, per
the https://no-color.org convention.
"""
from __future__ import annotations

import os
import sys

import colorama

colorama.init()

ENABLED = sys.stdout.isatty() and "NO_COLOR" not in os.environ

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "magenta": "\033[35m",
}


def _style(text: str, *codes: str) -> str:
    if not ENABLED:
        return text
    prefix = "".join(_CODES[c] for c in codes)
    return f"{prefix}{text}{_CODES['reset']}"


def success(text: str) -> str:
    return _style(text, "green", "bold")


def warn(text: str) -> str:
    return _style(text, "yellow")


def error(text: str) -> str:
    return _style(text, "red", "bold")


def info(text: str) -> str:
    return _style(text, "cyan")


def dim(text: str) -> str:
    return _style(text, "dim")


def bold(text: str) -> str:
    return _style(text, "bold")


def heading(text: str) -> str:
    return _style(text, "magenta", "bold")


_BANNER = (
    "========================================\n"
    "  R O J G A R  -  Job Search Scraper\n"
    "========================================"
)


def print_banner() -> None:
    print(_style(_BANNER, "cyan", "bold"))
