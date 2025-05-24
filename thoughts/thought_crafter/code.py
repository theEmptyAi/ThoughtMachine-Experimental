from pathlib import Path
import json

async def run(state, *, task=None):
    # Initialize the __dev context and drafts buffer
    ctx = state.setdefault("__dev", {})
    drafts = ctx.setdefault("drafts", {})
    step = ctx.get("crafter_step", 0)
    thought_name = ctx.get("thought")

    # Step 1: Ask for the thought name
    if not thought_name and step == 0:
        ctx["crafter_step"] = 1
        return {"reply": "What should we call this new thought? (e.g., `delete_file`)"}

    # Step 2: Store the thought name and ask for the description
    if step == 1:
        thought_name = task.strip().lower()
        ctx["thought"] = thought_name
        ctx["crafter_step"] = 2
        return {"reply": f"Got it, `{thought_name}`! What should this thought do?"}

    # Step 3: Store the description and suggest inputs/outputs
    if step == 2:
        desc = task.strip()
        ctx["desc"] = desc
        # Basic heuristic for inputs/outputs
        inputs = ["filepath"] if "file" in desc.lower() else []
        outputs = ["reply"]
        ctx["suggested_inputs"] = inputs
        ctx["suggested_outputs"] = outputs
        ctx["crafter_step"] = 3
        return {"reply": f"Okay, `{thought_name}` will '{desc}'. I suggest inputs: {inputs}, outputs: {outputs}. Does that sound good? (Say 'yes' or describe changes.)"}

    # Step 4: Generate initial drafts if inputs/outputs are confirmed
    if step == 3:
        if task.lower() in ["yes", "y"]:
            thought_path = f"thoughts/{thought_name}"
            # Generate skill.json (keeping filename for compatibility)
            drafts[f"{thought_path}/skill.json"] = json.dumps({
                "name": thought_name,
                "description": ctx["desc"],
                "inputs": ctx["suggested_inputs"],
                "outputs": ctx["suggested_outputs"],
                "model": "gpt-4o-mini",
                "temperature": 0.7
            }, indent=2)
            # Generate prompt.txt
            drafts[f"{thought_path}/prompt.txt"] = ctx["desc"]
            # Generate code.py
            code = "async def run(state, **kw):\n    pass"
            if ctx["suggested_inputs"]:
                params = ", ".join(f"{inp}=None" for inp in ctx["suggested_inputs"])
                code = (
                    "import os\n\n"
                    f"async def run(state, *, {params}):\n"
                    f"    # TODO: Implement {ctx['desc'].lower()}\n"
                    f"    return {{'reply': 'Not implemented yet'}}"
                )
            drafts[f"{thought_path}/code.py"] = code
            ctx["crafter_step"] = 4
            draft_text = "\n\n".join(f"**{k.split('/')[-1]}**:\n```\n{v}\n```" for k, v in drafts.items() if thought_name in k)
            return {"reply": f"Here’s the initial draft for `{thought_name}`:\n{draft_text}\nDescribe changes (e.g., 'add error handling'), or say `/dev_save` to finish."}
        else:
            ctx["crafter_step"] = 2
            return {"reply": "Let’s try again. What should this thought do?"}

    print("task : ", task)
    # Step 5: Handle modifications or saving
    if step == 4:
        if task.lower().startswith(('/dev_save', '/save')):
            # write all drafts to disk
            saved = 0
            for filepath, content in drafts.items():
                p = Path(filepath)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
                saved += 1
            # reset context for next thought
            ctx.clear()
            return {"reply": f"✅ Saved {saved} file(s). Thought '{thought_name}' ready!"}
        # Pass modifications to dev_reply
        draft_text = "\n\n".join(f"**{k.split('/')[-1]}**:\n```\n{v}\n```" for k, v in drafts.items() if thought_name in k)
        return {"reply": f"Current draft:\n{draft_text}\nFor changes like '{task}', describe them, and I’ll pass to `dev_reply`. Or say `/dev_save` to finish."}

    # Fallback for unexpected state
    return {"reply": "I’m not sure where we are. Say 'start over' to reset."}