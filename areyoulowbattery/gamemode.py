"""
Shared Game Mode detection used by the tray, the daemon and the CLI.

Detects a running competitive game (Linux: process scan, Windows: foreground
process + fullscreen window). Browsers and media players in fullscreen are NOT
treated as games, so watching a video never pauses battery polling.
"""

import os
import sys
import time

from areyoulowbattery.logger import logger

GAME_EXE_SIGNATURES = frozenset({
    "cs2", "csgo_linux64", "dota2", "steam_app_",
    "valorant.exe", "overwatch.exe", "r5apex.exe",
    "pubg.exe", "fortnite.exe", "deadlock",
})
GAME_EXE_SUBSTRINGS = ("cs2", "dota2", "steam_app", "deadlock")
WIN_GAME_SUBSTRINGS = (
    "cs2", "csgo", "dota2", "valorant", "r5apex", "overwatch",
    "pubg", "fortnite", "deadlock", "steam_app",
)

# Fullscreen apps that are clearly not games (video, browsing, presentations)
NON_GAME_FULLSCREEN_EXES = (
    "chrome", "chromium", "firefox", "msedge", "brave", "opera", "vivaldi",
    "vlc", "mpv", "mpc-hc", "mpc-be", "potplayer", "wmplayer", "netflix",
    "spotify", "powerpnt", "obs64", "obs32", "teams", "zoom", "discord",
)
WIN_SHELL_CLASSES = ("Progman", "WorkerW", "Shell_TrayWnd", "DV2ControlHost")

_last_check_ts = 0.0
_cached_state = False


def is_non_game_fullscreen_exe(exe_name: str) -> bool:
    """True if the executable is a browser/media/communication app, never a game."""
    lower = (exe_name or "").lower()
    return any(tok in lower for tok in NON_GAME_FULLSCREEN_EXES)


def _linux_game_running(my_pid: int) -> bool:
    try:
        for pid_str in os.listdir("/proc"):
            if not pid_str.isdigit() or int(pid_str) == my_pid:
                continue
            try:
                exe_name = os.path.basename(os.readlink(f"/proc/{pid_str}/exe")).lower()
            except Exception:
                continue
            if exe_name in GAME_EXE_SIGNATURES or any(s in exe_name for s in GAME_EXE_SUBSTRINGS):
                return True
    except Exception:
        pass
    return False


def _windows_game_running(my_pid: int) -> bool:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, 256)
        if class_buf.value in WIN_SHELL_CLASSES:
            return False

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == my_pid:
            return False

        fg_exe = ""
        h_proc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h_proc:
            try:
                exe_buf = ctypes.create_unicode_buffer(1024)
                buf_size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(h_proc, 0, exe_buf, ctypes.byref(buf_size)):
                    fg_exe = os.path.basename(exe_buf.value).lower()
            finally:
                kernel32.CloseHandle(h_proc)

        if fg_exe and any(sig in fg_exe for sig in WIN_GAME_SUBSTRINGS):
            return True

        # Generic fullscreen heuristic, but never for browsers / media players
        if is_non_game_fullscreen_exe(fg_exe):
            return False

        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            screen_w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            screen_h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            if (rect.right - rect.left) >= screen_w and (rect.bottom - rect.top) >= screen_h:
                return True
    except Exception as e:
        logger.debug("Windows game detection check failed: %s", e)
    return False


def is_game_active(ttl: float = 15.0) -> bool:
    """Cached game detection. Result is reused for `ttl` seconds."""
    global _last_check_ts, _cached_state
    now = time.time()
    if now - _last_check_ts < ttl:
        return _cached_state

    _last_check_ts = now
    my_pid = os.getpid()
    if sys.platform == "win32":
        _cached_state = _windows_game_running(my_pid)
    else:
        _cached_state = _linux_game_running(my_pid)
    return _cached_state
