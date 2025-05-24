from datetime import datetime, timezone
from pathlib import Path

async def run(state, *, filename: str | None = None,
                       file_name: str | None = None,
                       path: str | None = None,          # ← NEW alias
                       content: str):
    # accept both spellings
    if filename is None:
        filename = file_name or path     # ← fold alias
    if filename is None:
        raise ValueError("write_file needs a filename")

    ts   = datetime.now(timezone.utc).isoformat(timespec="seconds")
    body = f"[{ts}]\n{content}\n"
    path = Path(filename).expanduser().resolve()
    path.write_text(body, encoding="utf-8")
    return {"filepath": str(path)}