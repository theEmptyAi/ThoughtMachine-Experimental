import json
from datetime import datetime, timezone
import pathlib

def _wrap(thought, params=None):
    return {
        "start": "n0",
        "nodes": {
            "n0": {
                "thought": thought,
                "params": params or {},
                "next": None
            }
        }
    }

async def run(state, *, goal, catalogue, intent=None):
    llm    = state["__llm"]
    system = state["__prompt"]
    hist = state.get("__history", "")
    payload = {
        "goal": goal,
        "thoughts": catalogue,
        "history": hist
    }

    # ── log prompt & model output ────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_dir = pathlib.Path("logs") / "prompts"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"planner_prompt_{ts}.txt"

    # exact bytes fed to the LLM
    log_file.write_text(
        (system or "") + "\n\nPAYLOAD:\n" +
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    raw = llm.generate_json(json.dumps(payload, ensure_ascii=False), system)

    with log_file.open("a", encoding="utf-8") as f:
        f.write("\n\n### LLM OUTPUT ###\n")
        f.write(raw.strip() + "\n")
    
    try:
        plan = json.loads(raw)

        # FIX: Ensure short-form outputs like {"type":"reply"} get wrapped correctly
        if isinstance(plan, dict) and ("type" in plan or "name" in plan):
            plan = {
                "ok": True,
                "flow": plan,
                "missing": [],
                "question": None
            }

        assert isinstance(plan, dict)
    except Exception:
        return {"plan": {"ok": False, "missing": [], "question": "Sorry, could you rephrase?"}}

    flow = plan.get("flow")

    # ---------- NORMALISE FLOW -------------------------------------------
    if plan.get("ok"):
        if isinstance(flow, str):
            plan["flow"] = _wrap("reply" if flow == "reply" else flow,
                                 {"text": goal} if flow == "reply" else None)

        elif isinstance(flow, dict) and flow.get("type") == "reply":
            plan["flow"] = _wrap("reply", {"text": goal})

        elif isinstance(flow, dict) and "name" in flow:
            if flow["name"] == "write_file":
                p = flow.setdefault("params", {})
                if "file_name" in p and "filename" not in p:
                    p["filename"] = p.pop("file_name")
            plan["flow"] = _wrap(flow["name"], flow.get("params"))

        elif isinstance(flow, list) and len(flow) == 1 and "name" in flow[0]:
            step = flow[0]
            plan["flow"] = _wrap(step["name"], step.get("params"))

    plan.setdefault("missing", [])
    plan.setdefault("question", None)
    print("plan : ", plan)
    return {"plan": plan}