"""配置管理 —— 读写 JSON 配置文件、开机自启。"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
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
}


def config_dir() -> Path:
    """%APPDATA%\\GLMQuota"""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME


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
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2), "utf-8")


def is_configured(cfg: Config) -> bool:
    return bool(cfg.api_key and cfg.base_url)


# ── 开机自启（写注册表 Run 键）─────────────────────────────────
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_auto_start(enable: bool, exe_path: str | None = None) -> None:
    """通过注册表控制开机自启。打包成 exe 后才真正生效。"""
    try:
        import winreg
    except ImportError:
        return  # 非 Windows，忽略

    target = exe_path or sys.executable
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enable:
                winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{target}"')
            else:
                try:
                    winreg.DeleteValue(k, APP_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


# ── 单实例保护（Windows 命名互斥锁）───────────────────────────
# 模块级持有 mutex 句柄，进程退出时自动释放；
# 第二个实例尝试创建同名 mutex 会失败，从而知道已有实例在跑。
_mutex_handle = None


def acquire_single_instance() -> bool:
    """尝试获取单实例锁。

    返回 True 表示本进程是第一个实例，可以继续运行；
    返回 False 表示已有实例在跑，本进程应立即退出。
    非 Windows 平台始终返回 True。
    """
    global _mutex_handle
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        _mutex_handle = kernel32.CreateMutexW(None, False, f"Global\\{APP_NAME}_SingleInstance")
        # CreateMutex 若同名已存在，返回句柄但 last_error = ERROR_ALREADY_EXISTS (183)
        # use_last_error=True 让 ctypes.get_last_error() 正确读取
        already_exists = ctypes.get_last_error() == 183
        return not already_exists
    except Exception:
        # 任何异常都放行，避免锁死导致程序完全无法启动
        return True
