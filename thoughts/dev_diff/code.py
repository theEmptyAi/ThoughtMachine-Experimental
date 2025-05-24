import difflib

async def run(state, *, original: str, updated: str, filename: str = "file"):
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        n=3
    )
    return {"diff": "".join(diff)}
