from pathlib import Path
from datetime import datetime, timezone

async def run(state, *, filepath: str, content: str):
    root = state.get("__project_root")
    if not root:
        return {"reply": "⚠️  No active project – create or open one first."}

    abs_path = Path(root) / filepath
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = f"[{ts}]\n{content}\n"
    abs_path.write_text(body, encoding="utf-8")

    return {
        "reply": f"📝 Wrote `{filepath}` ({len(body.splitlines())} lines).",
        "file_path": str(abs_path)
    }
