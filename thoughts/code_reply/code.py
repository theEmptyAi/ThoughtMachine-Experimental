async def run(state, *, text=None):
    llm    = state["__llm"]
    system = state.get("__prompt", "")
    conv   = state.get("__conv")
    if conv:
        hist = "\n".join(f"{e['sender']}: {e['text']}" for e in conv.history())
    else:
        hist = state.get("__history", "")
    thoughts_md = state.get("__thoughts_md", "")
    prompt = "\n\n".join([
        system,
        "Here are my available thoughts:\n" + thoughts_md,
        "Conversation so far:\n"    + hist,
        f"user: {text}",
        "assistant:"
    ]).strip()
    answer = llm.generate_text(prompt, "")
    return {"reply": answer}
