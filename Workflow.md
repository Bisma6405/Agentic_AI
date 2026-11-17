## Simple way to think about it

- **Model (AI)** is a smart person in a closed room. It has **no hands**. It cannot touch or run anything. It can only write notes saying "please do this."
- **Agent (your code)** is the assistant. It reads the notes and does the work.
- **Sandbox (Docker)** is the workshop where the assistant does the real work safely.
- **messages list** is a notebook with the whole conversation so far. The model has no memory, so the agent shows it the **full notebook every time**.

## Example task

You type: `Write a script that prints the first 10 primes and run it`

---

### Round 1

**Step 1: Agent starts the notebook** (`run_agent`)
```
messages = [
  system: "You are an assistant. You can use the run_command tool..."
  user:   "Write a script that prints the first 10 primes and run it"
]
```

**Step 2: Agent sends the notebook to the model** (`chat`)
It sends two things together:
- The notebook (`messages`)
- The tool list: "There is one tool, `run_command`. It runs a shell command. It needs a text called `command`."

This goes over the internet to the model's server.

**Step 3: Model writes a note**
The model thinks: "I need to create a file and run it. I can't do it myself, but I have a tool." So it replies with a request:
```
tool_call: run_command(command="echo 'print([2,3,5,7,11,13,17,19,23,29])' > primes.py")
```
The model only **asked**. It ran nothing.

**Step 4: Agent reads the note** (`parse_response`)
The model's reply is one long block of JSON. `parse_response` pulls out the useful part: the tool name and the command. The agent sees the tool request is not empty, so it knows the model wants a tool. It adds the note to the notebook.

**Step 5: Agent runs the tool**
`execute_tool_call` → `tool_run_command` → `run_in_sandbox`. The agent starts a Docker container (no internet, and it can only write in the `workspace` folder) and runs the command inside.

**Step 6: Sandbox gives back a raw result**
The file was created and nothing was printed:
```
exit_code = 0,  stdout = "",  stderr = "",  timed_out = False
```

**Step 7: Format function turns it into clean text** (`tool_run_command`)
It joins the raw pieces into one simple text:
```
exit_code: 0
```
(Empty output is skipped. If the output were too long, `truncate` would shorten it.)

**Step 8: Agent adds the result to the notebook**
```
messages = [
  system: ...
  user:   "Write a script ..."
  assistant: (tool_call) run_command("echo ... > primes.py")
  tool:   "exit_code: 0"
]
```

---

### Round 2 (the loop runs again)

**Step 9:** The agent sends the **whole notebook** to the model again.

**Step 10:** The model reads it: "The file is created (`exit_code: 0`). Now I need to run it." New note:
```
tool_call: run_command(command="python primes.py")
```

**Steps 11-14:** Same as before. The agent runs it in the sandbox. This time the raw result is:
```
exit_code = 0,  stdout = "[2, 3, 5, 7, 11, 13, 17, 19, 23, 29]\n"
```
After formatting:
```
exit_code: 0
stdout:
[2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
```
This is added to the notebook. The notebook now has 6 entries.

---

### Round 3 (the last one)

**Step 15:** The agent sends the whole notebook to the model again.

**Step 16:** The model reads it: "The job is done and the output looks right. I don't need any more tools." This time it sends **no note**, just a plain text answer:
```
"I created primes.py and ran it. The first 10 primes: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29."
```

**Step 17:** The agent sees there are **no tool requests**. That means the model is finished. The loop stops and the agent prints the text on the terminal:
```
=== FINAL ANSWER (after 3 step(s)) ===
I created primes.py and ran it. ...
```
Then `task>` comes back.

---

## Summary table

| Round | What the model said | What the agent did |
|-------|---------------------|--------------------|
| 1 | "Create the file" (note) | Created the file in the sandbox, returned `exit_code: 0` |
| 2 | "Run the file" (note) | Ran it in the sandbox, returned the output |
| 3 | "Here is the answer" (text) | Printed it, **loop ends** |

## 3 things to remember

1. **The model never runs anything.** It only says "please run this command." The agent runs it.
2. **The loop continues as long as the model sends a note.** When it sends plain text, the loop stops.
3. **The full notebook is sent every round.** That is how the model knows what happened before. If the notebook gets too long, `compact_history` shrinks the old tool results.

























## The flow in simple English

1. **You type a task.** At the `task>` prompt you write your task. `main.py` catches it with `input()` and gives it to `run_agent`.
2. **The agent starts a notebook.** `run_agent` creates a `messages` list with two things: the system rules and your task.
3. **The agent sends everything to the model.** Through `chat()`, it sends the notebook and the **tool list** (what `run_command` is and what input it needs) to the model.
4. **The model reads the task and the tool list.** The model **never runs anything itself**. It only replies, and the reply is one of two things:
   - "I want to use `run_command`, and this is the command" (a tool request)
   - or a plain text answer
5. **The agent runs the tool.** If the model asked for a tool, the agent passes the request through `execute_tool_call` → `tool_run_command` → `run_in_sandbox`.
6. **The sandbox (Docker) runs the command.** It sends back a **raw result**: exit_code, stdout and stderr as separate pieces.
7. **The result is cleaned up.** `tool_run_command` **formats** the raw result into one simple text. If it is too long, `truncate` shortens it.
8. **The result goes back into the notebook.** The agent adds the text to `messages` as a "tool result", then **goes back to step 3** and sends the whole notebook to the model again.
9. **The model reads the result.** If the work is not finished, it asks for another tool (back to step 4). If it is finished, it sends a **plain text answer** instead.
10. **The agent prints the answer.** With no tool request left, the loop stops and the final answer is printed on the terminal. Then `task>` comes back.

**In one line:**
User → Agent → Model → (tool request) → Agent → Sandbox → raw result → format → Agent → Model → ... → final text → Agent → Terminal