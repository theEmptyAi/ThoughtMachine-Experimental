from pathlib import Path, PurePosixPath

async def run(state, *, glob: str = "**/*"):
    root = state.get("__project_root")
    if not root:
        return {"reply": "⚠️  No active project – create or open one first."}

    root = Path(root)
    files = [
        str(PurePosixPath(p.relative_to(root)))
        for p in root.glob(glob) if p.is_file()
    ]
    if not files:
        return {"reply": "📂 Project is empty."}

    return {
        "reply": "Files:\n" + "\n".join(f"- {f}" for f in files),
        "files": files
    }
