"""Fail CI when tracked files contain high-confidence credential signatures."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

SIGNATURES = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "OpenAI-style API key": re.compile(rb"\bsk-[A-Za-z0-9_-]{24,}\b"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key": re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
}


def tracked_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
    )
    return [ROOT / raw.decode("utf-8") for raw in output.split(b"\0") if raw]


def main() -> None:
    findings: list[str] = []
    for path in tracked_files():
        if path == SELF or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        for label, signature in SIGNATURES.items():
            if signature.search(data):
                findings.append(f"{path.relative_to(ROOT)}: possible {label}")

    history = subprocess.check_output(
        [
            "git",
            "log",
            "--all",
            "--format=",
            "--patch",
            "--no-ext-diff",
            "--",
            ".",
            ":(exclude)scripts/check_secrets.py",
        ],
        cwd=ROOT,
    )
    for label, signature in SIGNATURES.items():
        if signature.search(history):
            findings.append(f"Git history: possible {label}")

    if findings:
        print("Potential credentials found in the repository or history:")
        for finding in findings:
            print(f"- {finding}")
        raise SystemExit(1)
    print(
        "No high-confidence credential signatures found in the repository or history."
    )


if __name__ == "__main__":
    main()
