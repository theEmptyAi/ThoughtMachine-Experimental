class Basethought:
    def __init__(self, name, fn, inputs, outputs, desc=""):
        self.name, self.fn = name, fn
        self.inputs, self.outputs, self.desc = inputs, outputs, desc

    async def run(self, state, **kw):
        # every thought now already has  state["__llm"]  and  state["__prompt"]
        return await self.fn(state, **kw)
