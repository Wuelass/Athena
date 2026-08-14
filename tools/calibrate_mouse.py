import ctypes
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        print("Avertissement : gestion DPI Windows indisponible.")


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


print("Bouge la souris. CTRL+C pour arrêter.")
time.sleep(2)

while True:
    x, y = get_cursor_pos()
    print(f"x={x} y={y}", end="\r")
    time.sleep(0.02)