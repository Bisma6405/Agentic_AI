"""
config.py - all settings in one place.

Reads the .env file, picks the provider/model, and holds every limit and the system prompt.
Put these in a .env file next to this script (never hard-code your key!):

  AGENT_PROVIDER = "openai"     OpenAI-compatible APIs: Groq, Gemini, OpenRouter, OpenAI
                   "anthropic"  Claude API
                   "ollama"     local Ollama (default)
  AGENT_API_KEY  = your key     (anthropic also accepts ANTHROPIC_API_KEY)
  AGENT_MODEL    = optional model name override
  AGENT_URL      = optional endpoint override
  AGENT_SANDBOX  = "docker" (default, safe) or "local" (UNSAFE, testing only)
"""

import os
import sys
from pathlib import Path


def load_env_file(path: Path) -> None:
    """Read KEY=VALUE lines from a .env file into os.environ (real env vars win)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(Path(__file__).parent / ".env")   # keep your API key in .env, NOT in the code

PROVIDER = os.getenv("AGENT_PROVIDER", "ollama").lower()

# provider -> (default model, default endpoint).  Model names change over time:
# if you get a "model not found" error, check your provider's model list.
PROVIDERS = {
    "ollama":    ("qwen2.5:7b",         "http://localhost:11434/api/chat"),
    "openai":    ("openai/gpt-oss-120b", "https://api.groq.com/openai/v1/chat/completions"),
    "anthropic": ("claude-haiku-5-5",   "https://api.anthropic.com/v1/messages"),
}
# Other OpenAI-compatible endpoints you can put in AGENT_URL:
#   OpenRouter: https://openrouter.ai/api/v1/chat/completions
#   Gemini:     https://generativelanguage.googleapis.com/v1beta/openai/chat/completions
#   OpenAI:     https://api.openai.com/v1/chat/completions

if PROVIDER not in PROVIDERS:
    sys.exit(f"Unknown AGENT_PROVIDER '{PROVIDER}'. Use one of: {list(PROVIDERS)}")

MODEL = os.getenv("AGENT_MODEL", PROVIDERS[PROVIDER][0])
URL = os.getenv("AGENT_URL", PROVIDERS[PROVIDER][1])
API_KEY = os.getenv("AGENT_API_KEY") or (os.getenv("ANTHROPIC_API_KEY") if PROVIDER == "anthropic" else None)

SANDBOX = os.getenv("AGENT_SANDBOX", "docker")
DOCKER_IMAGE = "python:3.12-slim"
WORKSPACE = Path(__file__).parent.joinpath("workspace").resolve()   # folder the agent may write to

COMMAND_TIMEOUT = 15            # seconds before a sandboxed command is killed
MAX_STEPS = 10                  # hard stop so the loop can never run forever
MAX_TOOL_OUTPUT_CHARS = 2000    # one tool result is cut down to this size
MAX_HISTORY_CHARS = 12000       # when the whole conversation exceeds this, shrink old tool results
KEEP_RECENT_TOOL_RESULTS = 2    # the newest N tool results are never shrunk

SYSTEM_PROMPT = (
    "You are a careful assistant that can run shell commands through the run_command tool. "
    "Commands run inside an isolated Linux container with Python 3 and NO internet access. "
    "Your working directory is /workspace; files you create there persist between commands. "
    "If a command fails (non-zero exit_code) read the stderr, fix the problem and try again. "
    "Never print huge outputs: use head, tail, grep or wc. "
    "When the task is finished, reply with a short plain-text summary and do not call more tools."
)


def check_config() -> None:
    if PROVIDER != "ollama" and not API_KEY:
        sys.exit("No API key found. Set the AGENT_API_KEY environment variable "
                 "(PowerShell:  $env:AGENT_API_KEY=\"your-key\")  or add it in the IntelliJ run configuration.")