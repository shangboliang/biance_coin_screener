@echo off
REM 快速部署脚本 - Windows版本 - 无需Nginx
REM @author beck

echo ==========================================
echo   币安POC监控工具 - 快速部署脚本
echo ==========================================
echo.

REM 检查Docker
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker未安装，请先安装Docker Desktop
    pause
    exit /b 1
)

docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose未安装
    pause
    exit /b 1
)

echo ✅ Docker环境检查通过
echo.

REM 创建必要目录
echo 📁 创建数据目录...
if not exist data mkdir data
if not exist logs mkdir logs

REM 配置环境变量
if not exist .env (
    echo ⚙️  配置环境变量...
    set /p telegram_token="请输入Telegram Bot Token (可选，直接回车跳过): "
    set /p telegram_id="请输入Telegram Chat ID (可选，直接回车跳过): "
    set /p web_password="请输入Web访问密码 (默认: beck): "

    if "%web_password%"=="" set web_password=beck

    (
        echo # Telegram配置（可选）
        echo TELEGRAM_BOT_TOKEN=%telegram_token%
        echo TELEGRAM_CHAT_ID=%telegram_id%
        echo.
        echo # Web访问控制
        echo WEB_PASSWORD=%web_password%
        echo WEB_SESSION_TIMEOUT=3600
        echo.
        echo # 代理配置（国内用户取消注释）
        echo # BINANCE_PROXY_HOST=127.0.0.1
        echo # BINANCE_PROXY_PORT=7897
        echo # TELEGRAM_PROXY_HOST=127.0.0.1
        echo # TELEGRAM_PROXY_PORT=7897
    ) > .env

    echo ✅ 环境变量配置完成
) else (
    echo ℹ️  .env文件已存在，跳过配置
)
echo.

REM 构建镜像
echo 🔨 构建Docker镜像...
docker-compose build

REM 启动服务
echo 🚀 启动服务...
docker-compose up -d

REM 等待服务启动
echo ⏳ 等待服务启动...
timeout /t 5 /nobreak >nul

REM 检查服务状态
echo.
echo ==========================================
echo   部署完成！
echo ==========================================
echo.
docker-compose ps
echo.
echo 📊 Web界面访问地址:
echo    http://localhost:8501
echo.
echo 🔑 默认密码: %web_password%
echo.
echo 📝 常用命令:
echo    查看日志: docker-compose logs -f
echo    停止服务: docker-compose stop
echo    重启服务: docker-compose restart
echo    进入容器: docker exec -it poc_monitor bash
echo.
echo ==========================================
echo.
pause
