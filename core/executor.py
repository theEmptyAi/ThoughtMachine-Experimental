class Executor:
    """Walk the DAG produced by planner and execute each node sequentially."""
    def __init__(self, flow, factory, state, pub):
        self.flow     = flow
        self.factory  = factory
        self.state    = state
        self.pub      = pub            # async callback

    async def run(self):
        conv = self.state.get("__conv")   # may be None in tests

        node  = self.flow["start"]
        nodes = self.flow["nodes"]

        while node:
            spec = nodes[node]                        # {thought, params, next}
            await self.pub("node.start",
                           {"id": node, "thought": spec["thought"]})

            print(f"[EXECUTOR] Running thought: {spec['thought']} for node: {node}")
            out = await self.factory.run(
                spec["thought"], self.state, **spec.get("params", {})
            )

            # ── forward captured stdout to listeners ───────────────────
            logs = out.pop("__logs", None)
            if logs:
                await self.pub("node.log", {
                    "id":   node,
                    "thought": spec["thought"],
                    "logs": logs
                })

            self.state.update(out)
            print(f"[EXECUTOR] Output for node {node}: {out}")

            # ── NEW: persist *and publish* assistant replies ──────────
            if "reply" in out and isinstance(out["reply"], str):
                if conv:                       # save to conversation log
                    conv.add("assistant", out["reply"])
                # broadcast so every websocket client receives it
                await self.pub("assistant", out["reply"])
                print(f"[EXECUTOR] Emitted assistant reply: {out['reply'][:60]}…")

            print(f"[EXECUTOR] Publishing node.done event for node: {node}")
            await self.pub("node.done", {"id": node, "out": out})
            print(f"[EXECUTOR] Published node.done event successfully")
            node = spec.get("next")

        print("[EXECUTOR] All nodes processed, publishing task.done event")
        await self.pub("task.done", {"state": self.state})
        print("[EXECUTOR] Published task.done event successfully")
