"""配置管理 —— 读写 JSON 配置文件、开机自启、单实例锁。

支持 Windows / macOS / Linux：
- 配置目录按平台放：
    Windows : %APPDATA%/GLMQuota
    macOS   : ~/Library/Application Support/GLMQuota
    Linux   : ~/.config/GLMQuota
- 开机自启：
    Windows : 注册表 HKCU\\...\\Run
    macOS   : ~/Library/LaunchAgents/<id>.plist  (LaunchAgent)
    Linux   : ~/.config/autostart/<id>.desktop
- 单实例锁：
    Windows : 命名互斥锁
    macOS/Linux : 配置目录下的锁文件（fcntl 独占锁）
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

APP_NAME = "GLMQuota"

# 默认值
DEFAULTS = {
    "platform": "zhipu",           # "zhipu" | "zai"
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "api_key": "",
    "interval_min": 10,            # 刷新间隔（分钟）
    "auto_start": False,           # 开机自启
    "win_x": 50,                   # 悬浮窗位置
    "win_y": 50,
    "win_visible": True,           # 悬浮窗是否显示
    "theme": "scifi",              # 主题：scifi(科幻) | minimal(极简) | cozy(温暖)
}


def _is_mac() -> bool:
    return sys.platform == "darwin"


def _is_win() -> bool:
    return sys.platform == "win32"


def config_dir() -> Path:
    """按平台返回配置目录。"""
    if _is_win():
        # %APPDATA%\GLMQuota
        base = os.environ.get("APPDATA") or str(Path.home())
    elif _is_mac():
        # ~/Library/Application Support/GLMQuota
        base = os.path.expanduser("~/Library/Application Support")
    else:
        # ~/.config/GLMQuota（遵循 XDG）
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    d = Path(base) / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Config:
    platform: str = DEFAULTS["platform"]
    base_url: str = DEFAULTS["base_url"]
    api_key: str = DEFAULTS["api_key"]
    interval_min: int = DEFAULTS["interval_min"]
    auto_start: bool = DEFAULTS["auto_start"]
    win_x: int = DEFAULTS["win_x"]
    win_y: int = DEFAULTS["win_y"]
    win_visible: bool = DEFAULTS["win_visible"]
    theme: str = DEFAULTS["theme"]

    def to_dict(self) -> dict:
        return asdict(self)


def load() -> Config:
    p = config_path()
    if not p.exists():
        return Config()
    try:
        data = json.loads(p.read_text("utf-8"))
    except Exception:
        return Config()
    # 合并默认值，保证新字段有兜底
    merged = {**DEFAULTS, **data}
    return Config(**{k: merged[k] for k in DEFAULTS})


def save(cfg: Config) -> None:
    config_path().write_text(
        json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), "utf-8")


def is_configured(cfg: Config) -> bool:
    return bool(cfg.api_key and cfg.base_url)


# ── 开机自启 ──────────────────────────────────────────────────
def set_auto_start(enable: bool, exe_path: str | None = None) -> None:
    """跨平台设置开机自启。

    - Windows: 注册表 Run 键
    - macOS  : LaunchAgent plist（用户登录后由 launchd 拉起）
    - Linux  : XDG autostart .desktop 文件
    """
    if _is_win():
        _set_auto_start_win(enable, exe_path)
    elif _is_mac():
        _set_auto_start_mac(enable, exe_path)
    else:
        _set_auto_start_linux(enable, exe_path)


def _launch_target() -> str:
    """自启要执行的目标。
    打包成 .app / .exe 时用 sys.executable；脚本运行时用当前解释器 + app.py。
    """
    exe = sys.executable
    if _is_mac() and exe.endswith(("python", "python3")):
        # 脚本模式：python3 .../app.py
        return f'"{exe}" "{Path(__file__).resolve().parent / "app.py"}"'
    # macOS 打包后的 .app 里 sys.executable 指向可执行文件本体
    return f'"{exe}"'


def _set_auto_start_win(enable: bool, exe_path: str | None) -> None:
    try:
        import winreg
    except ImportError:
        return  # 非 Windows，忽略
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    target = exe_path or sys.executable
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0,
                            winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{target}"')
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


def _set_auto_start_mac(enable: bool, exe_path: str | None) -> None:
    # ~/Library/LaunchAgents/com.glm.quota-monitor.plist
    label = "com.glm.quota-monitor"
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    plist = agents_dir / f"{label}.plist"
    if not enable:
        # 先尝试卸载，再删文件
        try:
            import subprocess
            subprocess.run(["launchctl", "unload", str(plist)],
                           capture_output=True)
        except Exception:
            pass
        plist.unlink(missing_ok=True)
        return
    target = exe_path or _launch_target()
    import shlex
    parts = shlex.split(target)
    program = parts[0]
    args = parts[1:]
    arg_xml = "".join(
        f"        <string>{_xml_escape(a)}</string>\n" for a in args)
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{_xml_escape(program)}</string>
{arg_xml}    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
    plist.write_text(content, "utf-8")
    try:
        import subprocess
        subprocess.run(["launchctl", "load", str(plist)], capture_output=True)
    except Exception:
        pass


def _set_auto_start_linux(enable: bool, exe_path: str | None) -> None:
    autostart = Path.home() / ".config" / "autostart"
    autostart.mkdir(parents=True, exist_ok=True)
    desktop = autostart / f"{APP_NAME}.desktop"
    if not enable:
        desktop.unlink(missing_ok=True)
        return
    target = exe_path or _launch_target()
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name=GLM Quota Monitor\n"
        f"Exec={target}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n",
        "utf-8")


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


# ── 单实例保护 ────────────────────────────────────────────────
# Windows 用命名互斥锁；macOS/Linux 用配置目录下的锁文件 + fcntl 独占锁。
# 模块级持有锁句柄，进程退出时自动释放；第二个实例会拿不到锁。
_single_instance_lock = None  # POSIX: fcntl lock 句柄；Win: mutex 句柄


def acquire_single_instance() -> bool:
    """尝试获取单实例锁。

    返回 True 表示本进程是第一个实例，可以继续运行；
    返回 False 表示已有实例在跑，本进程应立即退出。
    """
    if _is_win():
        return _acquire_single_instance_win()
    return _acquire_single_instance_posix()


def _acquire_single_instance_posix() -> bool:
    global _single_instance_lock
    try:
        import fcntl
        lock_file = config_dir() / "single.lock"
        # 用 r+b 模式：文件不存在则创建，存在则覆盖打开
        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False  # 已有实例持有锁
        # 写入 PID 方便排查
        os.write(fd, str(os.getpid()).encode())
        _single_instance_lock = fd  # 持有到进程退出
        return True
    except Exception:
        # 任何异常都放行，避免锁死导致程序完全无法启动
        return True


def _acquire_single_instance_win() -> bool:
    global _single_instance_lock
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL,
                                          wintypes.LPCWSTR]
        _single_instance_lock = kernel32.CreateMutexW(
            None, False, f"Global\\{APP_NAME}_SingleInstance")
        already_exists = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
        return not already_exists
    except Exception:
        return True
