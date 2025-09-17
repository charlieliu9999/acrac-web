#!/bin/bash

# ACRAC项目自动化启动脚本
# 使用 Docker-Compose 启动所有服务

set -e  # 遇到错误立即退出

echo "=== ACRAC项目自动化启动脚本 (Docker-Compose) ==="
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
# 加载本地开发环境变量（默认加载 .env.dev）
if [ -f "backend/.env.dev" ]; then
  echo "[INFO] 加载 backend/.env.dev 环境变量"
  set -a
  . backend/.env.dev
  set +a
else
  echo "[WARN] 未找到 backend/.env.dev，跳过加载（不影响容器启动）"
fi


# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查必要的命令
check_dependencies() {
    log_info "检查依赖..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装或未在PATH中"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose未安装或未在PATH中"
        exit 1
    fi

    log_success "所有依赖检查通过"
}

# 启动所有服务
start_services() {
    log_info "正在使用 Docker-Compose 启动所有服务..."

    # 停止并移除旧容器，以防冲突
    docker-compose down

    # 构建并启动所有服务
    docker-compose up -d --build

    log_info "等待服务启动并检查健康状态..."

    MAX_ATTEMPTS=20
    for ((ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++)); do
        log_info "检查服务状态... (尝试次数: $ATTEMPT/$MAX_ATTEMPTS)"

        STATUS_OUTPUT=$(docker-compose ps)

        if echo "$STATUS_OUTPUT" | grep -q "unhealthy"; then
            log_error "部分容器健康检查失败。请运行 'docker-compose logs' 查看详情。"
            docker-compose ps
            exit 1
        fi

        if ! echo "$STATUS_OUTPUT" | grep -q "starting"; then
            log_success "所有服务已成功启动并通过健康检查。"
            return
        fi

        if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
            log_info "部分服务仍在启动中，10秒后重试..."
            sleep 10
        fi
    done

    log_error "部分容器启动超时。请运行 'docker-compose logs' 查看详情。"
    docker-compose ps
    exit 1
}

# 显示服务状态
show_status() {
    echo
    echo "=== 服务状态 ==="
    echo -e "${GREEN}✓ 所有服务已在 Docker 容器中运行${NC}"
    echo -e "  - ${GREEN}后端API:${NC} http://localhost:8001"
    echo -e "  - ${GREEN}前端应用:${NC} http://localhost:5173 (如果已在docker-compose.yml中配置)"
    echo -e "  - ${GREEN}API文档:${NC} http://localhost:8001/docs"
    echo
    echo "=== 查看日志 ==="
    echo "运行 'docker-compose logs -f' 查看所有服务的实时日志"
    echo "运行 'docker-compose logs -f <service_name>' 查看特定服务的日志 (例如: backend, nginx)"
    echo
    echo "=== 停止服务 ==="
    echo "运行 './stop.sh' 或 'docker-compose down' 停止所有服务"
    echo
}

# 主函数
main() {
    check_dependencies
    start_services
    show_status

    log_success "ACRAC项目启动完成！"
}

# 错误处理
trap 'log_error "启动过程中发生错误，请检查日志"; exit 1' ERR

# 运行主函数
main "$@"