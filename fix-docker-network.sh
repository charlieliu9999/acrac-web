#!/bin/bash

echo "🔧 修复 Docker 网络连接问题..."

# 1. 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

echo "✅ Docker 正在运行"

# 2. 配置 Docker 镜像源
echo "📝 配置 Docker 镜像源..."

# 创建 Docker 配置目录
mkdir -p ~/.docker

# 备份现有配置
if [ -f ~/.docker/daemon.json ]; then
    cp ~/.docker/daemon.json ~/.docker/daemon.json.backup
    echo "📋 已备份现有配置到 ~/.docker/daemon.json.backup"
fi

# 创建新的 daemon.json 配置
cat > ~/.docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://dockerproxy.com"
  ],
  "dns": ["8.8.8.8", "114.114.114.114"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

echo "✅ Docker 镜像源配置完成"

# 3. 重启 Docker 服务
echo "🔄 重启 Docker 服务..."

# 在 macOS 上，Docker Desktop 会自动应用配置
# 在 Linux 上需要重启 Docker 服务
if command -v systemctl > /dev/null 2>&1; then
    sudo systemctl restart docker
    echo "✅ Docker 服务已重启"
else
    echo "ℹ️  请手动重启 Docker Desktop 以应用配置"
fi

# 4. 测试网络连接
echo "🌐 测试网络连接..."
if ping -c 1 docker.io > /dev/null 2>&1; then
    echo "✅ 网络连接正常"
else
    echo "⚠️  网络连接可能有问题，但镜像源应该能解决"
fi

# 5. 预拉取基础镜像
echo "📦 预拉取基础镜像..."
docker pull python:3.10-slim || echo "⚠️  拉取失败，将使用镜像源"

echo "🎉 Docker 网络问题修复完成！"
echo ""
echo "📋 下一步操作："
echo "1. 如果使用 macOS，请重启 Docker Desktop"
echo "2. 运行: docker-compose up --build"
echo "3. 如果仍有问题，请检查网络代理设置"












