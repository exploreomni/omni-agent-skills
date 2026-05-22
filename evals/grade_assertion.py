#!/usr/bin/env python3
"""Grade a single assertion against agent output using Claude as an LLM judge.

Reads from stdin: a JSON object with keys "assertion", "output", and optional
"commands" (list of {command, result_preview} extracted from the transcript).
Calls Claude via the claude CLI and prints a grading JSON object.

Usage:
  echo '{"assertion": "...", "output": "...", "commands": [...]}' | python3 grade_assertion.py [model]
"""

import json
import re
import subprocess
import sys


def format_commands(commands: list) -> str:
    if not commands:
        return "(no tool calls recorded)"
    lines = []
    for i, c in enumerate(commands, 1):
        cmd = c.get("command", "")
        result = c.get("result_preview", "")
        lines.append(f"[{i}] $ {cmd}\n    → {result}")
    return "\n".join(lines)


def grade(assertion: str, output_text: str, commands: list, model: str) -> dict:
    commands_block = format_commands(commands)

    prompt = f"""Grade whether an AI agent's output satisfies this assertion.

Assertion: {assertion}

Agent's final response:
<output>
{output_text}
</output>

Agent's tool calls (authoritative log of what the agent actually did):
<commands>
{commands_block}
</commands>

Grading rules:
- For "did the agent call X" / "the query body includes Y" / "the agent ran omni Z" — prefer the <commands> log over the prose. The agent may not have mentioned a command it ran.
- For narrative or quality assertions ("the agent synthesizes…", "the result is clear…") — use the <output> prose.
- If <commands> is empty, fall back to the prose.

Reply with a JSON object only — no prose before or after:
{{
  "passed": true or false,
  "evidence": "Quote the specific command or part of the output that proves or disproves the assertion. If the assertion cannot be verified, state what is missing."
}}"""

    try:
        result = subprocess.run(
            [
                "claude",
                "--print", prompt,
                "--model", model,
                "--output-format", "json",
                "--bare",
                "--permission-mode", "bypassPermissions",
                "--no-session-persistence",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        envelope = json.loads(result.stdout)
        result_text = envelope.get("result", "")
    except Exception as e:
        return {"passed": False, "evidence": f"Grader call failed: {e}"}

    # Extract first JSON object from the result text
    m = re.search(r"\{.*\}", result_text, re.DOTALL)
    if not m:
        return {"passed": False, "evidence": "Grader returned no JSON object"}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {"passed": False, "evidence": "Grader returned unparseable JSON"}


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5-20251001"
    payload = json.loads(sys.stdin.read())
    result = grade(
        payload["assertion"],
        payload.get("output", ""),
        payload.get("commands", []),
        model,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
