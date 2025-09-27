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

# 选择 docker compose 命令
select_dc() {
    if command -v docker-compose >/dev/null 2>&1; then
        echo docker-compose
    else
        # prefer docker compose v2
        if docker compose version >/dev/null 2>&1; then
            echo "docker compose"
        else
            echo docker-compose
        fi
    fi
}

# 端口占用检测（尽量友好，若被占用则退出并提示使用合适脚本）
port_in_use() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i TCP:${port} -sTCP:LISTEN >/dev/null 2>&1
        return $?
    else
        # 尝试 bash tcp 探测
        (echo >/dev/tcp/127.0.0.1/${port}) >/dev/null 2>&1 && return 0 || return 1
    fi
}

# 检查必要的命令与文件
check_dependencies() {
    log_info "检查依赖..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker未安装或未在PATH中"
        exit 1
    fi

    # docker compose / docker-compose 二选一
    DC="$(select_dc)"
    log_info "使用Compose命令: $DC"

    log_success "所有依赖检查通过"
}

# 启动所有服务
start_services() {
    log_info "正在使用 Docker-Compose 启动所有服务..."

    # 防冲突：常见端口 8001 / 5173 / 8080 如被本地进程占用，提示使用 start-dev.sh 或释放端口
    if port_in_use 8001; then
        log_error "检测到本机 8001 端口被占用。若正在本地运行后端 dev，请使用 ./start-dev.sh，或释放端口后再运行 ./start.sh。"
        exit 1
    fi
    if port_in_use 5173; then
        log_error "检测到本机 5173 端口被占用。若正在本地运行前端 dev，请使用 ./start-dev.sh，或释放端口后再运行 ./start.sh。"
        exit 1
    fi
    if port_in_use 8080; then
        log_error "检测到本机 8080 端口被占用（Nginx 将无法绑定）。请释放端口后再运行 ./start.sh，或关闭冲突进程。"
        exit 1
    fi

    # 停止并移除旧容器，以防冲突
    $DC down

    # 构建并启动所有服务
    $DC up -d --build

    log_info "等待服务启动并检查健康状态..."

    MAX_ATTEMPTS=20
    for ((ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++)); do
        log_info "检查服务状态... (尝试次数: $ATTEMPT/$MAX_ATTEMPTS)"

        STATUS_OUTPUT=$($DC ps)

        if echo "$STATUS_OUTPUT" | grep -q "unhealthy"; then
            log_error "部分容器健康检查失败。请运行 'docker-compose logs' 查看详情。"
            $DC ps
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
    $DC ps
    exit 1
}

# 显示服务状态
show_status() {
    echo
    echo "=== 服务状态 ==="
    echo -e "${GREEN}✓ 所有服务已在 Docker 容器中运行${NC}"
    echo -e "  - ${GREEN}后端API:${NC} http://localhost:8001"
    echo -e "  - ${GREEN}前端应用:${NC} http://localhost:8080 (Nginx) 或 http://localhost:5173"
    echo -e "  - ${GREEN}API文档:${NC} http://localhost:8080/docs （或直连 http://localhost:8001/docs）"
    echo
    echo "=== 查看日志 ==="
    echo "运行 '$DC logs -f' 查看所有服务的实时日志"
    echo "运行 '$DC logs -f <service_name>' 查看特定服务的日志 (例如: backend, nginx)"
    echo
    echo "=== 停止服务 ==="
    echo "运行 './stop.sh' 或 'docker-compose down' 停止所有服务"
    echo
}

# 主函数
main() {
    check_dependencies

    # 预检：确保容器内使用docker环境变量而非本地.env
    if [ -f "backend/.env.docker" ]; then
        if ! grep -q "DOCKER_CONTEXT" backend/.env.docker; then
            log_info "为 backend/.env.docker 添加 DOCKER_CONTEXT=true 与 SKIP_LOCAL_DOTENV=true 可避免容器读取本地 .env"
        fi
    fi

    # 预检：可选检测宿主机 Ollama 是否可达
    if command -v curl >/dev/null 2>&1; then
        if curl -sSf http://localhost:11434/api/tags >/dev/null 2>&1 || curl -sSf http://localhost:11434/v1/models >/dev/null 2>&1; then
            log_info "检测到宿主机 Ollama 运行中 (localhost:11434)"
        else
            log_info "未检测到宿主机 Ollama（可忽略，若使用 SiliconFlow 则无需）"
        fi
    fi

    start_services
    # 基础可达性校验：检测 Nginx 与后端健康接口
    if command -v curl >/dev/null 2>&1; then
        if ! curl -sSf http://localhost:8080 >/dev/null 2>&1; then
            log_error "Nginx(8080) 无法访问。可能原因：端口被占用、Nginx配置错误或前端未就绪。建议执行: 'docker-compose logs nginx frontend' 排查。"
        fi
        # 使用轻量健康检查端点，降低误报
        if ! curl -sSf http://localhost:8001/health >/dev/null 2>&1; then
            log_error "后端健康检查失败。请执行: '$DC logs backend' 排查。"
        fi
    fi
    show_status

    log_success "ACRAC项目启动完成！"
}

# 错误处理
trap 'log_error "启动过程中发生错误，请检查日志"; exit 1' ERR

# 端口占用检测（尽量友好，若被占用则退出并提示使用合适脚本）
port_in_use() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -i TCP:${port} -sTCP:LISTEN >/dev/null 2>&1
        return $?
    else
        # 尝试 nc 探测
        (echo >/dev/tcp/127.0.0.1/${port}) >/dev/null 2>&1 && return 0 || return 1
    fi
}

# 运行主函数
main "$@"
