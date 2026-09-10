#!/usr/bin/env python3
"""Stamp the version from versions.json into every plugin manifest.

versions.json is the single source of truth. Manifests are generated from it,
so a PR changes one line instead of ten fields across six files.

  stamp_versions.py            rewrite the manifests
  stamp_versions.py --check    exit 1 if any manifest is out of date

Edits are textual so that manifest formatting — which is hand-maintained and
includes blank lines a JSON round-trip would discard — survives untouched.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

MANIFESTS = [
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".cursor-plugin/marketplace.json",
    "skills/omni-integrations/.claude-plugin/plugin.json",
    "skills/omni-integrations/.cursor-plugin/plugin.json",
]

# Only a semver-shaped value is rewritten, so an unrelated "version" key
# (a schema version, say) is never touched.
VERSION_LINE = re.compile(r'("version"\s*:\s*)"\d+\.\d+\.\d+[^"]*"')

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def read_version() -> str:
    data = json.loads((ROOT / "versions.json").read_text())
    version = data["version"]
    if not SEMVER.match(version):
        sys.exit(
            f"versions.json: {version!r} is not MAJOR.MINOR.PATCH. "
            "All three components are required, e.g. 1.11.0 rather than 1.11."
        )
    return version


def main() -> int:
    check = "--check" in sys.argv
    version = read_version()
    stale = []

    for rel in MANIFESTS:
        path = ROOT / rel
        before = path.read_text()
        after, count = VERSION_LINE.subn(rf'\1"{version}"', before)
        if not count:
            sys.exit(f"{rel}: no version field found — has the manifest moved?")
        if after == before:
            continue
        stale.append(rel)
        if not check:
            path.write_text(after)

    if check and stale:
        print(f"Manifests are not stamped at {version} from versions.json:")
        for rel in stale:
            print(f"  {rel}")
        print("\nRun .github/scripts/stamp_versions.py to fix.")
        return 1

    print(f"{'Would stamp' if check else 'Stamped'} {version} "
          f"({len(stale)} file(s) {'stale' if check else 'updated'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
