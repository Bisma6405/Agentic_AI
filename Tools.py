"""
tools.py - a Python function + a JSON schema that describes it to the LLM.

To add a new tool: write a function, then add an entry to TOOLS.
"""

import json

from Config import COMMAND_TIMEOUT
from Context import truncate
from Sandbox import run_in_sandbox


def tool_run_command(command: str) -> str:
    result = run_in_sandbox(command)

    if result["timed_out"]:
        return (f"ERROR: the command exceeded the {COMMAND_TIMEOUT}s timeout and was killed. "
                "Use a faster approach or avoid long-running / interactive commands.")

    parts = [f"exit_code: {result['exit_code']}"]
    if result["stdout"].strip():
        parts.append("stdout:\n" + truncate(result["stdout"]))
    if result["stderr"].strip():
        parts.append("stderr:\n" + truncate(result["stderr"]))
    if result["exit_code"] != 0:
        parts.append("The command FAILED. Read stderr, fix the cause and try again.")
    return "\n".join(parts)


TOOLS = {
    "run_command": {
        "fn": tool_run_command,
        "name": "run_command",
        "description": "Run a shell command in an isolated Linux container (Python 3, no internet). "
                       "Working directory is /workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run, e.g. 'python hello.py'"}
            },
            "required": ["command"],
        },
    }
}


def execute_tool_call(call: dict) -> str:
    """Run one tool call {id, name, arguments}. NEVER raises: errors go back to the LLM as text."""
    name = call.get("name", "")
    args = call.get("arguments", {})

    if isinstance(args, str):                       # some models send arguments as a JSON string
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return "ERROR: tool arguments were not valid JSON."
    if not isinstance(args, dict) or "__invalid_json__" in args:
        return "ERROR: tool arguments were not valid JSON."
    if name not in TOOLS:
        return f"ERROR: unknown tool '{name}'. Available tools: {list(TOOLS)}"
    try:
        return TOOLS[name]["fn"](**args)
    except TypeError as e:                          # wrong / missing argument names
        return f"ERROR: bad arguments for {name}: {e}"
    except Exception as e:                          # any other bug in our tool
        return f"ERROR: tool {name} crashed: {type(e).__name__}: {e}"