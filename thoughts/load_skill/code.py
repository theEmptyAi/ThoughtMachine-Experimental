from pathlib import Path

async def run(state, *, thought):
    # Access the __dev context in state, create it if it doesn’t exist
    ctx = state.setdefault("__dev", {})
    # Access or create the drafts buffer
    drafts = ctx.setdefault("drafts", {})
    # Define the thought’s directory path
    root = Path("thoughts") / thought

    # Check if the thought exists
    if not root.exists():
        return {"reply": f"thought '{thought}' not found."}

    # Load each file into the drafts buffer
    for filename in ["thought.json", "prompt.txt", "code.py"]:
        file_path = root / filename
        if file_path.exists():
            drafts[str(file_path)] = file_path.read_text()
        else:
            drafts[str(file_path)] = ""  # Use empty string if file doesn’t exist

    # Track the current thought being edited
    ctx["thought"] = thought
    return {"reply": f"Loaded '{thought}' into the buffer. You can now modify it."}