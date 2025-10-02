#!/bin/bash

echo "🔧 开始修复 Docker 网络问题..."

# 给脚本添加执行权限
chmod +x fix-docker-network.sh
chmod +x quick-fix-docker.sh

echo "📋 请选择修复方法："
echo "1. 自动修复（推荐）"
echo "2. 手动配置"
echo "3. 快速修复"

read -p "请输入选择 (1-3): " choice

case $choice in
    1)
        echo "🚀 执行自动修复..."
        ./fix-docker-network.sh
        ;;
    2)
        echo "📝 手动配置步骤："
        echo "1. 复制 docker-daemon.json 到 ~/.docker/daemon.json"
        echo "2. 重启 Docker Desktop"
        echo "3. 运行: docker-compose up --build"
        ;;
    3)
        echo "⚡ 执行快速修复..."
        ./quick-fix-docker.sh
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo "🎉 修复完成！"












