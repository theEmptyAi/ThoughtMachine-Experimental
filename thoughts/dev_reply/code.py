from pathlib import Path
import json
async def run(state, *, text):
    llm = state["__llm"]
    system = state["__prompt"]
    conv = state.get("__conv")
    hist = "\n".join(f"{e['sender']}: {e['text']}" for e in conv.history()) if conv else ""
    ctx = state.setdefault("__dev", {})
    drafts = ctx.get("drafts", {})
    thought = ctx.get("thought")

    if not thought:
        return {"reply": "Please load or create a thought first (e.g., `/load <thought>` or `/dev_new <thought>`)."}

    # Check if drafts are empty (new thought) or have content (modification)
    if not any(drafts.values()):  # New thought
        prompt = (
            f"User is creating a new thought '{thought}'.\n"
            f"User says: {text}\n\n"
            "Generate initial content for the thought files. Respond with a JSON object: "
            "{\"thought.json\": \"initial JSON\", \"prompt.txt\": \"initial prompt\", \"code.py\": \"initial code\"}"
        )
    else:  # Modify existing drafts
        prompt = (
            f"User wants to modify the thought '{thought}'.\n"
            f"Current drafts:\n"
            f"thought.json: {drafts.get(str(Path('thoughts') / thought / 'thought.json'), '')}\n"
            f"prompt.txt: {drafts.get(str(Path('thoughts') / thought / 'prompt.txt'), '')}\n"
            f"code.py: {drafts.get(str(Path('thoughts') / thought / 'code.py'), '')}\n\n"
            f"User says: {text}\n\n"
            "Suggest updates to the files. Respond with a JSON object: "
            "{\"thought.json\": \"new content\", \"prompt.txt\": \"new content\", \"code.py\": \"new content\"}"
        )

    updates = json.loads(llm.generate_json(prompt, system))
    for file, content in updates.items():
        if content:
            drafts[str(Path("thoughts") / thought / file)] = content

    draft_text = "\n\n".join(
        f"**{k.split('/')[-1]}**:\n```\n{v}\n```"
        for k, v in drafts.items()
        if k.startswith(str(Path("thoughts") / thought))
    )
    return {"reply": f"Updated draft for '{thought}':\n{draft_text}\nSay `/save` when ready."}