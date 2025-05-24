async def run(state, *args):
    import os
    
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

    subprocess = _lazy_import('subprocess')

    try:
        # Open the file explorer and navigate to the specified directory
        subprocess.Popen(['xdg-open', os.path.expanduser('~/Documents/gsm')])
        return {'success': True}
    except Exception as e:
        return {'success': False}