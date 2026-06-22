<div align="center">

# ⚡ GLM Quota Monitor

**智谱 AI / Z.ai GLM Coding Plan 套餐额度实时监控 · 桌面悬浮小工具**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-blue.svg)]()
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)]()

</div>

---

## 📖 这是什么

如果你在用智谱 AI（bigmodel.cn）或 Z.ai 的 **GLM Coding Plan 订阅套餐**（Lite / Pro / Max），一定遇到过这些烦恼：

- 😤 用着用着突然 429 报错，不知道是 5 小时窗口用完了还是月额度超了
- 🔍 想看剩余额度只能登录网页控制台翻菜单
- 📉 不知道自己 MCP 工具（联网搜索、网页读取）到底用了多少次

这个工具在**桌面常驻一个科幻风悬浮条**，实时显示：
- **5 小时 Token 窗口**使用百分比 + 重置倒计时
- **MCP 工具月用量**（联网搜索 / 网页读取 / zread）的消耗情况
- 套餐等级（LITE / PRO / MAX）和下次重置时间

让你在用 Claude Code / Cursor / ZCode 调 GLM 时，对额度消耗一目了然。

---

## ✨ 特性

- 🎨 **科幻风 UI** —— 深色主题、分段刻度进度条、三色分级（绿/黄/红）、发光端帽
- ⏱️ **实时倒计时** —— 大号青色数字每秒走表，显示距 5h 窗口重置还剩多久
- 📍 **桌面悬浮** —— 无边框半透明置顶，可拖到任意位置，位置自动记忆
- 🖤 **系统托盘** —— 不占任务栏，鼠标悬停看快照，右键菜单完整操作
- 🔄 **自动刷新** —— 后台线程定时查询（默认 10 分钟，可调），UI 永不卡顿
- 🔒 **单实例保护** —— 双击多次只保留一个进程
- 🔐 **隐私安全** —— API Key 只存在本地 `%APPDATA%`，不上传任何地方
- 🪶 **零依赖运行** —— 提供打包好的 exe，无需安装 Python

---

## 📸 效果预览

```
┌─────────────────────────────────────────┐
│ ◈ GLM · 智谱 · LITE                 ✕   │
│─────────────────────────────────────────│
│ TOKEN · 5H WINDOW                  48%  │
│ ████████░░░│░░░░░░░░░  ← 分段刻度+发光   │
│ 重置于 06-22 00:32                       │
│                                         │
│ MCP · MONTHLY                      20%  │
│ ██░░░░░░░░│░░░░░░░░░                    │
│ 20/100 used · 3天后重置                  │
│─────────────────────────────────────────│
│ ┌─────────────────────────────────────┐ │
│ │ ◷ RESET IN          03 : 42 : 18    │ │  ← 每秒走表
│ │ 5H 窗口重置倒计时                    │ │
│ └─────────────────────────────────────┘ │
│ ⟳ 14:23 · 10min refresh · drag to move  │
└─────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 方式一：下载 exe（推荐，无需装 Python）

1. 前往 [Releases](../../releases) 下载 `GLMQuotaMonitor.exe`
2. 双击运行
3. 首次启动会弹出设置窗口：
   - **站点**：选「智谱 AI（国内站）」或「Z.ai（国际站）」
   - **Base URL**：自动填充，一般不用改
   - **API Key**：在 [open.bigmodel.cn](https://open.bigmodel.cn) 控制台 → API Keys 获取
   - **刷新间隔**：默认 10 分钟
4. 点「保存并开始」→ 右下角托盘出现 ⚡ 图标
5. **左键点托盘图标**弹出悬浮条

### 方式二：从源码运行

```bash
git clone https://github.com/ChenMengfang/glm-quota-monitor.git
cd glm-quota-monitor
pip install -r requirements.txt
python app.py
```

---

## 🎮 使用说明

| 操作 | 效果 |
|------|------|
| **左键点托盘图标** | 显示 / 隐藏桌面悬浮条 |
| **鼠标悬停托盘图标** | 弹出 tooltip 显示当前额度快照 |
| **右键托盘图标** | 菜单：刷新 / 设置 / 开机自启 / 退出 |
| **拖动悬浮条** | 移到任意位置（位置会被记住） |
| **悬浮条 ✕** | 收起到托盘（不退出程序） |

### 进度条颜色含义

| 颜色 | 区间 | 含义 |
|------|------|------|
| 🟢 鲜青绿 | 0% – 69% | 充裕，放心用 |
| 🟡 琥珀 | 70% – 89% | 注意，开始节省 |
| 🔴 品红 | 90% – 100% | 危险，即将限流 |

---

## ⚙️ 配置说明

配置文件位置：`%APPDATA%\GLMQuota\config.json`

包含字段：
```json
{
  "platform": "zhipu",              // "zhipu" 国内站 | "zai" 国际站
  "base_url": "https://...",        // API 端点
  "api_key": "你的key",             // 本地存储，不上传
  "interval_min": 10,               // 刷新间隔（分钟）
  "auto_start": false,              // 开机自启
  "win_x": 50, "win_y": 50,         // 悬浮窗位置
  "win_visible": true               // 悬浮窗是否显示
}
```

想重置配置？删掉这个文件重启即可。

---

## 🔧 从源码打包 exe

修改代码后重新打包：

```bash
pip install -r requirements.txt
python -m PyInstaller --noconfirm --noconsole --onefile ^
    --name "GLMQuotaMonitor" ^
    --collect-submodules pystray ^
    app.py
```

产物在 `dist/GLMQuotaMonitor.exe`。

---

## 🏗️ 项目结构

```
glm-quota-monitor/
├── app.py              # 主程序：托盘 + 悬浮窗 + 后台线程
├── config.py           # 配置读写、开机自启、单实例锁
├── quota.py            # 额度查询逻辑
├── requirements.txt    # Python 依赖
├── LICENSE
└── README.md
```

### 技术栈

- **Python 3.10+** + **tkinter**（GUI，系统自带）
- **pystray** + **Pillow**（系统托盘 + 图标生成）
- **PyInstaller**（打包成单 exe）

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
<summary><b>启动后托盘没有图标？</b></summary>

Windows 可能折叠了托盘图标。点托盘区左侧的 `^` 展开查看，把图标拖到托盘区可固定显示。
</details>

<details>
<summary><b>一直显示「CONNECTION ERROR」？</b></summary>

检查设置里的 API Key 和 Base URL 是否正确：
- 智谱国内站：`https://open.bigmodel.cn/api/paas/v4`
- Z.ai 国际站：`https://api.z.ai/api/paas/v4`
- Key 格式形如 `xxxxxxxx.yyyyyyyy`（带点的完整字符串）
</details>

<details>
<summary><b>任务管理器里看到两个同名进程？</b></summary>

这是 PyInstaller 单文件模式的正常架构：一个 bootloader（~9MB）负责解压，一个 Python（~55MB）真正运行。两者合起来是同一个程序，PID 稳定不变，**不是 bug**。
</details>

<details>
<summary><b>杀毒软件报毒？</b></summary>

PyInstaller 打包的 exe 容易被误报。可加入白名单信任，或改用源码运行 `python app.py`。
</details>

<details>
<summary><b>支持 macOS / Linux 吗？</b></summary>

目前仅支持 Windows。macOS/Linux 用户可尝试源码运行，但托盘图标 API 需要适配。
</details>

<details>
<summary><b>我的 API Key 会被上传吗？</b></summary>

**不会。** Key 只存在本地 `%APPDATA%\GLMQuota\config.json`，查询请求直连智谱服务器，不经过任何第三方。本工具完全开源，可自行审计。
</details>

---

## 🤝 贡献

欢迎提 Issue 和 PR！特别需要：
- 🍎 macOS 适配
- 🐧 Linux 适配
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
