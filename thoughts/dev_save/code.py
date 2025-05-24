import json
from pathlib import Path

async def run(state):
    ctx = state.setdefault("__dev", {})
    drafts = ctx.get("drafts", {})
    if not drafts:
        return {"reply": "Nothing to save."}

    saved = 0
    for path, content in drafts.items():
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not isinstance(content, str):
            # pretty-print JSON/dicts so we still get a usable file
            content = json.dumps(content, indent=2, ensure_ascii=False)
        p.write_text(content, encoding="utf-8")
        saved += 1
    ctx.clear()
    return {"reply": f"✅ Saved {saved} file(s)."}
