import asyncio

async def run(state, seconds=10, **kw):
    try:
        secs = int(seconds)
    except (ValueError, TypeError):
        secs = 10
    await asyncio.sleep(secs)
    return {"reply": f"Waited for {secs} seconds."}