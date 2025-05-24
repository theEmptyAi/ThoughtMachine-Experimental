import asyncio, json, os
from core.thought_factory import ThoughtFactory
from core.executor      import Executor
from core.conversation  import Conversation
from core.pubsub        import hub
import json

import os, json

class Brain:
    def __init__(self, factory=None):
        from core.thought_factory import ThoughtFactory
        self.factory   = factory or ThoughtFactory()
        self.loop      = asyncio.get_event_loop()
        self.listeners = {}
        self.tasks     = {}
        self.convs     = {}
        self.dev_ctx        = {}
        self.active_profile = {}   # cid → profile name
        self.profile_cfg    = {}   # cid → loaded config
        self.dev_flag       = {}   # cid → is-dev-mode?

    # ---------------------------------------------------------------- events
    def add_listener(self, cid, cb):
        self.listeners.setdefault(cid, []).append(cb)

    async def _pub(self, cid, topic, data):
        # publish to websocket hub
        print(f"[BRAIN] Publishing to hub queue: {cid}, topic: {topic}")
        await hub.queue(cid).put({"topic": topic, "data": data})
        print(f"[BRAIN] Published to hub queue successfully: {cid}, topic: {topic}")
        for cb in self.listeners.get(cid, []):
            print(f"[BRAIN] Calling listener callback for: {cid}")
            await cb(topic, data)

  

    def _profile_cfg(self, cid):
        # first time: default to “code_dev”
        if cid not in self.active_profile:
            self.active_profile[cid] = "code_dev"
        name = self.active_profile[cid]
        # cache load
        if cid not in self.profile_cfg:
            path = os.path.join("profiles", f"{name}.json")
            if not os.path.exists(path):
                raise FileNotFoundError(f"Profile '{name}' not found")
            with open(path, "r", encoding="utf-8") as f:
                self.profile_cfg[cid] = json.load(f)

        # ↳ restrict visible thoughts for this conversation
        self.factory.set_pattern(
            cid,
            self.profile_cfg[cid].get("thoughts", ["*"])
        )
        return self.profile_cfg[cid]

    def _apply_profile(self, cid, name):
        # validate & reload
        path = os.path.join("profiles", f"{name}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Profile '{name}' not found")
        with open(path, "r", encoding="utf-8") as f:
            self.profile_cfg[cid]    = json.load(f)
        self.active_profile[cid] = name
        # turn on “dev” thoughts if we’re in thought_dev (or code_dev) profile
        self.dev_flag[cid] = (name in ("thought_dev", "code_dev"))

        # ↳ apply thought filtering for the new profile
        self.factory.set_pattern(
            cid,
            self.profile_cfg[cid].get("thoughts", ["*"])
        )

    async def handle(self, cid: str, user_text: str) -> str:
        dev_ctx = self.dev_ctx.setdefault(cid, {})
        # ensure we have a profile
        cfg = self._profile_cfg(cid)

        # ------------------------------------------------------------------
        # Names the active profile wants to use.  We **must** fetch them
        # before any early-return paths (e.g. greeting/small-talk fast-path)
        # to avoid UnboundLocalError.
        # ------------------------------------------------------------------
        planner_name  = cfg.get("planner", "planner")
        replier_thought = cfg.get("replier", "reply")

        # 1. persist user message
        conv = self.convs.setdefault(cid, Conversation(cid))
        conv.add("user", user_text)

        # handle profile commands -----------------------------
        cmd = user_text.lower().strip()
        if cmd.startswith("/profile"):
            parts = cmd.split(maxsplit=1)
            if len(parts) == 1:
                return f"Current profile: {self.active_profile.get(cid, 'general')}"
            name = parts[1].strip()
            try:
                self._apply_profile(cid, name)
                return f"switched to profile **{name}**."
            except FileNotFoundError:
                return f"unknown profile '{name}'."

        # compatibility: /dev on | off map to profiles
        if cmd == "/dev on":
            self._apply_profile(cid, "thought_dev")
            return "thought-dev profile enabled."
        if cmd == "/dev off":
            self._apply_profile(cid, "general")
            return "Back to general profile."

        # pass the full conversation history instead of just the last 10 turns
        hist = "\n".join(f"{m['sender']}: {m['text']}"
                        for m in conv.history())  # no arg = all messages

        # build a simple thoughts list for the LLM
        dev = self.dev_flag.get(cid, False)
        thoughts = self.factory.describe(cid) if dev else self.factory.describe()
        thoughts_md = "\n".join(f"- **{t['name']}**: {t['desc']}" for t in thoughts)

        shared_state = {
            "__factory": self.factory,
            "__history":  hist,
            "__thoughts_md": thoughts_md,
            "__dev": dev_ctx,
        }

        # ── 0.  classify intent first ───────────────────────────────
        ic_out  = await self.factory.run(
                        "intent_classifier",
                        shared_state,
                        history=hist,
                        text=user_text)
        intent  = ic_out.get("intent", "generic")

        # ── automatic profile toggling ──────────────────────────
        current_profile = self.active_profile.get(cid, "code_dev")  # Default to code_dev
        
        if intent == "dev_on":
            if current_profile == "thought_dev":
                reply = "thought-dev profile is already enabled."
            else:
                self._apply_profile(cid, "thought_dev")
                reply = "thought-dev profile enabled."
            conv.add("assistant", reply)
            return reply
            
        if intent == "dev_off":
            if current_profile != "thought_dev":
                reply = "thought-dev profile is already disabled."
            else:
                self._apply_profile(cid, "code_dev")  # Go to code_dev instead of general
                reply = "Switched to code-dev profile."
            conv.add("assistant", reply)
            return reply
            
        # ← code profile toggles:
        if intent == "code_on":
            if current_profile == "code_dev":
                reply = "Code-dev profile is already enabled."
            else:
                self._apply_profile(cid, "code_dev")
                reply = "Code-dev profile enabled."
            conv.add("assistant", reply)
            return reply
            
        if intent == "code_off":
            if current_profile == "general":
                reply = "General profile is already enabled."
            else:
                self._apply_profile(cid, "general")
                reply = "Back to general profile."
            conv.add("assistant", reply)
            return reply

        # ← general profile toggles:
        if intent == "general_on":
            if current_profile == "general":
                reply = "General profile is already enabled."
            else:
                self._apply_profile(cid, "general")
                reply = "General profile enabled."
            conv.add("assistant", reply)
            return reply

        if intent == "general_off":
            if current_profile == "code_dev":
                reply = "Code-dev profile is already disabled."
            else:
                self._apply_profile(cid, "code_dev")
                reply = "Switched to code-dev profile."
            conv.add("assistant", reply)
            return reply

        # Let greetings / small-talk follow the normal planner pipeline
        # so we still get node events and a single traced reply panel.

        # 2. ask the (dev_)planner for a task-flow
        cat           = self.factory.catalogue(cid)
        plan = (await self.factory.run(
            planner_name, shared_state,
            goal=user_text,
            catalogue=cat,
            intent=intent)              # ← pass hint to planner
        )["plan"]
        await self._pub(cid, "debug", {"stage": "plan", "plan": plan})

        # ── ACCEPT *bare* flows when planner forgets "ok/flow" wrapper ──
        if "ok" not in plan or "flow" not in plan:
            plan = {
                "ok":       True,
                "flow":     plan,       # treat the object itself as the flow
                "missing":  [],
                "question": None,
            }

        # ── NORMALISE short-form flows (strings / {type:name}) ────────────
        if plan.get("ok"):
            flow_data = plan.get("flow")
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

            # plain string → single node
            if isinstance(flow_data, str):
                if flow_data == "reply":
                    plan["flow"] = _wrap(replier_thought, {"text": user_text})
                else:
                    plan["flow"] = _wrap(flow_data)

            # short‐form dict → either {type:…} or {name:…,params:…}
            elif isinstance(flow_data, dict):
                # { "type":"reply" }
                if flow_data.get("type") == "reply":
                    plan["flow"] = _wrap(replier_thought, {"text": user_text})
                # { "name":"thought", "params":{…} }
                elif "name" in flow_data:
                    name   = flow_data["name"]
                    params = flow_data.get("params", {})
                    plan["flow"] = _wrap(name, params)
                # else: assume it's already a full DAG, leave it



        # 3. handle clarification / missing thoughts
        if not plan.get("ok"):
            if plan.get("question"):
                conv.add("assistant", plan["question"])
                return plan["question"]
            if plan.get("missing"):
                miss = [m for m in plan["missing"]
                        if m not in self.factory.catalogue()]
                if miss:
                    msg = f"⚠️ missing thought(s): {', '.join(miss)}."
                    conv.add("assistant", msg)
                    return msg

        # 4. if planner gave us a valid flow, run it (even single-node short-form)
        flow = plan.get("flow")
        if plan.get("ok") and isinstance(flow, dict) and "start" in flow and "nodes" in flow:
            state = {
                "goal":      user_text,
                "__factory": self.factory,
                "__history": hist,
                "__conv":    conv,
                "__cid":     cid,          # Make cid available to executor
                "__dev":     dev_ctx 
            }
            print(f"[BRAIN] Creating executor with flow: {flow}")
            exe = Executor(flow, self.factory, state,
                           lambda t, d: self._pub(cid, t, d))
            print(f"[BRAIN] Created task executor, starting execution")
            self.tasks[cid] = (self.loop.create_task(exe.run()), state)
            print(f"[BRAIN] Created task and stored in tasks dictionary")
            await self._pub(cid, "debug", {"stage": "execute"})
            print(f"[BRAIN] Published debug event, returning task started message")
            return "🚀 task started"

        # 5. planner "junk" fall-through
        junk = (
            "⚠️ Planner produced an invalid flow:\n"
            f"{json.dumps(plan, indent=2)}"
        )
        return junk
