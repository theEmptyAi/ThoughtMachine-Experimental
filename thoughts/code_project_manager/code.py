from pathlib import Path

ROOT = Path("/home/ubuntu/emptyWorkspace").expanduser()

# accept either `project_name=` or the alias `name=` so the planner's JSON
# (… "params": {"name": "<proj>"} …) still works.
async def run(state, *,
              project_name: str | None = None,
              name: str | None = None,
              path: str | None = None):
    # normalise aliases coming from the planner
    if project_name is None:
        project_name = name or path
    """
    • If project_name is given → create/switch.
    • If project_name is None  → report current selection.
    """

    current = state.get("__project_root")

    # Where am I?
    if project_name is None:
        if current:
            return {
                "reply": f"📂 Current project: **{state['__project_name']}**",
                "project_path": current
            }
        return {"reply": "⚠️  No project selected. Say `create project <name>` or `open project <name>`."}

    # Normalize
    safe = project_name.strip().replace(" ", "_")
    proj_path = ROOT / safe

    # Create if missing
    proj_path.mkdir(parents=True, exist_ok=True)

    # Persist
    state["__project_root"] = str(proj_path)
    state["__project_name"] = safe

    return {
        "reply": f"✅ Project **{safe}** ready at `{proj_path}`",
        "project_path": str(proj_path)
    }
