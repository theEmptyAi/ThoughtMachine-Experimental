from pathlib import Path

async def run(state, *, filepath: str):
    root = state.get("__project_root")
    if not root:
        return {"reply": "⚠️  No active project – create or open one first."}

    target = Path(root) / filepath
    if not target.exists():
        return {"reply": f"❌ `{filepath}` not found."}

    return {
        "reply": f"```{target.read_text(encoding='utf-8')}```",
        "file_path": str(target)
    }
