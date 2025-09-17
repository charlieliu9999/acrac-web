#!/bin/bash

# ACRAC项目开发环境启动脚本
# 启动数据库服务 + 独立的前端和后端开发服务器

set -e  # 遇到错误立即退出

echo "=== ACRAC项目开发环境启动脚本 ==="
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
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

    # 尝试加载nvm
    if [ -f ~/.nvm/nvm.sh ]; then
        source ~/.nvm/nvm.sh
        nvm use node >/dev/null 2>&1 || true
    fi

    if ! command -v node &> /dev/null; then
        log_error "Node.js未安装或未在PATH中"
        log_info "请安装Node.js或确保nvm已正确配置"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        log_error "Python3未安装或未在PATH中"
        exit 1
    fi

    log_success "所有依赖检查通过"
}

# 创建日志目录
create_log_dir() {
    mkdir -p logs
}

# 停止现有进程
stop_existing_processes() {
    log_info "停止现有进程..."

    # 停止前端进程
    if [ -f "logs/frontend.pid" ]; then
        FRONTEND_PID=$(cat logs/frontend.pid)
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID
            log_info "已停止前端进程 (PID: $FRONTEND_PID)"
        fi
        rm -f logs/frontend.pid
    fi

    # 停止后端进程
    if [ -f "logs/backend.pid" ]; then
        BACKEND_PID=$(cat logs/backend.pid)
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            log_info "已停止后端进程 (PID: $BACKEND_PID)"
        fi
        rm -f logs/backend.pid
    fi

    # 强制终止相关进程
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "node.*vite" 2>/dev/null || true
}

# 启动数据库服务
start_database() {
    log_info "启动数据库服务..."

    # 只启动数据库相关容器
    docker-compose up -d postgres redis

    # 等待数据库启动
    log_info "等待数据库启动..."
    sleep 5

    # 检查数据库健康状态
    MAX_ATTEMPTS=10
    for ((ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++)); do
        if docker-compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            log_success "数据库启动成功"
            return
        fi

        if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
            log_info "等待数据库启动... (尝试 $ATTEMPT/$MAX_ATTEMPTS)"
            sleep 3
        fi
    done

    log_error "数据库启动超时"
    exit 1
}

# 启动后端服务
start_backend() {
    log_info "启动后端服务..."

    cd backend

    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
    fi

    # 激活虚拟环境并安装依赖
    source venv/bin/activate

    # 检查是否需要安装依赖
    if [ ! -f "venv/.deps_installed" ] || [ requirements.txt -nt venv/.deps_installed ]; then
        log_info "安装Python依赖..."
        pip install -r requirements.txt
        touch venv/.deps_installed
    fi

    # 启动后端服务
    log_info "启动后端API服务 (端口: 8001)..."
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../logs/backend.pid

    cd ..

    # 等待后端启动
    log_info "等待后端服务启动..."
    sleep 5

    # 检查后端健康状态
    MAX_ATTEMPTS=10
    for ((ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++)); do
        if curl -s http://localhost:8001/api/v1/acrac/health >/dev/null 2>&1; then
            log_success "后端服务启动成功 (PID: $BACKEND_PID)"
            return
        fi

        if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
            log_info "等待后端服务启动... (尝试 $ATTEMPT/$MAX_ATTEMPTS)"
            sleep 3
        fi
    done

    log_error "后端服务启动超时"
    exit 1
}

# 启动前端服务
start_frontend() {
    log_info "启动前端服务..."

    cd frontend

    # 确保使用正确的Node.js版本
    if [ -f ~/.nvm/nvm.sh ]; then
        source ~/.nvm/nvm.sh
        nvm use node >/dev/null 2>&1 || true
    fi

    # 检查是否需要安装依赖
    if [ ! -d "node_modules" ] || [ package.json -nt node_modules/.package-lock.json ]; then
        log_info "安装前端依赖..."
        npm install
        touch node_modules/.package-lock.json
    fi

    # 启动前端开发服务器
    log_info "启动前端开发服务器 (端口: 5173)..."
    nohup npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../logs/frontend.pid

    cd ..

    # 等待前端启动
    log_info "等待前端服务启动..."
    sleep 8

    # 检查前端服务状态
    MAX_ATTEMPTS=10
    for ((ATTEMPT=1; ATTEMPT<=MAX_ATTEMPTS; ATTEMPT++)); do
        if curl -s http://localhost:5173 >/dev/null 2>&1; then
            log_success "前端服务启动成功 (PID: $FRONTEND_PID)"
            return
        fi

        if [ $ATTEMPT -lt $MAX_ATTEMPTS ]; then
            log_info "等待前端服务启动... (尝试 $ATTEMPT/$MAX_ATTEMPTS)"
            sleep 3
        fi
    done

    log_warning "前端服务可能仍在启动中，请稍后检查"
}

# 显示服务状态
show_status() {
    echo
    echo "=== 开发环境服务状态 ==="
    echo -e "${GREEN}✓ 所有服务已启动${NC}"
    echo
    echo "=== 服务访问地址 ==="
    echo -e "  - ${GREEN}前端应用:${NC} http://localhost:5173"
    echo -e "  - ${GREEN}后端API:${NC} http://localhost:8001"
    echo -e "  - ${GREEN}API文档:${NC} http://localhost:8001/docs"
    echo -e "  - ${GREEN}数据库:${NC} localhost:5432 (postgres/password)"
    echo -e "  - ${GREEN}Redis:${NC} localhost:6379"
    echo
    echo "=== 日志文件 ==="
    echo -e "  - ${BLUE}后端日志:${NC} logs/backend.log"
    echo -e "  - ${BLUE}前端日志:${NC} logs/frontend.log"
    echo
    echo "=== 实用命令 ==="
    echo "  - 查看后端日志: tail -f logs/backend.log"
    echo "  - 查看前端日志: tail -f logs/frontend.log"
    echo "  - 停止所有服务: ./stop.sh"
    echo "  - 重启服务: ./restart.sh"
    echo
}

# 主函数
main() {
    check_dependencies
    create_log_dir
    stop_existing_processes
    start_database
    start_backend
    start_frontend
    show_status

    log_success "ACRAC开发环境启动完成！"
    echo
    log_info "提示: 前端支持热重载，后端支持自动重启"
    log_info "修改代码后会自动生效，无需手动重启服务"
}

# 错误处理
trap 'log_error "启动过程中发生错误，请检查日志"; exit 1' ERR

# 运行主函数
main "$@"
