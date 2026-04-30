#!/usr/bin/env python3
"""Scan Git candidate files for secrets, personal information, and internal identifiers.

Scope intentionally follows Git, not the raw filesystem:
    git ls-files --cached --others --exclude-standard

This means ignored local folders such as .config/, data/, report/, .venv/ are not scanned
or reported by default. Findings are redacted and the script never prints full secret-like
values.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MAX_FILE_BYTES = 2_000_000
TEXT_SUFFIXES = {
    "",
    ".bash",
    ".cfg",
    ".conf",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
BINARY_SUFFIXES = {
    ".7z",
    ".avif",
    ".bin",
    ".bmp",
    ".class",
    ".dmg",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".tar",
    ".webp",
    ".zip",
}
PLACEHOLDER_RE = re.compile(r"^(|<[^>]+>|\$\{?[A-Z0-9_]+\}?|\*+|x+|X+|example|changeme|placeholder|null|none|true|false)$", re.I)
SENSITIVE_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|bearer|authorization|cookie|password|passwd|pwd|client[_-]?secret|app[_-]?secret|private[_-]?key|node[_-]?token|doc[_-]?token|root[_-]?node[_-]?token|space[_-]?id)"
)
FINANCIAL_NUMBER_CONTEXT_RE = re.compile(
    r"(?i)(turnover|volume|amount|market_cap|marketcap|cashflow|revenue|profit|ebitda|shares|float|成交|成交额|成交量|市值|营收|利润)"
)
CONTACT_CONTEXT_RE = re.compile(r"(?i)(phone|mobile|tel|telephone|contact|手机号|手机|电话|联系方式)")


@dataclass(frozen=True)
class Finding:
    severity: str
    kind: str
    path: str
    line: int
    detail: str


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {ch: value.count(ch) for ch in set(value)}
    return -sum((count / len(value)) * math.log2(count / len(value)) for count in counts.values())


def redact(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:3]}…{value[-3:]} len={len(value)}"


def git_candidate_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        text=True,
    )
    return [line for line in output.splitlines() if line]


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    return b"\0" not in sample


def read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES or not is_probably_text(path):
            return None
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    except OSError:
        return None


def inspect_filename(path: str) -> Iterable[Finding]:
    name = os.path.basename(path).lower()
    risky_exact = {".env", ".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json"}
    risky_suffixes = (".pem", ".p12", ".pfx", ".key")
    if name in risky_exact or name.endswith(risky_suffixes):
        yield Finding("HIGH", "risky_filename", path, 0, f"risky committed filename: {name}")
    if ".config/" in f"/{path}" or path.startswith(".config/"):
        yield Finding("HIGH", "ignored_local_config_committed", path, 0, "local .config file is in Git candidate scope")


def inspect_line(path: str, line_no: int, line: str) -> Iterable[Finding]:
    stripped = line.strip()

    literal_patterns = [
        ("HIGH", "private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        ("HIGH", "aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
        ("HIGH", "github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
        ("HIGH", "openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
        ("HIGH", "slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
        ("HIGH", "jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
        ("HIGH", "authorization_header", re.compile(r"(?i)authorization\s*[:=]\s*[\"']?bearer\s+[A-Za-z0-9._~+/-]{12,}")),
        ("HIGH", "cookie_assignment", re.compile(r"(?i)cookie\s*[:=]\s*[\"']?[^\"'\s]{16,}")),
        ("MEDIUM", "local_absolute_path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")),
        ("MEDIUM", "internal_doc_url", re.compile(r"https?://[^\s\"'<>]*(?:feishu\.cn|larksuite\.com|confluence\.|jira\.)[^\s\"'<>]*", re.I)),
        ("MEDIUM", "email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
        ("MEDIUM", "cn_id_card_like", re.compile(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)")),
    ]
    for severity, kind, pattern in literal_patterns:
        match = pattern.search(line)
        if match:
            yield Finding(severity, kind, path, line_no, f"matched {kind}: {redact(match.group(0))}")

    phone_match = re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", line)
    if phone_match and CONTACT_CONTEXT_RE.search(line) and not FINANCIAL_NUMBER_CONTEXT_RE.search(line):
        yield Finding("MEDIUM", "cn_mobile_like", path, line_no, f"mobile-like number near contact keyword: {redact(phone_match.group(0))}")

    if SENSITIVE_KEY_RE.search(line):
        assignment = re.search(r"(?i)([A-Za-z0-9_.-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|authorization|cookie|password|passwd|pwd|client[_-]?secret|app[_-]?secret|private[_-]?key)[A-Za-z0-9_.-]*)\s*[:=]\s*[\"']?([^\"'\s,}]+)", line)
        if assignment:
            value = assignment.group(2).strip()
            if not PLACEHOLDER_RE.match(value) and len(value) >= 8:
                yield Finding("HIGH", "sensitive_assignment", path, line_no, f"{assignment.group(1)} has non-placeholder value {redact(value)}")

        # Opaque identifiers are not auth credentials, but should not be real internal Wiki IDs.
        internal_assignment = re.search(r"(?i)(node[_-]?token|doc[_-]?token|root[_-]?node[_-]?token|space[_-]?id)\s*[:=]\s*[\"']?([^\"'\s,}]+)", line)
        if internal_assignment:
            value = internal_assignment.group(2).strip()
            if not PLACEHOLDER_RE.match(value) and not value.startswith("$") and len(value) >= 8:
                # Avoid flagging source code expressions, variable names, and CLI option names.
                is_code_expression = value.endswith("(") or "." in value or value.startswith("_")
                if not is_code_expression and not re.match(r"^[A-Z_][A-Z0-9_]*$", value) and not value.startswith("--"):
                    yield Finding("MEDIUM", "internal_identifier_assignment", path, line_no, f"{internal_assignment.group(1)} has non-placeholder value {redact(value)}")

    # High-entropy tokens near sensitive keywords.
    if SENSITIVE_KEY_RE.search(line):
        for candidate in re.findall(r"[A-Za-z0-9_+./=-]{24,}", line):
            if PLACEHOLDER_RE.match(candidate) or candidate.startswith("http"):
                continue
            if shannon_entropy(candidate) >= 4.5:
                yield Finding("HIGH", "high_entropy_near_sensitive_key", path, line_no, f"high-entropy candidate {redact(candidate)}")


def main() -> int:
    findings: list[Finding] = []
    files = git_candidate_files()
    for path_str in files:
        findings.extend(inspect_filename(path_str))
        path = Path(path_str)
        text = read_text(path)
        if text is None:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            findings.extend(inspect_line(path_str, idx, line))

    if findings:
        print("Sensitive information scan failed. Findings are redacted:", file=sys.stderr)
        for item in findings[:100]:
            print(
                f"[{item.severity}] {item.kind} {item.path}:{item.line} - {item.detail}",
                file=sys.stderr,
            )
        if len(findings) > 100:
            print(f"... and {len(findings) - 100} more findings", file=sys.stderr)
        return 1

    print(f"Sensitive information scan passed: {len(files)} Git candidate files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
