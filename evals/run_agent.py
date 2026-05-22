#!/usr/bin/env python3
"""Provider-agnostic agentic runner for skill evals.

Runs a tool-use loop with a bash executor against any LiteLLM-supported
provider. Prints a JSON envelope to stdout that runner.sh captures as
raw_output.json.

Usage:
  python3 run_agent.py \
    --provider anthropic \
    --model claude-sonnet-4-6 \
    --prompt "task text" \
    [--system-prompt-file path/to/SKILL.md] \
    [--working-dir path/to/outputs] \
    [--max-turns 20] \
    [--bash-timeout 60]

Output (stdout):
  {"result": "...", "usage": {"input_tokens": N, "output_tokens": N}}

API keys are read from the environment:
  Anthropic  → ANTHROPIC_API_KEY
  OpenAI     → OPENAI_API_KEY
  Gemini     → GEMINI_API_KEY
  (others per LiteLLM docs)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys

# ── Silence LiteLLM before importing it ──────────────────────────────────────
os.environ.setdefault("LITELLM_LOG", "ERROR")
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)

try:
    import litellm
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
except ImportError:
    print(json.dumps({
        "result": "",
        "is_error": True,
        "error": "litellm is not installed. Run: pip install litellm",
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }))
    sys.exit(1)


# ── Bash tool definition (OpenAI function-calling schema) ─────────────────────

BASH_TOOL = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Execute a bash command and return its stdout and stderr. "
            "Use this for all file operations, CLI tools, and system tasks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to run.",
                }
            },
            "required": ["command"],
        },
    },
}


# ── Bash executor ─────────────────────────────────────────────────────────────

def run_bash(command: str, cwd: str | None, timeout: int) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        out = proc.stdout
        if proc.returncode != 0:
            err = proc.stderr.strip()
            out += f"\n[exit {proc.returncode}]"
            if err:
                out += f"\n{err}"
        return out or "[no output]"
    except subprocess.TimeoutExpired:
        return f"[timed out after {timeout}s]"
    except Exception as exc:
        return f"[error: {exc}]"


# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_agent(
    provider: str,
    model: str,
    prompt: str,
    system_prompt: str | None,
    max_turns: int,
    bash_timeout: int,
    working_dir: str | None,
    reasoning_effort: str | None = None,
    transcript_file: str | None = None,
) -> dict:
    model_string = f"{provider}/{model}"

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    total_input = 0
    total_output = 0
    final_text = ""

    extra_kwargs: dict = {}
    if reasoning_effort:
        extra_kwargs["reasoning_effort"] = reasoning_effort

    for _turn in range(max_turns):
        try:
            response = litellm.completion(
                model=model_string,
                messages=messages,
                tools=[BASH_TOOL],
                tool_choice="auto",
                **extra_kwargs,
            )
        except Exception as exc:
            return {
                "result": final_text,
                "is_error": True,
                "error": str(exc),
                "usage": {"input_tokens": total_input, "output_tokens": total_output},
            }

        if response.usage:
            total_input += response.usage.prompt_tokens or 0
            total_output += response.usage.completion_tokens or 0

        msg = response.choices[0].message

        if msg.content:
            final_text = msg.content

        # No tool calls → model is done
        if not msg.tool_calls:
            break

        # Append the assistant turn
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        assistant_entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
        messages.append(assistant_entry)

        # Execute each tool call and feed results back
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
                command = args.get("command", "")
            except (json.JSONDecodeError, KeyError):
                command = tc.function.arguments

            result = run_bash(command, working_dir, bash_timeout)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    if transcript_file:
        try:
            with open(transcript_file, "w") as f:
                json.dump(messages, f, indent=2)
        except OSError:
            pass  # Best-effort; don't fail the run if transcript can't be written

    return {
        "result": final_text,
        "is_error": False,
        "usage": {"input_tokens": total_input, "output_tokens": total_output},
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provider-agnostic agentic runner for skill evals"
    )
    parser.add_argument(
        "--provider", required=True,
        help="LiteLLM provider slug (e.g. anthropic, openai, gemini, bedrock)",
    )
    parser.add_argument(
        "--model", required=True,
        help="Model name within the provider (e.g. claude-sonnet-4-6, gpt-4o)",
    )
    parser.add_argument("--prompt", required=True, help="Task prompt for the agent")
    parser.add_argument(
        "--system-prompt-file",
        help="Path to a file whose contents become the system prompt (e.g. SKILL.md)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=20,
        help="Maximum agentic turns before stopping (default: 20)",
    )
    parser.add_argument(
        "--bash-timeout", type=int, default=60,
        help="Per-command timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--working-dir",
        help="Working directory for bash commands (default: current directory)",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default=None,
        help="OpenAI reasoning effort (low/medium/high/xhigh); omit for provider default",
    )
    parser.add_argument(
        "--transcript-file",
        help="Path to write the full conversation transcript as JSON (optional)",
    )

    args = parser.parse_args()

    system_prompt: str | None = None
    if args.system_prompt_file:
        try:
            with open(args.system_prompt_file) as f:
                system_prompt = f.read()
        except OSError as exc:
            print(json.dumps({
                "result": "",
                "is_error": True,
                "error": f"Could not read system prompt file: {exc}",
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }))
            sys.exit(1)

    result = run_agent(
        provider=args.provider,
        model=args.model,
        prompt=args.prompt,
        system_prompt=system_prompt,
        max_turns=args.max_turns,
        bash_timeout=args.bash_timeout,
        working_dir=args.working_dir,
        reasoning_effort=args.reasoning_effort,
        transcript_file=args.transcript_file,
    )

    print(json.dumps(result))


if __name__ == "__main__":
    main()
