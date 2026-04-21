#!/usr/bin/env python3
"""Grade a single assertion against agent output using Claude as an LLM judge.

Reads from stdin: a JSON object with keys "assertion" and "output".
Calls Claude via the claude CLI and prints a grading JSON object.

Usage:
  echo '{"assertion": "...", "output": "..."}' | python3 grade_assertion.py [model]
"""

import json
import re
import subprocess
import sys


def grade(assertion: str, output_text: str, model: str) -> dict:
    prompt = f"""Grade whether an AI agent's output satisfies this assertion.

Assertion: {assertion}

Agent output:
<output>
{output_text}
</output>

Reply with a JSON object only — no prose before or after:
{{
  "passed": true or false,
  "evidence": "Quote the specific part of the output that proves or disproves the assertion. If the assertion cannot be verified from the output, state what is missing."
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
    result = grade(payload["assertion"], payload["output"], model)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
