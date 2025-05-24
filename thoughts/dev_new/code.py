import json, pathlib, difflib, os
from datetime import datetime, timezone
from pathlib import Path

async def run(state, *, thought: str | None = None,
                     name:  str | None = None,
                     text:  str | None = None):
    """
    Create – or iteratively refine – a thought draft via the LLM.

    • First call (no drafts) 👉 generate thought.json / prompt.txt / code.py.
    • Subsequent calls       👉 treat *text* as an instruction, ask the LLM
                                for updated file bodies, show a unified diff,
                                and stash them for later `/dev_save`.
    """
    llm     = state["__llm"]
    system  = state.get("__prompt", "")
    ctx     = state.setdefault("__dev", {})
    drafts  = ctx.setdefault("drafts", {})

    # ───────────────────────────────────────────────────────────────────────
    # 0.   Which thought are we talking about?
    # ───────────────────────────────────────────────────────────────────────
    chosen = (thought or name or ctx.get("thought") or "").strip()

    # ───────────────────────────────────────────────────────────────────────
    # 1.   FIRST-TIME CREATION  (no drafts yet)                             │
    # ───────────────────────────────────────────────────────────────────────
    if not drafts:
        # ----- build payload with rich context -----------------------
        factory   = state["__factory"]
        thoughts_md = state.get("__thoughts_md", "")

        # 1️⃣  conversation (last 20 turns for safety)
        conv_hist = ""
        conv = state.get("__conv")
        if conv:
            conv_hist = "\n".join(
                f"{e['sender']}: {e['text']}" for e in conv.history()
            )
        else:
            # fall back to whatever snapshot Brain passed in
            conv_hist = state.get("__history", "")

        # 2️⃣  emphasise *this* user request
        last_user_turn = (text or "").strip()

        # 3️⃣  any drafts already loaded (usually empty on first run)
        ctx_drafts = ctx.get("drafts", {})

        payload = json.dumps({
            "thought_name": chosen,            # may be ""
            "request":    last_user_turn,
            "history":    conv_hist,
            "thoughts_md":  thoughts_md,
            "drafts":     ctx_drafts         # {}
        }, ensure_ascii=False)

        # ----- LOG the full prompt -------------------------------------------
        ts      = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_dir = pathlib.Path("logs") / "prompts"
        log_dir.mkdir(parents=True, exist_ok=True)

        prompt_file = log_dir / f"dev_new_prompt_{ts}.txt"
        
        # EXACT bytes that go to the LLM
        full_prompt = "\n\n".join([
            (system or ""),
            "<THOUGHTS>",
            thoughts_md,
            "<PAYLOAD>",
            payload
        ])
        prompt_file.write_text(full_prompt, encoding="utf-8")

        # (No inter-prompt diff files – everything lives in one log now)

        # ----- call the LLM ----------------------------------------------------
        raw = llm.generate_json(payload, system_prompt=system)

        # ----- append the model's answer to the same file ----------------------
        with prompt_file.open("a", encoding="utf-8") as f:
            f.write("\n\n### LLM OUTPUT ###\n")
            f.write(raw.strip() + "\n")
        try:
            files = json.loads(raw)
        except Exception:
            return {"reply": "⚠️ LLM returned invalid JSON – please rephrase."}

        chosen = files.get("thought_name") or chosen or "new_thought"
        ctx["thought"] = chosen

        # Write each returned file into the draft buffer
        root = pathlib.Path("thoughts") / chosen
        for rel_path, body in files.items():
            if rel_path == "thought_name":
                continue
            drafts[str(root / rel_path)] = body
        # Build a preview of the generated files
        blobs = "\n\n".join(
            f"**{Path(path).name}**\n```{body}```"
            for path, body in drafts.items()
        )
        return {"reply": (
            f"🆕 Draft for **{chosen}** created:\n\n"
            f"{blobs}\n\n"
            "Tweak your instruction or `/dev_save` when ready."
        )}

    # ───────────────────────────────────────────────────────────────────────
    # 2.   REFINEMENT  (drafts already exist)                               │
    # ───────────────────────────────────────────────────────────────────────
    if not text:
        return {"reply": "✏️ Provide an instruction (e.g. 'add error handling')."}

    # Get the same context as for creation, but with additional instruction
    factory   = state["__factory"]
    thoughts_md = state.get("__thoughts_md", "")
    
    # Build conversation history
    conv_hist = ""
    conv = state.get("__conv")
    if conv:
        conv_hist = "\n".join(
            f"{e['sender']}: {e['text']}" for e in conv.history()
        )
    else:
        conv_hist = state.get("__history", "")

    # Create the payload
    payload = json.dumps({
        "thought_name": ctx.get("thought"),
        "instruction": text,
        "request": (text or "").strip(),
        "history": conv_hist,
        "thoughts_md": thoughts_md,
        "current": drafts
    }, ensure_ascii=False)

    # ----- LOG the full prompt for refinement -------------------------------------------
    ts      = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_dir = pathlib.Path("logs") / "prompts"
    log_dir.mkdir(parents=True, exist_ok=True)

    prompt_file = log_dir / f"dev_new_prompt_{ts}.txt"
    
    # EXACT bytes that go to the LLM
    full_prompt = "\n\n".join([
        (system or ""),
        "<THOUGHTS>",
        thoughts_md,
        "<PAYLOAD>",
        payload
    ])
    prompt_file.write_text(full_prompt, encoding="utf-8")
    
    raw = llm.generate_json(payload, system_prompt=system)
    
    # ----- append the model's answer to the same file ----------------------
    with prompt_file.open("a", encoding="utf-8") as f:
        f.write("\n\n### LLM OUTPUT ###\n")
        f.write(raw.strip() + "\n")
        
    try:
        updated = json.loads(raw)
    except Exception:
        return {"reply": "⚠️ Couldn't parse the LLM's response – try again."}

    # Build diff & stage updates
    diff_chunks = []
    for path, new_body in updated.items():
        old_body = drafts.get(path, "").splitlines(keepends=True)
        new_body = new_body.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(
            old_body, new_body,
            fromfile=f"a/{path}", tofile=f"b/{path}", n=3))
        diff_chunks.append(diff)
        drafts[path] = "\n".join(new_body)  # stage new version

    if not diff_chunks:
        return {"reply": "No changes detected."}

    ctx["pending_patch"] = "\n".join(diff_chunks)  # allow dev_patch to apply/rollback
    # Show unified diff preview immediately
    return {"reply": (
        f"Here's the proposed patch:\n```\
        \n{ctx['pending_patch']}\n```\n"
        "Say **apply patch** to accept or **discard** to ignore."
    )}
