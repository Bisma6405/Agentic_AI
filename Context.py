"""
context.py - keep tool output from flooding the conversation (context-window control).
"""

from Config import KEEP_RECENT_TOOL_RESULTS, MAX_HISTORY_CHARS, MAX_TOOL_OUTPUT_CHARS


def truncate(text: str, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Keep the beginning and the end (errors usually sit at the end)."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n[... {len(text) - limit} characters truncated ...]\n{text[-half:]}"


def compact_history(messages: list) -> None:
    """If the conversation is too big, shrink the OLDER tool results (in place)."""
    def total() -> int:
        return sum(len(str(m.get("content", ""))) for m in messages)

    if total() <= MAX_HISTORY_CHARS:
        return
    tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    for i in tool_idx[:-KEEP_RECENT_TOOL_RESULTS]:
        content = messages[i]["content"]
        if len(content) > 200 and not content.startswith("[old output shrunk"):
            messages[i]["content"] = f"[old output shrunk to save context] {content[:150]}..."
    if total() > MAX_HISTORY_CHARS:
        print(f"  (warning: history still {total()} chars after compaction)")