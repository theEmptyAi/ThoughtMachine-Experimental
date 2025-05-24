import asyncio

class Hub:
    def __init__(self):
        self.queues: dict[str, asyncio.Queue] = {}

    def queue(self, cid: str) -> asyncio.Queue:
        return self.queues.setdefault(cid, asyncio.Queue())

hub = Hub()
