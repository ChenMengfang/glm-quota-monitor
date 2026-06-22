@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================
echo   GLM 额度助手 打包脚本
echo ============================================
echo.

echo [1/4] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未检测到 Python，请先安装 Python 3.10+ 并加入 PATH
    pause
    exit /b 1
)

echo [2/4] 安装依赖...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 依赖安装失败，请检查网络或换国内镜像：
    echo    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

echo [3/4] 清理旧产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist GLM额度助手.spec del /q GLM额度助手.spec

echo [4/4] 打包...
python -m PyInstaller --noconfirm --noconsole --onefile ^
    --name "GLM额度助手" ^
    --collect-submodules pystray ^
    app.py

if errorlevel 1 (
    echo.
    echo ❌ 打包失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ 打包成功！
echo   产物：dist\GLM额度助手.exe
echo   双击即可运行，无需安装 Python
echo ============================================
echo.
pause
