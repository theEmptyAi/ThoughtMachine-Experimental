import json
async def run(state, *, instruction=None):
    llm    = state["__llm"]
    system = state.get("__prompt", "")
    # Build a little JSON payload so future you can switch to generate_json if needed
    prompt = (
        f"Instruction: {instruction}\n\n"
        "Draft a LinkedIn post or ask a single clarifying question."
    )
    post_or_question = llm.generate_text(prompt, system)
    return {"reply": post_or_question}
