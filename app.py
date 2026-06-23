"""GLM 额度助手 —— 系统托盘 + 桌面悬浮窗。

- 启动后进入系统托盘
- 左键点托盘：显示/隐藏悬浮窗
- 右键托盘菜单：显示/隐藏、立即刷新、设置、开机自启、退出
- 后台线程定时查询，UI 不卡死
"""
from __future__ import annotations

import sys
import threading
from datetime import datetime
from tkinter import FALSE, TRUE, BOTH, X, LEFT, RIGHT, FLAT
import tkinter as tk
from tkinter import messagebox

import config as cfg_mod
import quota

# ──────────────────────────────────────────────────────────────
# 主题系统：三套配色（科幻 / 极简 / 温暖）
#
# 设计要点：颜色常量名（BG/FG/ACCENT/...）全程序通用，由 apply_theme()
# 在启动时按 cfg.theme 重新赋值。由于主题"重启生效"，所有引用这些常量
# 的 widget 创建代码零改动。
# CAPSULE 决定折叠胶囊的渲染样式：dots=发光点+迷你条 / text=纯文字 / block=柔和色块
# ──────────────────────────────────────────────────────────────
THEMES = {
    "scifi": {  # 科幻风：深空黑底 + 青色霓虹
        "BG": "#0d1117", "BG_CARD": "#161b22", "BG_BAR_TRACK": "#1f2630",
        "FG": "#e6edf3", "FG_DIM": "#7d8590", "ACCENT": "#00e5ff",
        "COLOR_OK": "#00ffa3", "COLOR_WARN": "#ffb020", "COLOR_DANGER": "#ff3b6b",
        "HOVER": "#21262d", "EDGE": "#2a3441",
        "CAPSULE": "dots",
    },
    "minimal": {  # 极简风：白底冷调，类 macOS 原生
        "BG": "#ffffff", "BG_CARD": "#f5f5f7", "BG_BAR_TRACK": "#e5e5ea",
        "FG": "#1d1d1f", "FG_DIM": "#86868b", "ACCENT": "#007aff",
        "COLOR_OK": "#34c759", "COLOR_WARN": "#ff9500", "COLOR_DANGER": "#ff3b30",
        "HOVER": "#e5e5ea", "EDGE": "#d1d1d6",
        "CAPSULE": "text",
    },
    "cozy": {  # 温暖风：米黄书信，柔和舒适
        "BG": "#fdf6e3", "BG_CARD": "#f5ecd7", "BG_BAR_TRACK": "#ebe0c4",
        "FG": "#6b4423", "FG_DIM": "#a8896c", "ACCENT": "#d97706",
        "COLOR_OK": "#65a30d", "COLOR_WARN": "#d97706", "COLOR_DANGER": "#dc2626",
        "HOVER": "#f5ecd7", "EDGE": "#d6c9a8",
        "CAPSULE": "block",
    },
}

# 模块级配色常量（由 apply_theme 赋值；初值取科幻风，保证 import 即可用）
BG = "#0d1117"
BG_CARD = "#161b22"
BG_BAR_TRACK = "#1f2630"
FG = "#e6edf3"
FG_DIM = "#7d8590"
ACCENT = "#00e5ff"
COLOR_OK = "#00ffa3"
COLOR_WARN = "#ffb020"
COLOR_DANGER = "#ff3b6b"
HOVER = "#21262d"
EDGE = "#2a3441"
# 折叠胶囊样式
CAPSULE_STYLE = "dots"

# Windows 胶囊形状专用"魔法色"：用作窗口背景 + transparentcolor，
# 让无边框窗口矩形四角透明，只露出胶囊/卡片内容。
# 选品红色（#ff00ff）因为它是 UI 里几乎不会出现的颜色，安全可透明。
# macOS 不需要这个（原生支持任意形状窗口），所以只有 Windows 用。
WIN_MAGIC_PINK = "#ff00ff"


def apply_theme(name: str = "scifi") -> None:
    """按主题名重新赋值模块级配色常量。须在任何 Toplevel 创建前调用。"""
    global BG, BG_CARD, BG_BAR_TRACK, FG, FG_DIM, ACCENT
    global COLOR_OK, COLOR_WARN, COLOR_DANGER, HOVER, EDGE, CAPSULE_STYLE
    t = THEMES.get(name, THEMES["scifi"])
    BG = t["BG"]
    BG_CARD = t["BG_CARD"]
    BG_BAR_TRACK = t["BG_BAR_TRACK"]
    FG = t["FG"]
    FG_DIM = t["FG_DIM"]
    ACCENT = t["ACCENT"]
    COLOR_OK = t["COLOR_OK"]
    COLOR_WARN = t["COLOR_WARN"]
    COLOR_DANGER = t["COLOR_DANGER"]
    HOVER = t["HOVER"]
    EDGE = t["EDGE"]
    CAPSULE_STYLE = t["CAPSULE"]


def apply_window_transparency(win, want_magic_bg: bool = True) -> None:
    """让无边框窗口在 Windows 上实现"任意形状"。

    macOS 原生支持任意形状窗口（背景透明区域天然不捕获点击/不渲染），
    无需处理。Windows 的 tkinter 不支持窗口级真透明，但提供
    `-transparentcolor` 属性：把它设为某颜色，窗口上该颜色的像素就会
    完全透明（鼠标穿透）。

    做法：把窗口背景设为魔法品红色 WIN_MAGIC_PINK，再设 -transparentcolor
    为同一颜色。这样窗口矩形的"空白四角"（品红）变透明，只留下实际绘制的
    胶囊/卡片内容，从而在 Windows 上也呈现胶囊形。

    参数 want_magic_bg：True=用魔法色做背景（用于胶囊/圆角卡片）；False=用
    主题 BG 做背景（用于矩形全填充窗口，如主悬浮条，不需要异形）。
    """
    if not IS_WIN:
        return
    bg = WIN_MAGIC_PINK if want_magic_bg else BG
    try:
        win.configure(bg=bg)
        if want_magic_bg:
            win.attributes("-transparentcolor", WIN_MAGIC_PINK)
    except tk.TclError:
        # 极旧 Windows 或非 win32 预览，忽略
        pass


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """用平滑多边形在 Canvas 上画圆角矩形（tkinter Frame 不支持圆角）。

    返回 polygon item id。两个窗口类（MiniBar / FloatingBar）共用。
    r 取高度一半即为两端半圆的真正胶囊形。
    """
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


# ──────────────────────────────────────────────────────────────
# 平台相关：字体 / 托盘可用性
# ──────────────────────────────────────────────────────────────
# Windows 原生用 Segoe UI；等宽字用 Cascadia Code（VS Code 同款，比 Consolas
# 在小字号下清晰得多），不存在时 tkinter 自动回退。macOS/Linux 用系统自带字体。
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
if IS_WIN:
    FONT_UI = "Segoe UI"
    FONT_UI_SEMI = "Segoe UI Semibold"
    # Cascadia Code 是微软新等宽字体，小字号下比 Consolas 清晰；
    # 若未安装 tkinter 会回退到系统默认等宽字体
    FONT_MONO = "Cascadia Code"
elif IS_MAC:
    FONT_UI = "Helvetica Neue"
    FONT_UI_SEMI = "Helvetica Neue Bold"
    FONT_MONO = "Menlo"
else:
    FONT_UI = "DejaVu Sans"
    FONT_UI_SEMI = "DejaVu Sans"
    FONT_MONO = "DejaVu Sans Mono"

# Windows 上 tkinter 字号单位是像素，GDI 对小字号抗锯齿差，7-8px 会糊。
# macOS 字号单位是点（pt），天然比同数值的 px 大且清晰。
# 用 fs() 包装所有字号：Windows 上整体 +2 并设最小值 9，补偿渲染差异。
_FONT_BUMP = 2 if IS_WIN else 0
_FONT_MIN = 9 if IS_WIN else 1


def fs(size: int) -> int:
    """字号缩放：Windows 上 +2 且不低于 9，其他平台原样返回。"""
    return max(_FONT_MIN, size + _FONT_BUMP)


def _lighten(hex_color: str, amt: int = 40) -> str:
    """简单提亮颜色（按钮悬停用）。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = min(255, r + amt), min(255, g + amt), min(255, b + amt)
    return f"#{r:02x}{g:02x}{b:02x}"


# ──────────────────────────────────────────────────────────────
# 1. 图标生成（程序内用 Pillow 画一个简约闪电图标）
# ──────────────────────────────────────────────────────────────
def make_icon():
    from PIL import Image, ImageDraw

    def draw(size: int) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 圆角底
        margin = max(1, size // 16)
        d.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=size // 5, fill=(79, 157, 255, 255)
        )
        # 闪电
        cx, cy = size / 2, size / 2
        s = size * 0.28
        bolt = [
            (cx + s * 0.2, cy - s * 1.1),
            (cx - s * 0.5, cy + s * 0.1),
            (cx - s * 0.05, cy + s * 0.1),
            (cx - s * 0.3, cy + s * 1.1),
            (cx + s * 0.55, cy - s * 0.2),
            (cx + s * 0.05, cy - s * 0.2),
        ]
        d.polygon(bolt, fill=(255, 255, 255, 255))
        return img

    return draw(64)


# ──────────────────────────────────────────────────────────────
# 2a. 折叠态迷你胶囊（悬浮条收起后留在屏幕上的小标识）
# ──────────────────────────────────────────────────────────────
class MiniBar(tk.Toplevel):
    """悬浮条折叠后的迷你胶囊。三个主题共用同一布局：

    两个迷你环 —— 左：5 小时限额，右：周限额。环心显示百分比，
    环下方小标签区分维度。没有重复文字，一眼看清两个核心指标。

    交互：左键单击展开、左键拖动移动、右键出菜单、每秒自刷新。
    """

    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        self._moved = False
        self.style = CAPSULE_STYLE

        self.overrideredirect(TRUE)
        self.attributes("-topmost", TRUE)
        try:
            self.attributes("-alpha", 0.88)
        except tk.TclError:
            pass
        # Windows 用魔法色背景 + transparentcolor 实现胶囊异形；
        # macOS 直接用主题 BG（原生支持任意形状窗口）
        apply_window_transparency(self, want_magic_bg=IS_WIN)
        if not IS_WIN:
            self.configure(bg=BG)

        # 按样式构建不同容器底色（布局结构统一：两个迷你环）
        self._interactive = []
        if self.style == "block":
            self._build()
        else:
            self._build()

        # 绑交互
        for w in self._interactive:
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._on_click)
            w.bind("<Double-Button-1>", lambda e: self.app.show_floating())
            w.bind("<ButtonPress-3>", self._ctx)
            w.bind("<ButtonPress-2>", self._ctx)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

        self.refresh()

    def _build(self):
        """统一布局：两个迷你环（5H / 周），各带下方小标签。

        Windows 关键：窗口背景为魔法品红色 + -transparentcolor，
        矩形四角透明。胶囊本体用一个 Canvas 画圆角矩形（_round_rect），
        Canvas 透明区域（圆角外）保留魔法色 → 也透明。
        这样 Windows 上也呈现真正的胶囊形，和 macOS 一致。
        """
        bg_card = BG_CARD if self.style == "block" else BG
        # Windows 上窗口背景已是魔法色（透明），内部 Canvas 需要透明背景
        canvas_bg = WIN_MAGIC_PINK if IS_WIN else bg_card

        # 胶囊本体 Canvas：负责画圆角矩形底（Windows 异形的关键）
        self._capsule_w = 120
        self._capsule_h = 64
        self.canvas = tk.Canvas(self, width=self._capsule_w,
                                height=self._capsule_h, bg=canvas_bg,
                                bd=0, highlightthickness=0)
        self.canvas.pack()
        # 画胶囊底（圆角矩形，胶囊形：r 取高度一半即为两端半圆）
        r = self._capsule_h // 2 - 2
        round_rect(self.canvas, 1, 1, self._capsule_w - 1,
                   self._capsule_h - 1, r, fill=bg_card, outline=EDGE)

        # 在 Canvas 上放置两个迷你环（用 create_window 嵌套）
        # 左：5H 环
        left = tk.Frame(self.canvas, bg=bg_card)
        self.ring5h = tk.Canvas(left, width=32, height=32, bg=bg_card,
                                bd=0, highlightthickness=0)
        self.ring5h.pack()
        tk.Label(left, text="5H", bg=bg_card, fg=FG_DIM,
                 font=(FONT_MONO, fs(7))).pack(anchor="center")
        self.canvas.create_window(36, self._capsule_h // 2, window=left)

        # 右：周环
        right = tk.Frame(self.canvas, bg=bg_card)
        self.ring_week = tk.Canvas(right, width=32, height=32, bg=bg_card,
                                   bd=0, highlightthickness=0)
        self.ring_week.pack()
        tk.Label(right, text="周", bg=bg_card, fg=FG_DIM,
                 font=(FONT_MONO, fs(7))).pack(anchor="center")
        self.canvas.create_window(84, self._capsule_h // 2, window=right)

        self._interactive = [self, self.canvas, left, right,
                             self.ring5h, self.ring_week]

    def show_at(self, x, y):
        try:
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass
        self.deiconify()
        self.lift()
        self._schedule()

    def pos(self):
        return self.winfo_x(), self.winfo_y()

    def refresh(self):
        """刷新两个迷你环：5H 用量 + 周用量。"""
        data = self.app.last_data
        # 5H
        if data.is_empty:
            p5, f5 = 0.0, FG_DIM
        elif data.error:
            p5, f5 = 0.0, COLOR_DANGER
        else:
            p5 = data.token_5h.pct if data.token_5h else 0
            _, f5 = FloatingBar._grade(p5)
        # 周
        if data.is_empty:
            pw, fw = 0.0, FG_DIM
        elif data.error:
            pw, fw = 0.0, COLOR_DANGER
        else:
            pw = data.token_weekly.pct if data.token_weekly else 0
            _, fw = FloatingBar._grade(pw)

        self._draw_mini_ring(self.ring5h, p5, f5)
        self._draw_mini_ring(self.ring_week, pw, fw)

    def _draw_mini_ring(self, canvas, pct, fill):
        """迷你环形进度（小尺寸版，与主表盘同款画法）。"""
        canvas.delete("all")
        d = 36
        pad = 4
        x1, y1, x2, y2 = pad, pad, d - pad, d - pad
        thick = 3
        # 背景轨道
        canvas.create_arc(x1, y1, x2, y2, start=90, extent=-359,
                          style="arc", width=thick, outline=BG_BAR_TRACK)
        # 进度弧
        if pct > 0:
            canvas.create_arc(x1, y1, x2, y2, start=90,
                              extent=-359 * min(pct, 100) / 100,
                              style="arc", width=thick, outline=fill)
        # 环心百分比
        cx = d / 2
        canvas.create_text(cx, cx, text=f"{pct:.0f}", fill=fill,
                           font=(FONT_MONO, fs(9), "bold"))

    def _schedule(self):
        """每秒从主应用同步数据（独立于主刷新周期）。"""
        try:
            if self.winfo_exists():
                self.refresh()
                self.after(1000, self._schedule)
        except Exception:
            pass

    def _on_press(self, e):
        self._drag_dx = e.x
        self._drag_dy = e.y
        self._press_win_x = self.winfo_x()
        self._press_win_y = self.winfo_y()
        self._moved = False

    def _on_drag(self, e):
        x = self.winfo_x() + e.x - self._drag_dx
        y = self.winfo_y() + e.y - self._drag_dy
        if (abs(x - self._press_win_x) > 4
                or abs(y - self._press_win_y) > 4):
            self._moved = True
        self.geometry(f"+{x}+{y}")

    def _on_click(self, e):
        if not self._moved:
            self.app.show_floating()

    def _ctx(self, e):
        self.app.floating._show_ctx_menu(e)


# ──────────────────────────────────────────────────────────────
# 2. 桌面悬浮窗
# ──────────────────────────────────────────────────────────────
class FloatingBar(tk.Toplevel):
    """无边框、半透明、置顶、可拖动的桌面悬浮小条（科幻风）。"""

    WIDTH = 300

    def __init__(self, master, app: "App"):
        super().__init__(master)
        self.app = app
        self.cfg = app.cfg

        # 窗口外观
        self.overrideredirect(TRUE)          # 无边框
        self.attributes("-topmost", TRUE)    # 置顶
        try:
            self.attributes("-alpha", 0.88)  # 半透明（玻璃感）
        except tk.TclError:
            pass
        if sys.platform == "win32":
            self.attributes("-toolwindow", TRUE)
        self.configure(bg=BG)
        self.minsize(self.WIDTH, 10)

        # 位置
        try:
            self.geometry(f"+{self.cfg.win_x}+{self.cfg.win_y}")
        except Exception:
            pass

        # 拖动 / 单击折叠支持（实际绑定在 _bind_interaction 里，遍历所有子 widget）
        self._drag_dx = 0
        self._drag_dy = 0
        self._moved = False
        # 右键菜单（窗口级即可，子 widget 不抢右键）
        self.bind("<ButtonPress-3>", self._show_ctx_menu)
        self.bind("<ButtonPress-2>", self._show_ctx_menu)

        # 存进度条 canvas 引用
        self._bars = {}
        self._build_ui()
        # 把单击折叠 / 拖动绑定到所有子 widget（任意位置都可触发）
        self._bind_interaction()
        # 确保宽度已知后再画
        self.after(150, self._force_redraw)

    def _build_ui(self):
        # 外层卡片：带描边的容器
        card = tk.Frame(self, bg=BG, highlightbackground=EDGE,
                        highlightthickness=1, bd=0)
        card.pack(fill=BOTH, expand=True, padx=0, pady=0)

        # 顶部强调装饰线（科幻风 HUD 顶栏）
        top_accent = tk.Frame(card, bg=ACCENT, height=2)
        top_accent.pack(fill=X)

        # 标题行
        head = tk.Frame(card, bg=BG)
        head.pack(fill=X, padx=16, pady=(10, 2))
        self.title_lbl = tk.Label(
            head, text=self._head_text(), bg=BG, fg=ACCENT,
            font=(FONT_UI_SEMI, fs(11)), anchor="w"
        )
        self.title_lbl.pack(side=LEFT)
        close_btn = tk.Label(
            head, text="✕", bg=BG, fg=FG_DIM,
            font=(FONT_UI, fs(10)), cursor="hand2"
        )
        close_btn.pack(side=RIGHT)
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=FG))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=FG_DIM))

        # 分隔线
        tk.Frame(card, bg=EDGE, height=1).pack(fill=X, padx=16, pady=(6, 8))

        # 进度区
        body = tk.Frame(card, bg=BG)
        body.pack(fill=BOTH, padx=16, pady=(0, 8))
        self.token_row = self._make_row(body, "TOKEN · 5H WINDOW", is_token=True)
        self.week_row = self._make_row(body, "TOKEN · WEEKLY", is_token=True)
        self.mcp_row = self._make_row(body, "MCP · MONTHLY", is_token=False)

        # 5h 重置倒计时高亮区
        self.reset_zone = tk.Frame(card, bg=BG)
        self.reset_zone.pack(fill=X, padx=16, pady=(4, 8))
        self._build_reset_zone()

        # 底部状态行
        self.status_lbl = tk.Label(
            card, text="⟳ 初始化中…", bg=BG, fg=FG_DIM,
            font=(FONT_MONO, fs(8)), anchor="w"
        )
        self.status_lbl.pack(fill=X, padx=16, pady=(0, 10))

    def _build_reset_zone(self):
        """5h 重置倒计时：单独的高亮信息块。"""
        z = self.reset_zone
        for w in z.winfo_children():
            w.destroy()
        # 横向布局：[图标][标签文字] ............ [倒计时大字]
        wrap = tk.Frame(z, bg=BG_BAR_TRACK, highlightbackground=EDGE,
                        highlightthickness=1)
        wrap.pack(fill=X)
        # 左侧
        left = tk.Frame(wrap, bg=BG_BAR_TRACK)
        left.pack(side=LEFT, padx=12, pady=8)
        tk.Label(left, text="◷  RESET IN", bg=BG_BAR_TRACK, fg=FG_DIM,
                 font=(FONT_MONO, fs(8))).pack(anchor="w")
        # 副标题（窗口未激活时会改成提示文字）
        self.reset_sub_var = tk.StringVar(value="5H 窗口重置倒计时")
        tk.Label(left, textvariable=self.reset_sub_var, bg=BG_BAR_TRACK, fg=FG,
                 font=(FONT_UI, fs(8)), anchor="w").pack(anchor="w")
        # 右侧倒计时
        self.reset_cd_var = tk.StringVar(value="-- : -- : --")
        tk.Label(wrap, textvariable=self.reset_cd_var, bg=BG_BAR_TRACK,
                 fg=ACCENT, font=(FONT_MONO, fs(16), "bold"),
                 padx=14).pack(side=RIGHT)

    def _make_row(self, parent, label_text, is_token=True):
        """横向卡片布局：左环形表盘 + 右文字区。"""
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=X, pady=(0, 8))

        # 左：环形进度表盘
        ring = tk.Canvas(row, width=60, height=60, bg=BG, bd=0,
                         highlightthickness=0)
        ring.pack(side=LEFT, padx=(0, 10))
        self._bars[label_text] = ring   # 复用 _bars 字典（key 不变）

        # 右：文字区
        right = tk.Frame(row, bg=BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)
        tk.Label(right, text=label_text, bg=BG, fg=FG_DIM,
                 font=(FONT_MONO, fs(8))).pack(anchor="w")
        pct_var = tk.StringVar(value="0%")
        self._pct_labels = getattr(self, "_pct_labels", {})
        pct_lbl = tk.Label(right, textvariable=pct_var, bg=BG, fg=FG,
                           font=(FONT_UI_SEMI, fs(13), "bold"))
        pct_lbl.pack(anchor="w")
        # 副文本（用量明细 / 重置钟点）
        sub_var = tk.StringVar(value="　")
        tk.Label(right, textvariable=sub_var, bg=BG, fg=FG_DIM,
                 font=(FONT_MONO, fs(8)), anchor="w", justify=LEFT
                 ).pack(anchor="w", pady=(2, 0))

        return {"pct": pct_var, "pct_lbl": pct_lbl, "sub": sub_var,
                "bar_key": label_text}

    def _head_text(self):
        lvl = self.app.last_data.level.upper() if self.app.last_data.level else "—"
        plat = "智谱" if self.cfg.platform == "zhipu" else "Z.AI"
        return f"◈ GLM · {plat} · {lvl}"

    def _bind_interaction(self):
        """把单击折叠 / 拖动绑定到所有子 widget，使悬浮条任意位置可点。

        - 按下记录起点；移动超过阈值才算拖动（避免误触）。
        - 松开时若未拖动 → 视为单击 → 折叠成胶囊。
        """
        widgets = [self]
        try:
            widgets.extend(self.winfo_children())
            # 再往下一层（card 里的 head/body/status 等）
            for child in list(self.winfo_children()):
                widgets.extend(child.winfo_children())
        except Exception:
            pass
        for w in widgets:
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", self._on_release)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    def _on_press(self, e):
        # 用 root 坐标作为拖动基准，避免按到子 widget 时 e.x 是相对坐标
        self._drag_start_x = e.x_root - self.winfo_x()
        self._drag_start_y = e.y_root - self.winfo_y()
        # 记录按下时的窗口绝对位置，用于判断是否真的移动了
        self._press_win_x = self.winfo_x()
        self._press_win_y = self.winfo_y()
        self._moved = False

    def _on_drag(self, e):
        x = e.x_root - self._drag_start_x
        y = e.y_root - self._drag_start_y
        # 移动超过阈值才算拖动，防止单击被误判
        if (abs(x - self._press_win_x) > 4
                or abs(y - self._press_win_y) > 4):
            self._moved = True
        self.geometry(f"+{x}+{y}")

    def _on_release(self, e):
        # 未拖动 → 单击 → 折叠
        if not self._moved:
            self.hide()

    def _show_ctx_menu(self, e):
        """悬浮窗右键菜单：没有系统托盘时也能操作。"""
        m = tk.Menu(self, tearoff=0, bg=BG_CARD, fg=FG,
                    activebackground=HOVER, activeforeground=FG,
                    borderwidth=0, font=(FONT_UI, fs(10)))
        shown = self.winfo_viewable()
        m.add_command(label="隐藏悬浮条" if shown else "显示悬浮条",
                      command=lambda: self.app.toggle_floating())
        m.add_command(label="立即刷新", command=self.app.refresh_now)
        m.add_command(label="设置…", command=self.app.open_settings)
        m.add_separator()
        autostart_label = ("✓ " if self.app.cfg.auto_start else "") + "开机自启"
        m.add_command(label=autostart_label,
                      command=self.app.toggle_autostart)
        m.add_separator()
        m.add_command(label="退出", command=self.app.quit)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def hide(self):
        """折叠成小药丸（不彻底消失，便于重新展开）。"""
        self.cfg.win_visible = False
        cfg_mod.save(self.cfg)
        self._collapse()

    def show(self):
        self.cfg.win_visible = True
        cfg_mod.save(self.cfg)
        self._expand()

    def _collapse(self):
        """折叠成右上角小药丸：点击展开，右键菜单。"""
        if getattr(self, "_mini", None) is not None:
            return  # 已经折叠
        # 记住当前位置，药丸显示在主窗口位置附近
        try:
            self.cfg.win_x = self.winfo_x()
            self.cfg.win_y = self.winfo_y()
            cfg_mod.save(self.cfg)
        except Exception:
            pass
        self.withdraw()
        mini = MiniBar(self.master, self.app)
        mini.show_at(self.cfg.win_x, self.cfg.win_y)
        self._mini = mini

    def _expand(self):
        """从小药丸恢复成完整悬浮条。"""
        mini = getattr(self, "_mini", None)
        if mini is not None:
            # 药丸拖动后，把新位置同步回主窗口
            try:
                self.cfg.win_x, self.cfg.win_y = mini.pos()
                cfg_mod.save(self.cfg)
                self.geometry(f"+{self.cfg.win_x}+{self.cfg.win_y}")
            except Exception:
                pass
            mini.destroy()
            self._mini = None
        self.deiconify()
        self.lift()
        self.after(120, self._force_redraw)
        # 重启倒计时链条（窗口隐藏期间 after 链可能已断）
        self.after(150, self._restart_countdown)

    def winfo_viewable(self):  # type: ignore[override]
        """折叠态也算"可见"（有药丸在屏幕上）。"""
        if getattr(self, "_mini", None) is not None:
            return True
        return super().winfo_viewable()

    def _restart_countdown(self):
        """窗口重新显示时重启每秒走表的倒计时。"""
        ts = getattr(self, "_reset_ts", None)
        if ts and self.winfo_viewable():
            self._tick_reset()

    # ── 颜色分级 ──
    @staticmethod
    def _grade(pct):
        if pct >= 90:
            return COLOR_DANGER, COLOR_DANGER
        if pct >= 70:
            return COLOR_WARN, COLOR_WARN
        return COLOR_OK, COLOR_OK

    # ── 分级警示动画（≥90% 危险项闪烁）──
    _warning_after = None      # after 句柄
    _warning_phase = False     # 闪烁相位（True=危险色，False=暗色）

    def _check_warning(self):
        """检测是否有指标 ≥90%，启停警示闪烁。"""
        danger = []
        for name, pct in (("token", self._last_token_pct),
                          ("week", self._last_week_pct),
                          ("mcp", self._last_mcp_pct)):
            if pct >= 90:
                danger.append(name)
        if danger:
            self._danger_items = danger
            if self._warning_after is None:
                self._warning_phase = True
                self._blink_warning()
        else:
            self._stop_warning()

    def _blink_warning(self):
        """危险项的环 + 百分比文字在危险色↔暗色间闪烁，0.6s 一拍。"""
        try:
            for name in getattr(self, "_danger_items", []):
                row = {"token": self.token_row,
                       "week": self.week_row,
                       "mcp": self.mcp_row}.get(name)
                if not row:
                    continue
                color = COLOR_DANGER if self._warning_phase else BG_BAR_TRACK
                # 重画环：危险相位用 DANGER，暗相位画空轨道
                canvas = self._bars[row["bar_key"]]
                pct = {"token": self._last_token_pct,
                       "week": self._last_week_pct,
                       "mcp": self._last_mcp_pct}[name]
                if self._warning_phase:
                    self._draw_ring(canvas, pct)
                else:
                    # 暗相位：只画空轨道，隐藏进度弧
                    canvas.delete("all")
                    size = max(int(canvas.cget("height")), 60)
                    pad = 6
                    canvas.create_arc(pad, pad, size - pad, size - pad,
                                      start=90, extent=-359, style="arc",
                                      width=max(4, size // 12),
                                      outline=BG_BAR_TRACK)
                    cx = size / 2
                    canvas.create_text(cx, cx - 3,
                                       text=f"{pct:.0f}", fill=FG,
                                       font=(FONT_UI_SEMI, fs(max(12, size // 4)), "bold"))
                    canvas.create_text(cx, cx + size // 5, text="%",
                                       fill=FG_DIM, font=(FONT_MONO, fs(max(7, size // 10))))
                # 百分比文字也跟着闪
                row["pct_lbl"].config(fg=color)
            self._warning_phase = not self._warning_phase
            self._warning_after = self.after(600, self._blink_warning)
        except Exception:
            self._warning_after = None

    def _stop_warning(self):
        """停止警示闪烁，恢复正常显示。"""
        if self._warning_after is not None:
            try:
                self.after_cancel(self._warning_after)
            except Exception:
                pass
            self._warning_after = None
        # 恢复正常重绘
        try:
            self._draw_ring(self._bars[self.token_row["bar_key"]], self._last_token_pct)
            self._draw_ring(self._bars[self.week_row["bar_key"]], self._last_week_pct)
            self._draw_ring(self._bars[self.mcp_row["bar_key"]], self._last_mcp_pct)
            self.token_row["pct_lbl"].config(
                fg=self._grade(self._last_token_pct)[0])
            self.week_row["pct_lbl"].config(
                fg=self._grade(self._last_week_pct)[0])
            self.mcp_row["pct_lbl"].config(
                fg=self._grade(self._last_mcp_pct)[0])
        except Exception:
            pass

    # ── 科幻进度条绘制（窄长条 + 分段刻度 + 高光 + 发光端）──
    def _draw_bar(self, canvas, pct):
        canvas.delete("all")
        w = canvas.winfo_width()
        if w < 20:
            w = self.WIDTH - 32
        h = 14
        fill, _ = self._grade(pct)

        # 1. 凹槽底（深色圆角）
        canvas.create_rectangle(0, 0, w, h, fill=BG_BAR_TRACK, outline=EDGE,
                                width=1, tags="track")
        # 2. 填充段
        fw = int(w * min(pct, 100) / 100)
        if fw >= 2:
            # 主填充
            canvas.create_rectangle(1, 1, fw, h - 1, fill=fill, outline="", tags="fill")
            # 顶部高光线（亮一档）
            canvas.create_line(2, 1.5, max(2, fw - 2), 1.5,
                               fill=self._lighten(fill), width=1, tags="glow")
            # 末端发光端帽（竖条）
            canvas.create_line(fw - 0.5, 2, fw - 0.5, h - 2,
                               fill=self._lighten(fill, True), width=1, tags="cap")

        # 3. 分段刻度（10 段，科幻电表感）
        seg = w / 10
        for i in range(1, 10):
            x = round(i * seg)
            canvas.create_line(x, 2, x, h - 2, fill=BG, width=1, tags="tick")

    # ── 环形进度表盘（替代横条，更直观）──
    def _draw_ring(self, canvas, pct):
        """在给定 Canvas 上画环形进度表盘。

        - 背景轨道弧（整圈暗色）+ 进度弧（分级配色）
        - 环心显示百分比大字（数值 + % 小字，强视觉层次）
        - pct=0 时只画空轨道，不画进度弧
        """
        canvas.delete("all")
        size = canvas.winfo_width()
        if size < 20:
            size = int(canvas.cget("height"))
        h = canvas.winfo_height()
        if h < 20:
            h = int(canvas.cget("height"))
        # 用 height 作为直径基准（ring Canvas 是正方形）
        d = min(size, h)
        if d < 20:
            d = 60
        pad = 6
        x1, y1, x2, y2 = pad, pad, d - pad, d - pad
        thick = max(4, d // 12)   # 环厚随尺寸缩放

        # 1. 背景轨道（整圈）
        canvas.create_arc(x1, y1, x2, y2, start=90, extent=-359,
                          style="arc", width=thick, outline=BG_BAR_TRACK)

        # 2. 进度弧
        if pct > 0:
            fill, _ = self._grade(pct)
            ext = -359 * min(pct, 100) / 100
            canvas.create_arc(x1, y1, x2, y2, start=90, extent=ext,
                              style="arc", width=thick, outline=fill)

        # 3. 环心百分比文字（数值大 + % 小）
        cx = d / 2
        num = f"{pct:.0f}"
        # 数值
        canvas.create_text(cx, cx - 3, text=num, fill=FG,
                           font=(FONT_UI_SEMI, max(12, d // 4), "bold"))
        # % 号
        canvas.create_text(cx, cx + d // 5, text="%",
                           fill=FG_DIM, font=(FONT_MONO, max(7, d // 10)))

    @staticmethod
    def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
        """用 arc+rectangle 拼一个圆角矩形（tkinter Frame 不支持圆角）。返回 item id。"""
        return round_rect(canvas, x1, y1, x2, y2, r, **kw)

    @staticmethod
    def _lighten(hex_color, strong=False):
        """简单提亮颜色用于高光。"""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        amt = 90 if strong else 55
        r, g, b = min(255, r + amt), min(255, g + amt), min(255, b + amt)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _force_redraw(self):
        """窗口显示后强制重绘进度条（解决 winfo_width=0 的问题）。"""
        try:
            self._draw_ring(self._bars[self.token_row["bar_key"]], self._last_token_pct)
            self._draw_ring(self._bars[self.week_row["bar_key"]], self._last_week_pct)
            self._draw_ring(self._bars[self.mcp_row["bar_key"]], self._last_mcp_pct)
        except Exception:
            pass

    _last_token_pct = 0.0
    _last_week_pct = 0.0
    _last_mcp_pct = 0.0

    def update_data(self, data: quota.QuotaData):
        """收到新数据时刷新整个 UI。"""
        self.title_lbl.config(text=self._head_text())

        # 刚启动还没拿到真实数据：显示加载态，不要显示误导性的 0%
        if data.is_empty:
            self.token_row["pct"].set("···")
            self.token_row["pct_lbl"].config(fg=FG_DIM)
            self.token_row["sub"].set("首次查询中…")
            self.week_row["pct"].set("···")
            self.week_row["pct_lbl"].config(fg=FG_DIM)
            self.week_row["sub"].set("")
            self.mcp_row["pct"].set("···")
            self.mcp_row["pct_lbl"].config(fg=FG_DIM)
            self.mcp_row["sub"].set("")
            self._last_token_pct = self._last_week_pct = self._last_mcp_pct = 0
            self._draw_ring(self._bars[self.token_row["bar_key"]], 0)
            self._draw_ring(self._bars[self.week_row["bar_key"]], 0)
            self._draw_ring(self._bars[self.mcp_row["bar_key"]], 0)
            self.reset_cd_var.set("LOADING…")
            self.status_lbl.config(text="⟳ 正在获取额度数据…")
            return

        if data.error:
            self.token_row["pct"].set("ERR")
            self.token_row["pct_lbl"].config(fg=COLOR_DANGER)
            self.token_row["sub"].set(data.error[:28])
            self.week_row["pct"].set("--")
            self.week_row["sub"].set("")
            self.mcp_row["pct"].set("--")
            self.mcp_row["sub"].set("")
            self._last_token_pct = self._last_week_pct = self._last_mcp_pct = 0
            self._draw_ring(self._bars[self.token_row["bar_key"]], 0)
            self._draw_ring(self._bars[self.week_row["bar_key"]], 0)
            self._draw_ring(self._bars[self.mcp_row["bar_key"]], 0)
            self.reset_cd_var.set("CONNECTION ERROR")
            self.status_lbl.config(text=f"✗ 失败 · {datetime.now():%H:%M}")
            return

        # Token 行（5h 窗口）
        t5h = data.token_5h
        if t5h:
            self.token_row["pct"].set(f"{t5h.pct:.0f}%")
            tfill, _ = self._grade(t5h.pct)
            self.token_row["pct_lbl"].config(fg=tfill)
            self._last_token_pct = t5h.pct
            clk = quota.ts_to_clock(t5h.reset_ts)
            self.token_row["sub"].set(f"重置于 {clk}" if clk else "")
            self._draw_ring(self._bars[self.token_row["bar_key"]], t5h.pct)
        else:
            self.token_row["pct"].set("--")
            self._draw_ring(self._bars[self.token_row["bar_key"]], 0)

        # 周 token 窗口（如果有）
        tw = data.token_weekly
        if tw and hasattr(self, "week_row"):
            self.week_row["pct"].set(f"{tw.pct:.0f}%")
            wfill, _ = self._grade(tw.pct)
            self.week_row["pct_lbl"].config(fg=wfill)
            self._last_week_pct = tw.pct
            wclk = quota.ts_to_clock(tw.reset_ts)
            self.week_row["sub"].set(f"重置于 {wclk}" if wclk else "")
            self._draw_ring(self._bars[self.week_row["bar_key"]], tw.pct)

        # MCP 行
        self.mcp_row["pct"].set(f"{data.mcp_pct:.0f}%")
        mfill, _ = self._grade(data.mcp_pct)
        self.mcp_row["pct_lbl"].config(fg=mfill)
        self._last_mcp_pct = data.mcp_pct
        mcp_sub = f"{data.mcp_current}/{data.mcp_total} used"
        mcp_cd = quota.ts_to_countdown(data.mcp_reset_ts)
        if mcp_cd:
            mcp_sub += f"  ·  {mcp_cd}重置"
        self.mcp_row["sub"].set(mcp_sub)
        self._draw_ring(self._bars[self.mcp_row["bar_key"]], data.mcp_pct)

        # 5h 重置倒计时（高亮大字）——用真正的 5h 窗口时间戳
        t5h_for_cd = data.token_5h
        self._update_reset_countdown(t5h_for_cd.reset_ts if t5h_for_cd else None)

        # 状态行
        next_min = self.cfg.interval_min
        self.status_lbl.config(
            text=f"⟳ {datetime.now():%H:%M}  ·  {next_min}min refresh  ·  drag to move")

        # 警示动画：任一指标 ≥90% 则启动闪烁
        self._check_warning()

    def _update_reset_countdown(self, ts_ms):
        """刷新 5h 重置倒计时，每秒走表。"""
        if not ts_ms:
            self.reset_cd_var.set("-- : -- : --")
            return
        # 计算并立即设置一次
        self._reset_ts = ts_ms
        self._tick_reset()

    def _tick_reset(self):
        ts = getattr(self, "_reset_ts", None)
        if not ts:
            return
        delta = datetime.fromtimestamp(ts / 1000) - datetime.now()
        secs = max(0, int(delta.total_seconds()))
        sub = getattr(self, "reset_sub_var", None)
        if sub:
            sub.set("5H 窗口重置倒计时")
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        self.reset_cd_var.set(f"{h:02d} : {m:02d} : {s:02d}")
        # 每秒走一次，但只在本窗口可见时持续
        if self.winfo_viewable():
            self.after(1000, self._tick_reset)


# ──────────────────────────────────────────────────────────────
# 3. 设置窗口
# ──────────────────────────────────────────────────────────────
class SettingsDialog(tk.Toplevel):
    def __init__(self, master, cfg: cfg_mod.Config, on_save):
        super().__init__(master)
        self.cfg = cfg
        self.on_save = on_save
        self.title("GLM 额度助手 · 设置")
        self.configure(bg=BG)
        self.resizable(FALSE, FALSE)
        self.grab_set()

        # 居中
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = 420, 380
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._build()

    def _build(self):
        pad = {"padx": 20, "pady": 8}
        f = tk.Frame(self, bg=BG)
        f.pack(fill=BOTH, expand=True)

        tk.Label(f, text="GLM 额度助手 · 设置", bg=BG, fg=FG,
                 font=(FONT_UI, fs(13), "bold")).grid(row=0, column=0, columnspan=2, pady=(20, 12), sticky="w", padx=20)

        # 平台
        tk.Label(f, text="站点", bg=BG, fg=FG_DIM, font=(FONT_UI, fs(9))).grid(row=1, column=0, sticky="w", **pad)
        pf = tk.Frame(f, bg=BG)
        pf.grid(row=1, column=1, sticky="w")
        self.plat_var = tk.StringVar(value=self.cfg.platform)
        tk.Radiobutton(pf, text="智谱 AI（国内站）", variable=self.plat_var, value="zhipu",
                       bg=BG, fg=FG, selectcolor=BG_CARD, activebackground=BG,
                       font=(FONT_UI, fs(9)), command=self._on_plat).pack(side=LEFT)
        tk.Radiobutton(pf, text="Z.ai（国际站）", variable=self.plat_var, value="zai",
                       bg=BG, fg=FG, selectcolor=BG_CARD, activebackground=BG,
                       font=(FONT_UI, fs(9)), command=self._on_plat).pack(side=LEFT, padx=(10, 0))

        # Base URL
        tk.Label(f, text="Base URL", bg=BG, fg=FG_DIM, font=(FONT_UI, fs(9))).grid(row=2, column=0, sticky="w", **pad)
        self.url_var = tk.StringVar(value=self.cfg.base_url)
        tk.Entry(f, textvariable=self.url_var, width=34, bg=BG_CARD, fg=FG,
                 insertbackground=FG, relief=FLAT, font=(FONT_UI, fs(9))).grid(row=2, column=1, sticky="w", pady=8)

        # API Key
        tk.Label(f, text="API Key", bg=BG, fg=FG_DIM, font=(FONT_UI, fs(9))).grid(row=3, column=0, sticky="w", **pad)
        kf = tk.Frame(f, bg=BG)
        kf.grid(row=3, column=1, sticky="w")
        self.key_var = tk.StringVar(value=self.cfg.api_key)
        self.key_entry = tk.Entry(kf, textvariable=self.key_var, width=28, bg=BG_CARD, fg=FG,
                                  insertbackground=FG, relief=FLAT, show="●", font=(FONT_UI, fs(9)))
        self.key_entry.pack(side=LEFT)
        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kf, text="显示", variable=self.show_var, command=self._toggle_key,
                       bg=BG, fg=FG_DIM, selectcolor=BG_CARD, activebackground=BG,
                       font=(FONT_UI, fs(8))).pack(side=LEFT, padx=(6, 0))

        # 刷新间隔
        tk.Label(f, text="刷新间隔", bg=BG, fg=FG_DIM, font=(FONT_UI, fs(9))).grid(row=4, column=0, sticky="w", **pad)
        iv = tk.Frame(f, bg=BG)
        iv.grid(row=4, column=1, sticky="w")
        self.int_var = tk.IntVar(value=self.cfg.interval_min)
        tk.Spinbox(iv, from_=1, to=1440, textvariable=self.int_var, width=6, bg=BG_CARD, fg=FG,
                   insertbackground=FG, relief=FLAT, font=(FONT_UI, fs(9))).pack(side=LEFT)
        tk.Label(iv, text=" 分钟", bg=BG, fg=FG_DIM, font=(FONT_UI, fs(9))).pack(side=LEFT)

        # 主题（极简 / 科幻 / 温暖）—— 重启后生效
        tk.Label(f, text="主题", bg=BG, fg=FG_DIM, font=(FONT_UI, fs(9))).grid(row=5, column=0, sticky="w", **pad)
        tf = tk.Frame(f, bg=BG)
        tf.grid(row=5, column=1, sticky="w")
        self.theme_var = tk.StringVar(value=self.cfg.theme)
        for val, txt in [("minimal", "极简"), ("scifi", "科幻"), ("cozy", "温暖")]:
            tk.Radiobutton(tf, text=txt, variable=self.theme_var, value=val,
                           bg=BG, fg=FG, selectcolor=BG_CARD, activebackground=BG,
                           font=(FONT_UI, fs(9))).pack(side=LEFT, padx=(0, 10))

        # 按钮（用 Label 模拟：macOS 原生 Button 不吃背景色，会显示成
        # 系统默认白色，白字白底完全看不清。Label 在所有平台都受 bg/fg 控制）
        bf = tk.Frame(f, bg=BG)
        bf.grid(row=6, column=0, columnspan=2, pady=(20, 16))
        self._make_btn(bf, "保存并开始", self._save, primary=True).pack(side=LEFT, padx=8)
        self._make_btn(bf, "取消", self.destroy, primary=False).pack(side=LEFT)

    def _make_btn(self, parent, text, command, *, primary=False):
        """用 Label 模拟按钮，跨平台背景色可控。"""
        bg = ACCENT if primary else BG_CARD
        fg = "white" if primary else FG
        btn = tk.Label(parent, text=text, bg=bg, fg=fg,
                       font=(FONT_UI, fs(10), "bold" if primary else "normal"),
                       padx=20 if primary else 16, pady=6, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        # 悬停效果
        btn.bind("<Enter>", lambda e: btn.config(bg=HOVER) if not primary else btn.config(bg=_lighten(ACCENT)))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def _on_plat(self):
        if self.plat_var.get() == "zhipu":
            self.url_var.set("https://open.bigmodel.cn/api/paas/v4")
        else:
            self.url_var.set("https://api.z.ai/api/paas/v4")

    def _toggle_key(self):
        self.key_entry.config(show="" if self.show_var.get() else "●")

    def _save(self):
        if not self.key_var.get().strip():
            messagebox.showwarning("提示", "请填写 API Key", parent=self)
            return
        if not self.url_var.get().strip():
            messagebox.showwarning("提示", "请填写 Base URL", parent=self)
            return
        # 记录主题是否变更（保存后提示需重启）
        theme_changed = self.theme_var.get() != self.cfg.theme
        self.cfg.platform = self.plat_var.get()
        self.cfg.base_url = self.url_var.get().strip()
        self.cfg.api_key = self.key_var.get().strip()
        self.cfg.theme = self.theme_var.get()
        try:
            self.cfg.interval_min = max(1, int(self.int_var.get()))
        except (ValueError, tk.TclError):
            self.cfg.interval_min = 10
        cfg_mod.save(self.cfg)
        self.on_save(self.cfg)
        if theme_changed:
            messagebox.showinfo("主题已切换",
                                "主题将在重启程序后生效。", parent=self)
        self.destroy()


# ──────────────────────────────────────────────────────────────
# 4. 主应用：托盘 + 后台线程
# ──────────────────────────────────────────────────────────────
def _try_import_pystray():
    """尝试导入 pystray。没有安装时返回 None（程序仍可运行，只是没有托盘）。

    macOS 上刻意不用 pystray：pystray 的 pyobjc 后端与 tkinter 同进程运行时，
    点击托盘会触发 `PyEval_RestoreThread: GIL is released` 硬崩溃
    （pyobjc 的 Mach 信号处理与 Python 3.12 线程状态冲突，无法在应用层修复）。
    所以 macOS 走「纯 tkinter + 悬浮窗右键菜单」模式，安全且功能完整。
    """
    if IS_MAC:
        return None
    try:
        import pystray  # noqa: F401
        return pystray
    except Exception:
        return None


class App:
    def __init__(self):
        self.cfg = cfg_mod.load()
        # 在创建任何 Toplevel 前应用主题（改写模块级配色常量）
        apply_theme(self.cfg.theme)
        self.last_data = quota.QuotaData()
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口，只用 Toplevel

        # macOS Dock 图标点击 / 退出信号
        self._has_tray = _try_import_pystray() is not None
        self.floating: FloatingBar | None = None
        self._stop = threading.Event()
        self._refresh_evt = threading.Event()

        # 启动后台刷新线程
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

        # UI 刷新轮询（每 500ms 把新数据从 worker 搬到 UI）
        self.root.after(500, self._poll)
        self.root.after(800, self._first_show)

    # ── 后台刷新线程 ──
    def _worker(self):
        while not self._stop.is_set():
            # 未配置好之前不查询，保持 UI 的"加载中/等待配置"状态
            if cfg_mod.is_configured(self.cfg):
                try:
                    data = quota.query_quota(self.cfg.base_url, self.cfg.api_key)
                except Exception as e:  # noqa: BLE001
                    data = quota.QuotaData(error=str(e)[:120])
            else:
                data = quota.QuotaData()  # 空，触发 is_empty 加载态
            self._pending = data
            # 等待 interval 或被立即刷新信号唤醒
            self._refresh_evt.wait(timeout=self.cfg.interval_min * 60)
            self._refresh_evt.clear()

    _pending: quota.QuotaData | None = None

    def _poll(self):
        if self._pending is not None:
            data = self._pending
            self._pending = None
            self.last_data = data
            if self.floating:
                self.floating.update_data(data)
                # 折叠态药丸也要跟着刷新 5H 百分比
                mini = getattr(self.floating, "_mini", None)
                if mini is not None:
                    try:
                        mini.refresh()   # 数据到达立即刷新胶囊
                    except Exception:
                        pass
            self._update_tooltip()
        self.root.after(500, self._poll)

    def _first_show(self):
        if not cfg_mod.is_configured(self.cfg):
            self.open_settings()
        # 上次退出时若处于折叠态(win_visible=false)，启动直接显示药丸，
        # 否则会出现"什么都看不到"的情况。
        self._clamp_window_pos()
        if self.cfg.win_visible:
            self.show_floating()
        else:
            # 折叠态：建主窗口(隐藏) + 直接弹出药丸
            if self.floating is None:
                self.floating = FloatingBar(self.root, self)
            self.floating.withdraw()
            self.floating._collapse()

    def _clamp_window_pos(self):
        """把记忆的窗口位置拉回屏幕可见区，防止跑出屏外找不到。"""
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, min(self.cfg.win_x, sw - 80))
            y = max(0, min(self.cfg.win_y, sh - 60))
            self.cfg.win_x, self.cfg.win_y = x, y
        except Exception:
            pass

    # ── 托盘菜单动作 ──
    def show_floating(self):
        if self.floating is None:
            self.floating = FloatingBar(self.root, self)
        self.floating.show()
        self.floating.update_data(self.last_data)

    def hide_floating(self):
        if self.floating:
            self.floating.hide()

    def toggle_floating(self, icon=None, item=None):
        if self.floating and self.floating.winfo_viewable():
            self.root.after(0, self.hide_floating)
        else:
            self.root.after(0, self.show_floating)

    def refresh_now(self, icon=None, item=None):
        self._refresh_evt.set()

    def open_settings(self, icon=None, item=None):
        self.root.after(0, lambda: SettingsDialog(self.root, self.cfg, self._on_cfg_saved).focus_set())

    def _on_cfg_saved(self, new_cfg):
        # 重启 worker 以应用新间隔
        self._refresh_evt.set()

    def toggle_autostart(self, icon=None, item=None):
        self.cfg.auto_start = not self.cfg.auto_start
        cfg_mod.save(self.cfg)
        cfg_mod.set_auto_start(self.cfg.auto_start)
        self._rebuild_menu()

    def quit(self, icon=None, item=None):
        # 记住窗口位置
        if self.floating:
            try:
                self.cfg.win_x = self.floating.winfo_x()
                self.cfg.win_y = self.floating.winfo_y()
                cfg_mod.save(self.cfg)
            except Exception:
                pass
        self._stop.set()
        self._refresh_evt.set()
        try:
            self.icon.stop()
        except Exception:
            pass
        try:
            self.root.after(0, self.root.quit)
        except Exception:
            pass

    # ── 托盘 ──
    def _update_tooltip(self):
        # macOS 菜单栏状态项的悬停 tooltip 在很多系统版本上不显示，
        # 所以这里同时做两件事：
        #   1. 更新 icon.title（Windows / Linux 上能显示悬停提示）
        #   2. 重建菜单，把额度信息放菜单顶部（macOS 点开菜单即可看到）
        try:
            if getattr(self, "icon", None) is not None:
                self.icon.title = self._tip_text()
                self._rebuild_menu()
        except Exception:
            pass

    def _tip_text(self) -> str:
        """单行 tooltip 文本（Windows/Linux 悬停用，也拼进菜单）。"""
        d = self.last_data
        if d.error:
            return "GLM 额度 · 查询失败"
        if d.is_empty:
            return "GLM 额度 · 加载中…"
        lvl = d.level.upper() if d.level else "—"
        t5h_pct = d.token_5h.pct if d.token_5h else 0
        return f"GLM 额度 · {lvl} · 5H {t5h_pct:.0f}%"

    def _quota_menu_lines(self) -> list[str]:
        """多行额度明细，放进托盘菜单顶部展示。"""
        d = self.last_data
        if d.error:
            return ["查询失败", "——"]
        if d.is_empty:
            return ["加载中…", "——"]
        lvl = d.level.upper() if d.level else "—"
        t5h_pct = d.token_5h.pct if d.token_5h else 0
        tw_pct = d.token_weekly.pct if d.token_weekly else 0
        return [
            f"GLM · {lvl}",
            f"Token(5h): {t5h_pct:.0f}%",
            f"Token(周): {tw_pct:.0f}%",
            f"MCP(月): {d.mcp_pct:.0f}% ({d.mcp_current}/{d.mcp_total})",
        ]

    def _menu(self):
        pystray = _try_import_pystray()
        shown = self.cfg.win_visible
        # 顶部额度明细：只读项（enabled=False, default=False），点不动
        head_items = [
            pystray.MenuItem(line, None, enabled=False)
            for line in self._quota_menu_lines()
        ]
        return pystray.Menu(
            *head_items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "隐藏悬浮条" if shown else "显示悬浮条",
                self.toggle_floating, default=True
            ),
            pystray.MenuItem("立即刷新", self.refresh_now),
            pystray.MenuItem("设置…", self.open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _: ("✓ " if self.cfg.auto_start else "") + "开机自启",
                self.toggle_autostart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self.quit),
        )

    def _rebuild_menu(self):
        try:
            self.icon.menu = self._menu()
            self.icon.update_menu()
        except Exception:
            pass

    def run(self):
        pystray = _try_import_pystray()
        # macOS：关掉所有窗口时不要真正退出，仍驻留后台
        # （靠悬浮窗右键菜单 / 系统托盘来退出）。
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        if pystray is not None:
            self.icon = pystray.Icon(
                "GLMQuota",
                make_icon(),
                "GLM 额度助手",
                menu=self._menu(),
            )
            # pystray 在 Windows 上可安全 run_detached 到子线程；
            # macOS 上 AppKit 后端虽更想吃主线程，但 run_detached 在
            # pystray 内部会用独立线程驱动，实测可用。
            self.icon.run_detached()
        else:
            self.icon = None
        self.root.mainloop()           # tkinter 主循环（主线程）


def main():
    # 高 DPI 感知：用 per-monitor v2（2），让窗口在高分屏/缩放下保持清晰。
    # 旧的 SetProcessDpiAwareness(1) 只是系统级感知，多屏或缩放变化时会模糊。
    # 优先用新版 API（SetProcessDpiAwarenessContext，Win10 1703+），
    # 不支持时回退到旧版 SetProcessDpiAwareness(2)。
    try:
        import ctypes
        try:
            # PER_MONITOR_AWARE_V2 = -4（Win10 1703+，推荐）
            ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        except (AttributeError, OSError):
            # 回退：PER_MONITOR_AWARE = 2
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    # 单实例保护：已有实例在跑就静默退出
    if not cfg_mod.acquire_single_instance():
        sys.exit(0)

    App().run()


if __name__ == "__main__":
    main()
