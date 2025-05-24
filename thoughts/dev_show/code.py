async def run(state):
    ctx = state.setdefault("__dev", {})
    drafts = ctx.get("drafts", {})
    if not drafts:
        return {"reply": "⚠️ No drafts in the buffer."}
    blobs = "\n\n".join(f"**{k}**\n```{v}```" for k, v in drafts.items())
    return {"reply": blobs}
