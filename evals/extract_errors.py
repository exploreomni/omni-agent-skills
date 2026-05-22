#!/usr/bin/env python3
"""Extract failed commands from a run_agent.py transcript.

Reads transcript.json (the full message history) and outputs a JSON summary
of every bash tool call whose result indicates failure (non-zero exit code,
timeout, or error).

Usage:
  python3 extract_errors.py <transcript-file>

Output (stdout):
  {
    "total_commands": 12,
    "failed_commands": 3,
    "errors": [
      {
        "turn": 2,
        "command": "omni query run --body '{...}'",
        "result_preview": "[exit 1]\nUnable to parse data stream",
        "category": "cli_error"
      }
    ]
  }
"""

import json
import re
import sys

EXIT_PATTERN = re.compile(r"\[exit (\d+)]")
TIMEOUT_PATTERN = re.compile(r"\[timed out after")
ERROR_PATTERN = re.compile(r"\[error:")


def extract(transcript_path: str) -> dict:
    with open(transcript_path) as f:
        messages = json.load(f)

    errors = []
    total_commands = 0
    turn = 0

    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            turn += 1

        if msg.get("role") == "tool":
            total_commands += 1
            result = msg.get("content", "")

            # Detect failure indicators
            exit_match = EXIT_PATTERN.search(result)
            is_timeout = TIMEOUT_PATTERN.search(result)
            is_error = ERROR_PATTERN.search(result)

            if exit_match or is_timeout or is_error:
                # Find the matching assistant turn to get the command
                command = ""
                for prev in messages:
                    if prev.get("role") == "assistant" and prev.get("tool_calls"):
                        for tc in prev["tool_calls"]:
                            if tc.get("id") == msg.get("tool_call_id"):
                                try:
                                    args = json.loads(tc["function"]["arguments"])
                                    command = args.get("command", "")
                                except (json.JSONDecodeError, KeyError):
                                    command = tc["function"].get("arguments", "")
                                break

                # Classify the error
                if is_timeout:
                    category = "timeout"
                elif is_error:
                    category = "runtime_error"
                elif exit_match and int(exit_match.group(1)) != 0:
                    category = "cli_error"
                else:
                    category = "unknown"

                # Build a preview (first 200 chars, single line)
                preview = result.replace("\n", " ").strip()
                if len(preview) > 200:
                    preview = preview[:197] + "..."

                errors.append({
                    "turn": turn,
                    "command": command,
                    "result_preview": preview,
                    "category": category,
                })

    return {
        "total_commands": total_commands,
        "failed_commands": len(errors),
        "errors": errors,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: extract_errors.py <transcript-file>", file=sys.stderr)
        sys.exit(1)

    result = extract(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
