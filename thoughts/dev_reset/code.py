async def run(state, *, force: bool = False):
    """
    Discard every unsaved draft in the developer buffer.

    If the buffer is already empty – and *force* is not set –
    return a gentle notice instead of an unnecessary confirmation.
    """
    ctx = state.setdefault("__dev", {})

    if not ctx or not ctx.get("drafts") and not force:
        return {"reply": "⚠️ No drafts to discard."}

    ctx.clear()
    return {"reply": "🗑️ Draft buffer cleared. All unsaved changes discarded."}
