import json

async def run(state, *, data=None, goal=None):
    """
    • data – any Python object (dict, list, str, …) from the previous node.  
    • goal – original user request (optional; defaults to state['goal']).
    """
    llm    = state["__llm"]
    system = state.get("__prompt", "")

    payload = json.dumps({
        "goal": goal or state.get("goal", ""),
        "data": data
    }, ensure_ascii=False)

    reply = llm.generate_text(payload, system_prompt=system)
    return {"reply": reply}
