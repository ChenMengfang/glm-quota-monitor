<div align="center">

# ⚡ GLM Quota Monitor

**智谱 AI / Z.ai GLM Coding Plan 套餐额度实时监控 · 桌面悬浮小工具**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows · macOS · Linux](https://img.shields.io/badge/Platform-Win%20%7C%20macOS%20%7C%20Linux-blue.svg)]()
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)]()
[![Version: v2.0](https://img.shields.io/badge/Version-v2.0-orange.svg)]()
[![Build Windows EXE](https://github.com/ChenMengfang/glm-quota-monitor/actions/workflows/build-windows.yml/badge.svg)](https://github.com/ChenMengfang/glm-quota-monitor/actions/workflows/build-windows.yml)

</div>

---

## 📖 这是什么

如果你在用智谱 AI（bigmodel.cn）或 Z.ai 的 **GLM Coding Plan 订阅套餐**（Lite / Pro / Max），一定遇到过这些烦恼：

- 😤 用着用着突然 429 报错，不知道是 5 小时窗口用完了还是月额度超了
- 🔍 想看剩余额度只能登录网页控制台翻菜单
- 📉 不知道自己 MCP 工具（联网搜索、网页读取）到底用了多少次

这个工具在**桌面常驻一个悬浮条**，实时显示：
- **5 小时 Token 窗口** + **周 Token 窗口**使用百分比（环形表盘）
- **MCP 工具月用量**（联网搜索 / 网页读取 / zread）的消耗情况
- 套餐等级（LITE / PRO / MAX）和下次重置时间

让你在用 Claude Code / Cursor / ZCode 调 GLM 时，对额度消耗一目了然。

> **v2.0 重大更新**：从 Windows 独占升级为 **Windows / macOS / Linux 跨平台**，UI 重构为**环形进度表盘 + 三套主题（科幻/极简/温暖）+ 分级警示动画**，双平台安装包均已在 [Releases](../../releases) 提供，Windows 版由 GitHub Actions 云端自动构建。

---

## ✨ 特性

### 🎨 视觉
- 💍 **环形进度表盘** —— 每个指标用环形仪表展示，环心显示百分比，比横条更直观（参考 Apple HIG）
- 🎭 **三套主题** —— 科幻风（深空黑+青色霓虹）/ 极简风（白底冷调）/ 温暖风（米黄书信），设置里一键切换
- 🔔 **分级警示动画** —— 任一指标 ≥90% 自动闪烁提醒，避免被限流
- 🪟 **玻璃质感** —— 半透明置顶悬浮，轻盈浮于桌面

### 🖥️ 跨平台
- 🪟 **Windows** —— 系统托盘 + 注册表开机自启 + 命名互斥锁单实例
- 🍎 **macOS** —— 原生 `.app` 应用包 + LaunchAgent 开机自启 + 文件锁单实例
- 🐧 **Linux** —— XDG autostart 开机自启（理论支持）

### ⚙️ 功能
- ⏱️ **实时倒计时** —— 每秒走表，显示距 5h 窗口重置还剩多久
- 📍 **桌面悬浮** —— 无边框置顶，点任意处折叠成迷你胶囊，拖动移位，位置自动记忆
- 🔄 **自动刷新** —— 后台线程定时查询（默认 10 分钟，可调），UI 永不卡顿
- 🔒 **单实例保护** —— 双击多次只保留一个进程
- 🔐 **隐私安全** —— API Key 只存在本地，不上传任何地方

---

## 📸 效果预览

**主悬浮条（环形表盘 + 倒计时）：**
```
┌─────────────────────────────────────────┐
│ ◈ GLM · 智谱 · MAX                  ✕   │
│─────────────────────────────────────────│
│ ╭───╮  TOKEN · 5H WINDOW         48%   │
│ │48%│  重置于 06-22 00:32                │  ← 环形表盘
│ ╰───╯                                   │
│ ╭───╮  TOKEN · WEEKLY            35%   │
│ │35%│  重置于 ...                        │
│ ╰───╯                                   │
│ ╭───╮  MCP · MONTHLY             20%   │
│ │20%│  20/100 used · 3天后重置           │
│ ╰───╯                                   │
│─────────────────────────────────────────│
│ ┌─────────────────────────────────────┐ │
│ │ ◷ RESET IN          03 : 42 : 18    │ │  ← 每秒走表
│ │ 5H 窗口重置倒计时                    │ │
│ └─────────────────────────────────────┘ │
│ ⟳ 14:23 · 10min refresh                 │
└─────────────────────────────────────────┘
```

**折叠后的迷你胶囊（双环：5H + 周限额）：**
```
┌─────────────────┐
│  ╭──╮    ╭──╮   │
│  │48│    │35│   │   ← 左：5H 用量  右：周用量
│  ╰──╯    ╰──╯   │
│   5H      周    │
└─────────────────┘
```

---

## 🚀 快速开始

### 方式一：下载安装包（推荐）

| 平台 | 文件 | 说明 |
|------|------|------|
| 🪟 **Windows** | `GLM额度助手-Windows.exe` | 双击运行，无需装 Python。[GitHub Actions 自动构建] |
| 🍎 **macOS** | `GLM额度助手-macOS-v2.0.zip` | 解压后拖入「应用程序」 |
| 🐧 **Linux** | 源码运行 | `pip install -r requirements.txt && python app.py` |

前往 [Releases](../../releases) 下载对应平台的安装包。

> **macOS 首次打开**若提示"无法验证开发者"：右键 `.app` →「打开」→ 弹窗点「打开」放行一次。
>
> **Windows** 若被杀毒软件误报（PyInstaller 打包的常见现象）：加入白名单信任，或改用源码运行。

### 方式二：从源码运行

```bash
git clone https://github.com/ChenMengfang/glm-quota-monitor.git
cd glm-quota-monitor
pip install -r requirements.txt
python app.py
```

首次启动会弹出设置窗口：
- **站点**：选「智谱 AI（国内站）」或「Z.ai（国际站）」
- **Base URL**：自动填充，一般不用改
- **API Key**：在 [open.bigmodel.cn](https://open.bigmodel.cn) 控制台 → API Keys 获取
- **主题**：极简 / 科幻 / 温暖（切换后重启生效）
- **刷新间隔**：默认 10 分钟

点「保存并开始」即可。

---

## 🎮 使用说明

| 操作 | 效果 |
|------|------|
| **单击悬浮条任意位置** | 折叠成迷你胶囊（双环显示 5H + 周用量） |
| **单击迷你胶囊** | 展开成完整悬浮条 |
| **拖动悬浮条/胶囊** | 移到任意位置（位置会被记住） |
| **右键** | 菜单：显示/隐藏、立即刷新、设置、开机自启、退出 |

> macOS 上不使用系统托盘（pystray 在 macOS + Python 3.12 上有 GIL 崩溃问题），改为悬浮条 + 迷你胶囊的纯 tkinter 模式，功能完整且稳定。

### 进度环颜色含义

| 颜色 | 区间 | 含义 |
|------|------|------|
| 🟢 绿 | 0% – 69% | 充裕，放心用 |
| 🟡 黄/橙 | 70% – 89% | 注意，开始节省 |
| 🔴 红 | 90% – 100% | 危险，闪烁提醒，即将限流 |

---

## ⚙️ 配置说明

配置文件位置（按平台）：

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%\GLMQuota\config.json` |
| macOS | `~/Library/Application Support/GLMQuota/config.json` |
| Linux | `~/.config/GLMQuota/config.json` |

包含字段：
```json
{
  "platform": "zhipu",              // "zhipu" 国内站 | "zai" 国际站
  "base_url": "https://...",        // API 端点
  "api_key": "你的key",             // 本地存储，不上传
  "interval_min": 10,               // 刷新间隔（分钟）
  "auto_start": false,              // 开机自启
  "win_x": 50, "win_y": 50,         // 悬浮窗位置
  "win_visible": true,              // 悬浮窗是否显示
  "theme": "scifi"                  // 主题：scifi | minimal | cozy
}
```

想重置配置？删掉这个文件重启即可。

---

## 🔧 从源码打包

### macOS（生成 .app）

```bash
pip install -r requirements.txt
./build.sh
# 产物：dist/GLM额度助手.app
```

### Windows（生成 exe）

**推荐：用 GitHub Actions 自动构建**——推送 `v*` tag 时会自动在云端 Windows 环境打包 exe 并上传到对应 Release（见仓库 `.github/workflows/build-windows.yml`）。也可在 Actions 页面手动触发。

**本地打包**（需 Windows 机器）：

```cmd
pip install -r requirements.txt
build.bat
```

---

## 🏗️ 项目结构

```
glm-quota-monitor/
├── app.py              # 主程序：悬浮窗 + 迷你胶囊 + 后台线程 + 主题系统
├── config.py           # 配置读写、开机自启（三平台）、单实例锁
├── quota.py            # 额度查询逻辑
├── build.sh            # macOS 打包脚本
├── build.bat           # Windows 打包脚本
├── .github/workflows/  # GitHub Actions：自动构建 Windows exe
├── app_icon.icns       # macOS 应用图标
├── app_icon.ico        # Windows 应用图标（多尺寸）
├── app_icon.png        # 通用图标
├── requirements.txt    # Python 依赖
├── LICENSE
└── README.md
```

### 技术栈

- **Python 3.10+** + **tkinter**（GUI，系统自带）
- **pystray** + **Pillow**（Windows 系统托盘 + 图标生成）
- **PyInstaller**（打包成 exe / app）

---

## 🔌 数据来源说明

本工具通过调用智谱的额度查询接口（`/api/monitor/usage/*`）获取数据。该接口路径参考自智谱官方开源插件 **glm-plan-usage**（[zai-org/zai-coding-plugins](https://github.com/zai-org/zai-coding-plugins)，Apache-2.0 协议）。

需要说明：
- 本项目**未复制官方插件的任何代码**，所有代码均为独立编写（Python 实现，官方为 JavaScript）
- 仅参考了"存在这样一个 HTTP 接口"这一客观事实，并自行实现了请求与解析逻辑
- 该接口**未写入智谱公开 API 文档**，属于内部接口，未来可能变更。若失效请对照上述官方仓库的最新实现

> 💡 这类似编写一个第三方客户端调用某平台的 API——用户使用自己的 API Key 查询自己的额度数据，不涉及绕过、冒充或批量爬取。

---

## ❓ 常见问题

<details>
<summary><b>启动后看不到悬浮条？</b></summary>

可能是上次退出时处于折叠态（迷你胶囊），但胶囊跑到屏幕外了。删掉配置文件里的 `win_x`/`win_y` 改回 `50` 重启即可，或直接删除配置文件重置。v2.0 已加入位置越界保护，自动拉回可见区。
</details>

<details>
<summary><b>一直显示「CONNECTION ERROR」？</b></summary>

检查设置里的 API Key 和 Base URL 是否正确：
- 智谱国内站：`https://open.bigmodel.cn/api/paas/v4`
- Z.ai 国际站：`https://api.z.ai/api/paas/v4`
- Key 格式形如 `xxxxxxxx.yyyyyyyy`（带点的完整字符串）
</details>

<details>
<summary><b>macOS 上没有系统托盘图标？</b></summary>

这是 v2.0 的设计选择。pystray 在 macOS + Python 3.12 上会触发 GIL 硬崩溃（`PyEval_RestoreThread` 错误），无法在应用层修复。所以 macOS 改为「悬浮条 + 迷你胶囊」的纯 tkinter 模式：单击折叠成胶囊、单击展开、右键出菜单，功能完整。Windows 上仍保留系统托盘。
</details>

<details>
<summary><b>主题切换后没变化？</b></summary>

主题需要重启程序才生效（设置里保存时会提示）。这是为了保持架构简洁——颜色常量在启动时一次性加载，避免运行时重建所有控件的复杂度。
</details>

<details>
<summary><b>我的 API Key 会被上传吗？</b></summary>

**不会。** Key 只存在本地配置文件，查询请求直连智谱服务器，不经过任何第三方。本工具完全开源，可自行审计。
</details>

---

## 🤝 贡献

欢迎提 Issue 和 PR！特别需要：
- 🐧 Linux 实测适配
- 🎨 更多 UI 主题
- 🌍 英文界面国际化

---

## 📄 许可证

[MIT License](LICENSE) - 自由使用、修改、分发。

---

<div align="center">

**如果这个工具帮到了你，欢迎 ⭐ Star 支持！**

Made with 💙 for the GLM Coding community

</div>
