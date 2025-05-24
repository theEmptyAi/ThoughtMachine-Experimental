import json, difflib

async def run(state, *, text=None):
    ctx    = state.setdefault("__dev", {})
    drafts = ctx.get("drafts", {})
    llm    = state["__llm"]
    system = state.get("__prompt", "")

    if not drafts:
        return {"reply": "No drafts loaded. Use `/load <thought>` or `dev_new` first."}

    payload = {"instruction": text, "drafts": drafts}
    new_files = json.loads(llm.generate_json(json.dumps(payload), system_prompt=system))

    # Show diff summary
    summary_lines = []
    for path, new_content in new_files.items():
        old = drafts.get(path, "").splitlines(keepends=True)
        new = new_content.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old, new, fromfile="old", tofile="new", n=3))
        drafts[path] = new_content
        summary_lines.append(f"### {path}\n```diff\n{diff}\n```")

    return {"reply": "Updated drafts:\n" + "\n".join(summary_lines) + "\nSay `/dev_save` when ready."}
