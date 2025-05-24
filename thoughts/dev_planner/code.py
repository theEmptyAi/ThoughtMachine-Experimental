import json

def _wrap(name, params=None):
    return {
        "start": "n0",
        "nodes": {
            "n0": {"thought": name, "params": params or {}, "next": None}
        }
    }

async def run(state, *, goal, catalogue, intent=None):
    """
    • Decide which dev_* thought (or dev_reply) should handle *goal*.
    • Accepts the same contract as the normal planner.
    """
    llm     = state["__llm"]
    system  = state.get("__prompt", "")
    hist    = state.get("__history", "")

    # Ask LLM for a plan
    payload = {"goal": goal, "thoughts": catalogue, "history": hist}
    raw = llm.generate_json(json.dumps(payload, ensure_ascii=False), system_prompt=system)

    try:
        plan = json.loads(raw)
    except Exception:
        # fallback graceful degradation
        return {"plan": {"ok": False, "flow": None, "missing": [], "question": "Sorry, I didn't catch that – could you rephrase?"}}

    # ── SHORT-FORM normalisation ───────────────────────────────
    if isinstance(plan, dict) and ("type" in plan or "name" in plan):
        plan = {"ok": True, "flow": plan, "missing": [], "question": None}

    # If the flow is still a bare dict with name/params ⇒ wrap it
    if plan.get("ok") and isinstance(plan.get("flow"), dict) and "name" in plan["flow"]:
        plan["flow"] = _wrap(plan["flow"]["name"], plan["flow"].get("params"))

    return {"plan": plan}
