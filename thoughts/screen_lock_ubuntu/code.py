async def run(state, **kwargs):
    import subprocess
    # On modern Ubuntu use loginctl
    cmd = ['loginctl', 'lock-session']
    try:
        subprocess.run(cmd, check=True)
        return {"reply": "🔒 Screen locked successfully."}
    except Exception as e:
        return {"reply": f"⚠️ Failed to lock screen: {e}"}