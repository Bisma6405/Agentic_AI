# Raw Tool-Calling Agent

A small agent built with only the Python standard library and an LLM. No LangChain, no CrewAI, no SDKs.

## How it works

An agent is just a loop:

1. Send the conversation and the list of tools to the LLM.
2. If the LLM replies with plain text, we are done.
3. If the LLM asks for a tool, our code runs it, adds the result to the conversation, and goes back to step 1.

The LLM never runs anything itself. It only asks. Our code decides what runs, and commands run inside a locked-down Docker container.

## Files

| File | What it does |
|------|--------------|
| `agent.py` | Entry point and the agent loop |
| `config.py` | Reads `.env`, picks provider and model, holds limits and the system prompt |
| `sandbox.py` | Runs a shell command in Docker (no network, memory/CPU limits, timeout) |
| `context.py` | Cuts long tool output and shrinks old tool results so the conversation stays small |
| `tools.py` | Tool functions, their JSON schemas, and `execute_tool_call` |
| `llm.py` | Converts messages to each provider's format and makes the HTTP call |

## Setup

1. Install Python 3.10+ and Docker (Docker is needed for the default safe sandbox).
2. Put all files in one folder.
3. Create a `.env` file in the same folder:

```
AGENT_PROVIDER=openai
AGENT_API_KEY=your-key-here
# AGENT_MODEL=optional model name
# AGENT_URL=optional endpoint
# AGENT_SANDBOX=docker
```

Providers:

- `openai`: any OpenAI-compatible API (Groq by default, also Gemini, OpenRouter, OpenAI)
- `anthropic`: Claude API (also reads `ANTHROPIC_API_KEY`)
- `ollama`: local Ollama, no key needed (default)

Never hard-code your key in the code and never commit `.env`.

## Run

One task:

```
python main.py "Write a script that prints the first 10 primes and run it"
```

Interactive mode:

```
python main.py
```

Type a task at the `task>` prompt. Type `quit` to exit.

## Settings (in `config.py`)

| Setting | Default | Meaning |
|---------|---------|---------|
| `COMMAND_TIMEOUT` | 15 | Seconds before a command is killed |
| `MAX_STEPS` | 10 | Hard stop for the loop |
| `MAX_TOOL_OUTPUT_CHARS` | 2000 | One tool result is cut to this size |
| `MAX_HISTORY_CHARS` | 12000 | Old tool results are shrunk above this |
| `KEEP_RECENT_TOOL_RESULTS` | 2 | Newest results that are never shrunk |

## Adding a new tool

1. Write a function in `tools.py` that returns a string.
2. Add an entry for it in the `TOOLS` dictionary with a name, description and parameters schema.

No other file needs to change.

## Notes

- Files the agent creates are saved in the `workspace/` folder next to the scripts.
- `AGENT_SANDBOX=local` runs commands directly on your machine. It is not safe, use it only for quick tests.
- If you get a "model not found" error, check your provider's model list and set `AGENT_MODEL`.