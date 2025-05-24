import difflib, io

async def run(state):
    ctx    = state.setdefault("__dev", {})
    drafts = ctx.get("drafts", {})
    patch  = ctx.pop("pending_patch", None)

    if not patch:
        return {"reply": "⚠️ No patch pending."}

    # Apply diff chunk-by-chunk
    applied = 0
    diff_io = io.StringIO(patch)
    for hdr in difflib.Differ()._parse_unified_diff(diff_io):
        path = hdr[0].path  # path after the b/ prefix
        new_text = "".join(hdr[1])
        drafts[path] = new_text
        applied += 1

    return {"reply": f"✅ Applied patch to {applied} file(s). "
                     "Review with `dev_show` or `/dev_save` to persist."}
