"""
Agent.py - the agent loop (entry point).

THE IDEA
--------
An "agent" is just a while-loop:

    1. Send the conversation + a list of tools to the LLM.
    2. If the LLM answers with plain text      -> we are done.
    3. If the LLM asks to call a tool          -> WE run it, append the result
                                                  to the conversation, go to 1.

The LLM never runs anything itself. It only *asks*; our code decides what runs
and where (here: inside a locked-down Docker container).

Files:
  config.py   settings, limits, system prompt
  sandbox.py  runs commands in Docker
  context.py  truncate / compact the conversation
  tools.py    tool definitions + execute_tool_call
  llm.py      provider formats + HTTP call
  main.py     this file: the loop

Run:   python main.py "Write a script that prints the first 10 primes and run it"
"""

import sys

from Config import MAX_STEPS, MODEL, PROVIDER, SANDBOX, SYSTEM_PROMPT, check_config
from Context import compact_history
from Llm import chat
from Tools import execute_tool_call


def run_agent(task: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    for step in range(1, MAX_STEPS + 1):
        compact_history(messages)
        msg = chat(messages)
        messages.append(msg)

        if not msg["tool_calls"]:                            # plain answer -> finished
            print(f"\n=== FINAL ANSWER (after {step} step(s)) ===\n{msg['content']}")
            return msg["content"]

        for call in msg["tool_calls"]:                       # LLM wants tools -> run them
            print(f"\n[step {step}] TOOL CALL  {call['name']}({call['arguments']})")
            result = execute_tool_call(call)
            print(f"[step {step}] TOOL RESULT\n{result}")
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "name": call["name"], "content": result})

    print(f"\n=== STOPPED: reached MAX_STEPS={MAX_STEPS} without a final answer ===")
    return ""


if __name__ == "__main__":
    check_config()
    if len(sys.argv) > 1:
        run_agent(" ".join(sys.argv[1:]))
    else:
        print(f"Agent ready (provider={PROVIDER}, model={MODEL}, sandbox={SANDBOX}). Type a task, or 'quit'.")
        while True:
            task = input("\ntask> ").strip()
            if task.lower() in {"quit", "exit", ""}:
                break
            run_agent(task)
