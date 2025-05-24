async def run(state, *args):
    pyautogui = _lazy_import('pyautogui')
    screen_width, screen_height = pyautogui.size()
    pyautogui.moveTo(screen_width / 2, screen_height / 2)
    return {}