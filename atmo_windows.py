"""Native dark title bars. Preserve Windows move/resize/minimize controls."""
import sys


def colorref(hex_color):
    value = hex_color.lstrip('#')
    red, green, blue = (int(value[index:index+2], 16) for index in (0, 2, 4))
    return red | green << 8 | blue << 16


def dark_titlebar(window):
    if sys.platform != 'win32':return False
    try:
        import ctypes
        from ctypes import wintypes
        user32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
        ancestor = user32.GetAncestor
        ancestor.argtypes = (wintypes.HWND, wintypes.UINT)
        ancestor.restype = wintypes.HWND
        handle = ancestor(window.winfo_id(), 2) or window.winfo_id()
        setter = dwm.DwmSetWindowAttribute
        setter.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        setter.restype = ctypes.c_long
        def set_value(attribute, value):
            data = ctypes.c_uint(value)
            return setter(handle, attribute, ctypes.byref(data), ctypes.sizeof(data)) == 0
        dark = set_value(20, 1)
        if not dark:dark = set_value(19, 1)
        # Windows 10 supports immersive dark; exact caption colors are supported
        # on newer Windows. Unsupported attributes are harmless HRESULT failures.
        caption = set_value(35, colorref('#0b1224'))
        set_value(36, colorref('#f5f7ff'))
        set_value(34, colorref('#203452'))
        redraw = user32.SetWindowPos
        redraw.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, ctypes.c_int, wintypes.UINT)
        redraw.restype = wintypes.BOOL
        redraw(handle, None, 0, 0, 0, 0, 0x0037)
        return dark or caption
    except (AttributeError, OSError, TypeError, ValueError):
        return False
