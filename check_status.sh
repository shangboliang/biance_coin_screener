#!/bin/bash
# 部署后检查脚本
# @author beck

echo "=========================================="
echo "  POC监控工具 - 服务状态检查"
echo "=========================================="
echo ""

# 1. 检查容器状态
echo "📦 容器运行状态："
docker compose ps
echo ""

# 2. 检查服务健康状态
echo "🏥 服务健康检查："
sleep 5
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 3. 查看最近日志
echo "📝 最近日志（监控服务）："
docker compose logs --tail=20 poc-monitor
echo ""

echo "📝 最近日志（Web服务）："
docker compose logs --tail=20 poc-web
echo ""

# 4. 获取访问地址
echo "=========================================="
echo "  🎉 部署成功！"
echo "=========================================="
echo ""
echo "📊 访问地址："
echo "   Nginx (80端口): http://$(curl -s ifconfig.me):80"
echo "   或直接访问: http://localhost"
echo ""
echo "🔑 登录信息："
echo "   密码: beck"
echo ""
echo "📝 常用命令："
echo "   查看实时日志: docker compose logs -f"
echo "   重启服务: docker compose restart"
echo "   停止服务: docker compose stop"
echo "   进入容器: docker exec -it poc_monitor bash"
echo "   查看数据库: docker exec -it poc_monitor sqlite3 /app/data/poc_monitor.db"
echo ""
echo "=========================================="
