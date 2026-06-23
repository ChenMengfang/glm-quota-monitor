#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# GLM 额度助手 macOS 打包脚本
# 产物：dist/GLM额度助手.app （可拖进 /Applications）
# ──────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo "  GLM 额度助手 macOS 打包脚本"
echo "============================================"
echo

# [1/4] 检查 Python 3
echo "[1/4] 检查 Python..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ 未检测到 python3，请先安装 Python 3.10+"
    echo "   推荐用 Homebrew：brew install python"
    exit 1
fi
python3 --version

# [2/4] 安装依赖
echo
echo "[2/4] 安装依赖..."
python3 -m pip install --upgrade pip >/dev/null 2>&1 || true
# macOS 上 pystray 的后端是 pyobjc，需要一并装上
python3 -m pip install -r requirements.txt pyobjc-core pyobjc-framework-Cocoa
if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败，请检查网络或换国内镜像："
    echo "   python3 -m pip install -r requirements.txt pyobjc-core pyobjc-framework-Cocoa \\"
    echo "       -i https://pypi.tuna.tsinghua.edu.cn/simple"
    exit 1
fi

# [3/4] 清理旧产物
echo
echo "[3/4] 清理旧产物..."
rm -rf build dist GLM额度助手.spec 2>/dev/null || true

# [4/4] 打包（.app 应用包）
echo
echo "[4/4] 打包..."
# 图标参数（如果 app_icon.icns 存在则使用）
ICON_ARGS=""
if [ -f app_icon.icns ]; then
    ICON_ARGS="--icon app_icon.icns --add-data app_icon.png:."
fi
python3 -m PyInstaller --noconfirm --windowed \
    --name "GLM额度助手" \
    --collect-submodules pystray \
    --osx-bundle-identifier "com.glm.quota-monitor" \
    $ICON_ARGS \
    app.py

if [ $? -ne 0 ]; then
    echo
    echo "❌ 打包失败"
    exit 1
fi

echo
echo "============================================"
echo "  ✅ 打包成功！"
echo "  产物：dist/GLM额度助手.app"
echo "  双击即可运行；可拖进 /Applications 永久使用"
echo "============================================"
