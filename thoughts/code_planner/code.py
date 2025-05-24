import json
import logging
from datetime import datetime, timezone
import pathlib

# ─────────────────────────────── ALIAS MAP ───────────────────────────────
alias = {
    "write_file":      "code_file_write",       # safer thought
    "project_creator": "code_project_manager",
    # add other aliases here as needed
}

# ── Setup logger for tracing ───────────────────────────────────────────
logger = logging.getLogger("code_planner")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[CODE_PLANNER] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)


def _wrap_flow(raw_flow):
    """
    Convert a raw list of step dicts into a linear DAG structure, or pass through
    an already valid DAG dict unchanged.
    """
    # If it's already a full DAG, return as-is
    if isinstance(raw_flow, dict) and 'start' in raw_flow and 'nodes' in raw_flow:
        return raw_flow

    # If it's a list of steps, construct a linear DAG
    if isinstance(raw_flow, list):
        nodes = {}
        for idx, step in enumerate(raw_flow):
            node_id = f"n{idx}"
            # If the step is a dict with an 'action' key, use that as the thought name
            if isinstance(step, dict) and 'action' in step:
                # Use global alias map to translate friendly aliases to real thought names
                thought = alias.get(step['action'], step['action'])
                params = {k: v for k, v in step.items() if k != 'action'}
            else:
                # Otherwise treat the step itself (if string) as the thought name
                thought = step if isinstance(step, str) else None
                params = {}

            # Wire up the next pointer
            next_node = f"n{idx+1}" if idx + 1 < len(raw_flow) else None
            nodes[node_id] = {
                "thought": thought,
                "params": params or {},
                "next": next_node
            }

        return {"start": "n0", "nodes": nodes}

    # Otherwise assume it's already valid
    return raw_flow

# ------------------------------------------------------------------------
# Post-processing: ensure every flow that ends with `code_repl` actually
# yields a visible assistant message by appending a `code_reply` step.
# ------------------------------------------------------------------------
def _ensure_repl_reply(flow):
    """
    If the tail node is `code_repl`, append a `code_reply` node that forwards
    its output so the Executor will emit an assistant reply.
    """
    if not isinstance(flow, dict) or "nodes" not in flow:
        return flow

    nodes = flow["nodes"]

    # Locate the tail (node whose `next` is None)
    tail_id = next(
        (nid for nid, spec in nodes.items() if spec.get("next") is None),
        None
    )
    if not tail_id:
        return flow

    tail_spec = nodes[tail_id]
    if tail_spec.get("thought") != "code_repl":
        return flow

    # Create the reply node
    new_id = f"n{len(nodes)}"
    tail_spec["next"] = new_id          # wire old tail → new node

    nodes[new_id] = {
        "thought": "code_reply",
        "params": { "text": f"{{{{{tail_id}.output}}}}" },
        "next":  None
    }
    return flow

async def run(state, *, goal: str = None, catalogue: list = None, intent: str = None):
    llm    = state["__llm"]
    system = state.get("__prompt", "")
    now    = datetime.now(timezone.utc).isoformat()

    # ── 0-A • Fast-path: small-talk / greetings ─────────────────────────────
    # The intent_classifier is already executed by Brain before calling us.
    if intent in ("greeting", "smalltalk", "generic"):
        logger.debug(f"Fast-path for intent '{intent}' – use chat replier.")
        return {"plan": {
            "ok": True,
            "flow": { "type": "reply" },
            "missing": [],
            "question": None
        }}

    # ── Intercept capability queries → list thoughts ────────────────────────────
    if goal:
        gl = goal.lower().strip()
        capability_queries = [
            "what can you do", "what are your thoughts",
            "list thoughts", "available thoughts", "what and all you can do"
        ]
        if any(gl.startswith(q) for q in capability_queries):
            logger.debug(f"Capability query detected: '{goal}'")
            return {
                "plan": {
                    "ok":       True,
                    "flow":     {"name": "thought_list"},
                    "missing":  [],
                    "question": None
                }
            }

    # For simple greetings, return a reply type flow to use the profile's replier
    simple_greetings = ["hi", "hello", "hey", "greetings", "hola", "howdy"]
    if goal and goal.lower().strip() in simple_greetings:
        return {
            "plan": {
                "ok": True,
                "flow": {"type": "reply"},
                "missing": [],
                "question": None
            }
        }

    query = {
        "role": "planner",
        "name": "code_planner",
        "time": now,
        "system": system,
        "payload": json.dumps({"goal": goal, "thoughts": catalogue}, ensure_ascii=False)
    }

    raw = await llm.plan(query)

    # ── 0. NORMALISE model output so we *always* end up with {ok,flow,…} ──
    if (
        "plan" in raw                         # model used the cheap wrapper
        and "ok" not in raw and "flow" not in raw
    ):
        inner = raw["plan"]

        # • plan is a step-LIST  → turn it into a linear DAG
        if isinstance(inner, list):
            flow = _wrap_flow(inner)

        # • plan is a short-form DICT ({"type":"reply"} or {"name":…})
        elif isinstance(inner, dict):
            flow = inner

        # • plan is a plain STRING → treat it like {"type":"reply"}
        else:
            flow = {"type": "reply", "text": str(inner)}

        plan = {
            "ok":       True,
            "flow":     flow,
            "missing":  [],
            "question": None
        }
    else:
        # Model already followed the full schema
        plan = raw

    # ─── 1.  UNWRAP  { "plan": [...] }  RESPONSES  ────────────────────
    if plan.get("ok") and isinstance(plan.get("flow"), dict):
        inner = plan["flow"]
        if "plan" in inner and isinstance(inner["plan"], list):
            plan["flow"] = _wrap_flow(inner["plan"])        # <── new
            plan["flow"] = _ensure_repl_reply(plan["flow"]) # <── keeps chatty REPLs readable

    # ───────────── 2.  ALIAS TRANSLATION FOR SAFER thought CALLS ─────────
    if isinstance(plan.get("flow"), dict):
        root = plan["flow"]
        thought = root.get("thought")
        if thought in alias:
            new_thought = alias[thought]
            root["thought"] = new_thought
            params = root.setdefault("params", {})
            if new_thought == "code_file_write":
                # Normalize param keys
                params["filepath"] = params.pop("path", params.pop("filename", ""))

    # ─────────────────────── FLOW UNWRAPPING ───────────────────────
    if "ok" not in plan or "flow" not in plan:
        plan = {
            "ok": True,
            "flow": plan
        }

    # Plan object is complete ─ make sure Brain gets {"plan": …}

    # If earlier branches have already wrapped, let them pass through.
    if isinstance(plan, dict) and "plan" in plan and ("ok" in plan or "flow" in plan):
        return plan

    # Otherwise wrap the raw plan object
    return {"plan": plan}
