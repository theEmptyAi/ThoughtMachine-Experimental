import json

async def run(state, *, history: str = "", text: str = ""):
    llm    = state["__llm"]
    system = state.get("__prompt", "")
    payload = json.dumps({"history": history, "text": text}, ensure_ascii=False)
    raw    = llm.generate_json(payload, system_prompt=system)
    try:
        obj = json.loads(raw)
        intent = obj.get("intent", "generic")
    except Exception:
        intent = "generic"
    return {"intent": intent}