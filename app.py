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

# 科幻风调色板
BG = "#0d1117"            # 深空黑
BG_CARD = "#161b22"       # 卡片底
BG_BAR_TRACK = "#1f2630"  # 进度条凹槽
FG = "#e6edf3"            # 主文字
FG_DIM = "#7d8590"        # 次要文字
ACCENT = "#00e5ff"        # 主青色（科幻强调色）
# 分阶段颜色：正常 / 警告 / 危险
COLOR_OK = "#00ffa3"      # 鲜青绿
COLOR_WARN = "#ffb020"    # 琥珀
COLOR_DANGER = "#ff3b6b"  # 品红
HOVER = "#21262d"
EDGE = "#2a3441"          # 描边色


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
            self.attributes("-alpha", 0.94)  # 半透明
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

        # 拖动支持
        self._drag_dx = 0
        self._drag_dy = 0
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)

        # 存进度条 canvas 引用
        self._bars = {}
        self._build_ui()
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
            font=("Segoe UI Semibold", 11), anchor="w"
        )
        self.title_lbl.pack(side=LEFT)
        close_btn = tk.Label(
            head, text="✕", bg=BG, fg=FG_DIM,
            font=("Segoe UI", 10), cursor="hand2"
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
        self.mcp_row = self._make_row(body, "MCP · MONTHLY", is_token=False)

        # 5h 重置倒计时高亮区
        self.reset_zone = tk.Frame(card, bg=BG)
        self.reset_zone.pack(fill=X, padx=16, pady=(4, 8))
        self._build_reset_zone()

        # 底部状态行
        self.status_lbl = tk.Label(
            card, text="⟳ 初始化中…", bg=BG, fg=FG_DIM,
            font=("Consolas", 8), anchor="w"
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
                 font=("Consolas", 8)).pack(anchor="w")
        # 副标题（窗口未激活时会改成提示文字）
        self.reset_sub_var = tk.StringVar(value="5H 窗口重置倒计时")
        tk.Label(left, textvariable=self.reset_sub_var, bg=BG_BAR_TRACK, fg=FG,
                 font=("Segoe UI", 8), anchor="w").pack(anchor="w")
        # 右侧倒计时
        self.reset_cd_var = tk.StringVar(value="-- : -- : --")
        tk.Label(wrap, textvariable=self.reset_cd_var, bg=BG_BAR_TRACK,
                 fg=ACCENT, font=("Consolas", 16, "bold"),
                 padx=14).pack(side=RIGHT)

    def _make_row(self, parent, label_text, is_token=True):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=X, pady=(0, 10))

        # 标签行
        head = tk.Frame(row, bg=BG)
        head.pack(fill=X)
        tk.Label(
            head, text=label_text, bg=BG, fg=FG_DIM,
            font=("Consolas", 8)
        ).pack(side=LEFT)
        pct_var = tk.StringVar(value="0%")
        self._pct_labels = getattr(self, "_pct_labels", {})
        pct_lbl = tk.Label(head, textvariable=pct_var, bg=BG, fg=FG,
                           font=("Segoe UI Semibold", 10))
        pct_lbl.pack(side=RIGHT)

        # 科幻进度条 canvas（窄长条）
        bar = tk.Canvas(row, height=14, bg=BG, bd=0, highlightthickness=0)
        bar.pack(fill=X, pady=(3, 0))
        self._bars[label_text] = bar

        # 副文本（用量明细 / 重置钟点）
        sub_var = tk.StringVar(value="　")
        tk.Label(
            row, textvariable=sub_var, bg=BG, fg=FG_DIM,
            font=("Consolas", 8), anchor="w", justify=LEFT
        ).pack(fill=X, pady=(2, 0))

        return {"pct": pct_var, "pct_lbl": pct_lbl, "sub": sub_var,
                "bar_key": label_text}

    def _head_text(self):
        lvl = self.app.last_data.level.upper() if self.app.last_data.level else "—"
        plat = "智谱" if self.cfg.platform == "zhipu" else "Z.AI"
        return f"◈ GLM · {plat} · {lvl}"

    def _on_press(self, e):
        self._drag_dx = e.x
        self._drag_dy = e.y

    def _on_drag(self, e):
        x = self.winfo_x() + e.x - self._drag_dx
        y = self.winfo_y() + e.y - self._drag_dy
        self.geometry(f"+{x}+{y}")

    def hide(self):
        self.cfg.win_visible = False
        cfg_mod.save(self.cfg)
        self.withdraw()

    def show(self):
        self.cfg.win_visible = True
        cfg_mod.save(self.cfg)
        self.deiconify()
        self.after(120, self._force_redraw)
        # 重启倒计时链条（窗口隐藏期间 after 链可能已断）
        self.after(150, self._restart_countdown)

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
            self._draw_bar(self._bars[self.token_row["bar_key"]], self._last_token_pct)
            self._draw_bar(self._bars[self.mcp_row["bar_key"]], self._last_mcp_pct)
        except Exception:
            pass

    _last_token_pct = 0.0
    _last_mcp_pct = 0.0

    def update_data(self, data: quota.QuotaData):
        """收到新数据时刷新整个 UI。"""
        self.title_lbl.config(text=self._head_text())

        # 刚启动还没拿到真实数据：显示加载态，不要显示误导性的 0%
        if data.is_empty:
            self.token_row["pct"].set("···")
            self.token_row["pct_lbl"].config(fg=FG_DIM)
            self.token_row["sub"].set("首次查询中…")
            self.mcp_row["pct"].set("···")
            self.mcp_row["pct_lbl"].config(fg=FG_DIM)
            self.mcp_row["sub"].set("")
            self._last_token_pct = self._last_mcp_pct = 0
            self._draw_bar(self._bars[self.token_row["bar_key"]], 0)
            self._draw_bar(self._bars[self.mcp_row["bar_key"]], 0)
            self.reset_cd_var.set("LOADING…")
            self.status_lbl.config(text="⟳ 正在获取额度数据…")
            return

        if data.error:
            self.token_row["pct"].set("ERR")
            self.token_row["pct_lbl"].config(fg=COLOR_DANGER)
            self.token_row["sub"].set(data.error[:28])
            self.mcp_row["pct"].set("--")
            self.mcp_row["sub"].set("")
            self._last_token_pct = self._last_mcp_pct = 0
            self._draw_bar(self._bars[self.token_row["bar_key"]], 0)
            self._draw_bar(self._bars[self.mcp_row["bar_key"]], 0)
            self.reset_cd_var.set("CONNECTION ERROR")
            self.status_lbl.config(text=f"✗ 失败 · {datetime.now():%H:%M}")
            return

        # Token 行
        self.token_row["pct"].set(f"{data.token_pct:.0f}%")
        tfill, _ = self._grade(data.token_pct)
        self.token_row["pct_lbl"].config(fg=tfill)
        self._last_token_pct = data.token_pct
        cd = quota.ts_to_countdown(data.token_reset_ts)
        clk = quota.ts_to_clock(data.token_reset_ts)
        self.token_row["sub"].set(f"重置于 {clk}" if clk else "")
        self._draw_bar(self._bars[self.token_row["bar_key"]], data.token_pct)

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
        self._draw_bar(self._bars[self.mcp_row["bar_key"]], data.mcp_pct)

        # 5h 重置倒计时（高亮大字）
        self._update_reset_countdown(data.token_reset_ts)

        # 状态行
        next_min = self.cfg.interval_min
        self.status_lbl.config(
            text=f"⟳ {datetime.now():%H:%M}  ·  {next_min}min refresh  ·  drag to move")

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
        # 5h 窗口理论上限就是 5 小时；超过 6h 说明窗口还没被激活
        # （新账号/新 key 未产生过调用时，接口返回的是占位重置点）
        # 此时显示友好提示，而不是一个荒谬的大数字
        sub = getattr(self, "reset_sub_var", None)
        if secs > 6 * 3600:
            self.reset_cd_var.set("NOT ACTIVE")
            if sub:
                sub.set("窗口未激活 · 调用一次模型后开始计时")
            return
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
        w, h = 420, 340
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        self._build()

    def _build(self):
        pad = {"padx": 20, "pady": 8}
        f = tk.Frame(self, bg=BG)
        f.pack(fill=BOTH, expand=True)

        tk.Label(f, text="GLM 额度助手 · 设置", bg=BG, fg=FG,
                 font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=2, pady=(20, 12), sticky="w", padx=20)

        # 平台
        tk.Label(f, text="站点", bg=BG, fg=FG_DIM, font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", **pad)
        pf = tk.Frame(f, bg=BG)
        pf.grid(row=1, column=1, sticky="w")
        self.plat_var = tk.StringVar(value=self.cfg.platform)
        tk.Radiobutton(pf, text="智谱 AI（国内站）", variable=self.plat_var, value="zhipu",
                       bg=BG, fg=FG, selectcolor=BG_CARD, activebackground=BG,
                       font=("Segoe UI", 9), command=self._on_plat).pack(side=LEFT)
        tk.Radiobutton(pf, text="Z.ai（国际站）", variable=self.plat_var, value="zai",
                       bg=BG, fg=FG, selectcolor=BG_CARD, activebackground=BG,
                       font=("Segoe UI", 9), command=self._on_plat).pack(side=LEFT, padx=(10, 0))

        # Base URL
        tk.Label(f, text="Base URL", bg=BG, fg=FG_DIM, font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", **pad)
        self.url_var = tk.StringVar(value=self.cfg.base_url)
        tk.Entry(f, textvariable=self.url_var, width=34, bg=BG_CARD, fg=FG,
                 insertbackground=FG, relief=FLAT, font=("Segoe UI", 9)).grid(row=2, column=1, sticky="w", pady=8)

        # API Key
        tk.Label(f, text="API Key", bg=BG, fg=FG_DIM, font=("Segoe UI", 9)).grid(row=3, column=0, sticky="w", **pad)
        kf = tk.Frame(f, bg=BG)
        kf.grid(row=3, column=1, sticky="w")
        self.key_var = tk.StringVar(value=self.cfg.api_key)
        self.key_entry = tk.Entry(kf, textvariable=self.key_var, width=28, bg=BG_CARD, fg=FG,
                                  insertbackground=FG, relief=FLAT, show="●", font=("Segoe UI", 9))
        self.key_entry.pack(side=LEFT)
        self.show_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kf, text="显示", variable=self.show_var, command=self._toggle_key,
                       bg=BG, fg=FG_DIM, selectcolor=BG_CARD, activebackground=BG,
                       font=("Segoe UI", 8)).pack(side=LEFT, padx=(6, 0))

        # 刷新间隔
        tk.Label(f, text="刷新间隔", bg=BG, fg=FG_DIM, font=("Segoe UI", 9)).grid(row=4, column=0, sticky="w", **pad)
        iv = tk.Frame(f, bg=BG)
        iv.grid(row=4, column=1, sticky="w")
        self.int_var = tk.IntVar(value=self.cfg.interval_min)
        tk.Spinbox(iv, from_=1, to=1440, textvariable=self.int_var, width=6, bg=BG_CARD, fg=FG,
                   insertbackground=FG, relief=FLAT, font=("Segoe UI", 9)).pack(side=LEFT)
        tk.Label(iv, text=" 分钟", bg=BG, fg=FG_DIM, font=("Segoe UI", 9)).pack(side=LEFT)

        # 按钮
        bf = tk.Frame(f, bg=BG)
        bf.grid(row=5, column=0, columnspan=2, pady=(20, 16))
        tk.Button(bf, text="保存并开始", command=self._save, bg=ACCENT, fg="white",
                  activebackground=HOVER, relief=FLAT, padx=20, pady=6,
                  font=("Segoe UI", 10, "bold")).pack(side=LEFT, padx=8)
        tk.Button(bf, text="取消", command=self.destroy, bg=BG_CARD, fg=FG,
                  activebackground=HOVER, relief=FLAT, padx=16, pady=6,
                  font=("Segoe UI", 10)).pack(side=LEFT)

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
        self.cfg.platform = self.plat_var.get()
        self.cfg.base_url = self.url_var.get().strip()
        self.cfg.api_key = self.key_var.get().strip()
        try:
            self.cfg.interval_min = max(1, int(self.int_var.get()))
        except (ValueError, tk.TclError):
            self.cfg.interval_min = 10
        cfg_mod.save(self.cfg)
        self.on_save(self.cfg)
        self.destroy()


# ──────────────────────────────────────────────────────────────
# 4. 主应用：托盘 + 后台线程
# ──────────────────────────────────────────────────────────────
class App:
    def __init__(self):
        self.cfg = cfg_mod.load()
        self.last_data = quota.QuotaData()
        self.root = tk.Tk()
        self.root.withdraw()  # 隐藏主窗口，只用 Toplevel

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
            self._update_tooltip()
        self.root.after(500, self._poll)

    def _first_show(self):
        if not cfg_mod.is_configured(self.cfg):
            self.open_settings()
        if self.cfg.win_visible:
            self.show_floating()

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
        self.root.after(0, self.root.quit)

    # ── 托盘 ──
    def _update_tooltip(self):
        d = self.last_data
        if d.error:
            tip = f"GLM 额度 · 查询失败"
        else:
            lvl = d.level.upper() if d.level else "—"
            tip = f"GLM 额度 · {lvl}\nToken(5h): {d.token_pct:.0f}%\nMCP(月): {d.mcp_pct:.0f}% ({d.mcp_current}/{d.mcp_total})"
        try:
            self.icon.title = tip
        except Exception:
            pass

    def _menu(self):
        import pystray
        shown = self.cfg.win_visible
        return pystray.Menu(
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
        import pystray
        self.icon = pystray.Icon(
            "GLMQuota",
            make_icon(),
            "GLM 额度助手",
            menu=self._menu(),
        )
        self.icon.run_detached()        # 托盘在子线程跑
        self.root.mainloop()           # tkinter 主循环（主线程）


def main():
    # 高 DPI 感知
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # 单实例保护：已有实例在跑就静默退出
    if not cfg_mod.acquire_single_instance():
        sys.exit(0)

    App().run()


if __name__ == "__main__":
    main()
