#!/bin/bash

echo "🚀 快速修复 Docker 网络问题"

# 方法1: 使用国内镜像源构建
echo "📦 使用国内镜像源构建..."
PY_BASE_IMAGE=registry.cn-hangzhou.aliyuncs.com/library/python:3.10-slim docker-compose build --no-cache

# 如果方法1失败，尝试方法2
if [ $? -ne 0 ]; then
    echo "⚠️  方法1失败，尝试方法2..."
    
    # 方法2: 先拉取镜像再构建
    echo "📥 预拉取基础镜像..."
    docker pull registry.cn-hangzhou.aliyuncs.com/library/python:3.10-slim
    docker pull pgvector/pgvector:pg15
    docker pull redis:7-alpine
    
    echo "🔨 重新构建..."
    docker-compose build
fi

# 如果方法2也失败，尝试方法3
if [ $? -ne 0 ]; then
    echo "⚠️  方法2失败，尝试方法3..."
    
    # 方法3: 使用本地构建
    echo "🏗️  使用本地构建..."
    docker-compose build --no-cache --build-arg PY_BASE_IMAGE=python:3.10-slim
fi

echo "✅ 修复完成！"






















