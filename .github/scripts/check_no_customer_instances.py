#!/usr/bin/env python3
"""Fail when a customer or partner Omni instance hostname appears in public text.

This repository is public. A tenant hostname like `<customer>.omniapp.co` names a
specific Omni customer, so it must not reach a file, a commit message, or a pull
request title or body. Nothing here is a credential — the leak is the customer
relationship itself, which is why the usual secret scanners do not catch it.

The check is **default-deny** on the tenant domain: any `<sub>.omniapp.co` fails
unless `<sub>` is one of the generic placeholders below. That is deliberate.
Maintaining a denylist of real customer names would mean committing those names
to a public repo — the guard would become the leak.

Usage:
    check_no_customer_instances.py                    # every git-tracked file
    check_no_customer_instances.py PATH [PATH ...]    # specific files
    check_no_customer_instances.py --stdin LABEL      # text on stdin (commit
                                                      # messages, PR body, ...)

Exits 0 when clean, 1 on a finding, 2 on a usage error.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Per-tenant Omni domain. A subdomain here is an instance name.
TENANT_RE = re.compile(
    r"(?<![A-Za-z0-9._-])([A-Za-z0-9][A-Za-z0-9-]*)\.omniapp\.co\b",
    re.IGNORECASE,
)

# Generic stand-ins that carry no customer identity. Keep this list boring:
# if a name could plausibly be a real organisation, it does not belong here.
PLACEHOLDERS = {
    "acme",
    "company",
    "example",
    "instance",
    "my-org",
    "myorg",
    "org",
    "placeholder",
    "tenant",
    "your-instance",
    "your-org",
    "yourinstance",
    "yourorg",
}

# Omni-owned domains are fine and deliberately not matched by TENANT_RE:
# omni.co, exploreomni.dev (incl. playground/evals hosts).

SKIP_DIRS = {".git"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".woff", ".woff2", ".zip"}


def findings_in(text: str) -> list[tuple[int, str]]:
    """Return (line number, offending hostname) for each disallowed instance."""
    found = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in TENANT_RE.finditer(line):
            if match.group(1).lower() not in PLACEHOLDERS:
                found.append((lineno, match.group(0)))
    return found


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = []
    for name in out.split("\0"):
        if not name:
            continue
        path = Path(name)
        if SKIP_DIRS & set(path.parts) or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        paths.append(path)
    return paths


def report(label: str, found: list[tuple[int, str]]) -> None:
    for lineno, host in found:
        print(f"  {label}:{lineno}: {host}")


def main(argv: list[str]) -> int:
    if argv[:1] == ["--stdin"]:
        if len(argv) != 2:
            print("usage: check_no_customer_instances.py --stdin LABEL", file=sys.stderr)
            return 2
        label = argv[1]
        found = findings_in(sys.stdin.read())
        if not found:
            print(f"No customer or partner instance hostnames in {label}.")
            return 0
        print(f"Customer or partner instance hostname in {label}:")
        report(label, found)
        print(explain())
        return 1

    targets = [Path(a) for a in argv] if argv else tracked_files()

    total = 0
    for path in targets:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        found = findings_in(text)
        if found:
            if total == 0:
                print("Customer or partner instance hostnames found:")
            report(str(path), found)
            total += len(found)

    if total:
        print(explain())
        return 1

    scope = "tracked files" if not argv else f"{len(targets)} file(s)"
    print(f"No customer or partner instance hostnames in {scope}.")
    return 0


def explain() -> str:
    return (
        "\nThis repository is public, and a tenant hostname names a specific Omni\n"
        "customer. Replace it with a placeholder such as `yourorg.omniapp.co`, or\n"
        "describe the instance generically (\"a real multi-tenant instance\").\n"
        "\n"
        "Validation claims do not need a hostname to be credible — say what was run\n"
        "and what came back, not whose instance it ran against.\n"
        "\n"
        "If the name has already been pushed, scrubbing the file is not enough:\n"
        "commit messages and pull request bodies keep their own history. See the\n"
        "\"Customer and partner instance names\" section of CONTRIBUTING.md.\n"
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
