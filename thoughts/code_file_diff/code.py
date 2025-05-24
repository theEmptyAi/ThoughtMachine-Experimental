import difflib
from pathlib import Path

async def run(state, *, filepath: str, new_content: str):
    root = state.get("__project_root")
    if not root:
        return {"reply": "⚠️  No active project."}

    tgt = Path(root) / filepath
    old = tgt.read_text(encoding="utf-8").splitlines(keepends=True) if tgt.exists() else []
    new = new_content.splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(
        old, new,
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
        n=3
    ))
    state["__pending_patch"] = {"file": str(tgt), "content": new_content}
    return {
        "reply": f"```diff\n{diff}\n```\nSay **apply patch** to accept or **discard** to ignore."
    }
