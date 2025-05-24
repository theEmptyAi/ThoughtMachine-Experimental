async def run(state, *, text):
    def _lazy_import(name, pip_name=None):
        try:
            return __import__(name)
        except ImportError:
            import subprocess, sys, importlib
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                pip_name or name
            ])
            return importlib.import_module(name)

    # Lazy import the pyttsx3 library
    pyttsx3 = _lazy_import('pyttsx3')

    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return {"success": True, "message": "Text played successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}