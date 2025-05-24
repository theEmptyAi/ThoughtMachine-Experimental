async def run(state, *args):
    pyautogui = _lazy_import('pyautogui')
    screen_width, screen_height = pyautogui.size()
    pyautogui.moveTo(screen_width, 0)
    return {}