# skills/reply/code.py
import json
from pathlib import Path
from datetime import datetime, timezone
import pathlib
async def run(state, *, text):
    llm     = state["__llm"]
    system  = state["__prompt"]
    # if we're running under the Executor, we have a Conversation handle:
    conv = state.get("__conv")
    if conv:
        # rebuild the full chat history
        entries = conv.history()   # list of {sender, text, ts}
        hist = "\n".join(f"{e['sender']}: {e['text']}" for e in entries)
    else:
        # fallback to whatever snapshot was passed in
        hist = state.get("__history", "")
    skills  = state.get("__skills_md", "")


    # build a few-shot style prompt:
    prompt = "\n\n".join([
      system,
      "Here are my available skills to use:\n" + skills,
      "Conversation so far:\n" + hist,
      f"user: {text}",
      "assistant:"
    ]).strip()

    # ── log prompt & model output ────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_dir = pathlib.Path("logs") / "prompts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"reply_prompt_{ts}.txt"
    log_file.write_text(prompt, encoding="utf-8")

    answer = llm.generate_text(prompt, "")

    with log_file.open("a", encoding="utf-8") as f:
        f.write("\n\n### LLM OUTPUT ###\n")
        f.write(answer.strip() + "\n")

    return {"reply": answer}
