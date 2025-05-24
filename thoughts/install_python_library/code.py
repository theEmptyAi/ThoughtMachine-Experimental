async def run(state, *, library_name):
    import subprocess
    import sys

    # Use the LLM to determine the pip command
    llm = state["__llm"]
    prompt = state["__prompt"]
    pip_command = await llm.complete(prompt, library_name=library_name)

    try:
        # Execute the pip command
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', library_name], check=True, capture_output=True, text=True)
        return {"success": True, "message": result.stdout}
    except subprocess.CalledProcessError as e:
        return {"success": False, "message": e.stderr}