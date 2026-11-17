"""
llm.py - talking to the LLM.

Internally we keep ONE neutral message format:
  {"role":"system"|"user","content":str}
  {"role":"assistant","content":str,"tool_calls":[{"id","name","arguments":dict}]}
  {"role":"tool","tool_call_id":str,"name":str,"content":str}
The functions below translate it to/from each provider's own format.
"""

import json
import time
import urllib.error
import urllib.request
import uuid

from Config import API_KEY, MODEL, PROVIDER, URL
from Tools import TOOLS


# ---- neutral format -> provider format -------------------------------------
def _openai_tool_schemas() -> list:
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
            for t in TOOLS.values()]


def to_openai(messages: list, ollama: bool = False) -> list:
    out = []
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            calls = []
            for c in m["tool_calls"]:
                if ollama:   # Ollama wants arguments as an object
                    calls.append({"function": {"name": c["name"], "arguments": c["arguments"]}})
                else:        # OpenAI-style wants arguments as a JSON string
                    calls.append({"id": c["id"], "type": "function",
                                  "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}})
            out.append({"role": "assistant", "content": m["content"] or "", "tool_calls": calls})
        elif m["role"] == "tool":
            if ollama:
                out.append({"role": "tool", "tool_name": m["name"], "content": m["content"]})
            else:
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def to_anthropic(messages: list) -> list:
    """Claude wants content *blocks*; all tool results for one turn go in ONE user message."""
    out = []
    for m in messages:
        if m["role"] == "user":
            out.append({"role": "user", "content": m["content"]})
        elif m["role"] == "assistant":
            blocks = []
            if m["content"]:
                blocks.append({"type": "text", "text": m["content"]})
            for c in m.get("tool_calls", []):
                blocks.append({"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]})
            out.append({"role": "assistant", "content": blocks})
        elif m["role"] == "tool":
            block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out


def build_request(messages: list):
    headers = {"Content-Type": "application/json", "User-Agent": "agent-demo/1.0"}
    if PROVIDER == "ollama":
        payload = {"model": MODEL, "messages": to_openai(messages, ollama=True),
                   "tools": _openai_tool_schemas(), "stream": False, "options": {"temperature": 0}}
    elif PROVIDER == "openai":
        headers["Authorization"] = f"Bearer {API_KEY}"
        payload = {"model": MODEL, "messages": to_openai(messages),
                   "tools": _openai_tool_schemas(), "temperature": 0}
    else:  # anthropic
        headers["x-api-key"] = API_KEY
        headers["anthropic-version"] = "2023-06-01"
        payload = {"model": MODEL, "max_tokens": 1024, "system": messages[0]["content"],
                   "messages": to_anthropic(messages[1:]),
                   "tools": [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                             for t in TOOLS.values()]}
    return payload, headers


# ---- provider reply -> neutral format --------------------------------------
def parse_response(data: dict) -> dict:
    """Turn any provider's reply into our neutral assistant message."""
    text, calls = "", []
    if PROVIDER == "ollama":
        m = data["message"]
        text = m.get("content") or ""
        for c in m.get("tool_calls") or []:
            calls.append({"id": f"call_{uuid.uuid4().hex[:8]}", "name": c["function"]["name"],
                          "arguments": c["function"].get("arguments") or {}})
    elif PROVIDER == "openai":
        m = data["choices"][0]["message"]
        text = m.get("content") or ""
        for c in m.get("tool_calls") or []:
            raw = c["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                args = {"__invalid_json__": raw}
            calls.append({"id": c["id"], "name": c["function"]["name"], "arguments": args})
    else:  # anthropic
        for block in data["content"]:
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                calls.append({"id": block["id"], "name": block["name"], "arguments": block["input"]})
    return {"role": "assistant", "content": text, "tool_calls": calls}


# ---- the actual HTTP call --------------------------------------------------
def chat(messages: list) -> dict:
    payload, headers = build_request(messages)
    req = urllib.request.Request(URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return parse_response(json.loads(resp.read()))
        except urllib.error.HTTPError as e:            # must come BEFORE URLError (it is a subclass)
            body = e.read().decode("utf-8", "replace")[:500]
            last_error = f"HTTP {e.code}: {body}"
            if e.code in (429, 500, 502, 503, 529) and attempt < 3:   # rate limit / server hiccup -> retry
                print(f"  LLM busy ({last_error[:80]}) - retrying {attempt}/3 ...")
                time.sleep(5 * attempt)
                continue
            raise RuntimeError(f"LLM API error - {last_error}")      # 401 bad key, 404 bad model... no point retrying
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = str(e)
            print(f"  LLM request failed (attempt {attempt}/3): {e}")
            time.sleep(2)
    raise RuntimeError(f"Could not reach the LLM at {URL}: {last_error}")