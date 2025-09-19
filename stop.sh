#!/bin/bash

# ACRAC项目停止脚本

set -e

echo "=== ACRAC项目停止脚本 ==="
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

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 选择 docker compose 命令
select_dc() {
    if command -v docker-compose >/dev/null 2>&1; then
        echo docker-compose
    else
        if docker compose version >/dev/null 2>&1; then
            echo "docker compose"
        else
            echo docker-compose
        fi
    fi
}

# 停止前端服务
stop_frontend() {
    log_info "停止前端服务..."
    
    if [ -f "logs/frontend.pid" ]; then
        FRONTEND_PID=$(cat logs/frontend.pid)
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID
            log_success "前端服务已停止 (PID: $FRONTEND_PID)"
        else
            log_warning "前端进程不存在"
        fi
        rm -f logs/frontend.pid
    fi
    
    # 强制终止相关进程
    pkill -f "vite" 2>/dev/null || true
    pkill -f "node.*vite" 2>/dev/null || true
}

# 停止后端服务
stop_backend() {
    log_info "停止后端服务..."
    
    if [ -f "logs/backend.pid" ]; then
        BACKEND_PID=$(cat logs/backend.pid)
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            log_success "后端服务已停止 (PID: $BACKEND_PID)"
        else
            log_warning "后端进程不存在"
        fi
        rm -f logs/backend.pid
    fi
    
    # 强制终止相关进程
    pkill -f "uvicorn" 2>/dev/null || true
}

# 停止数据库服务
stop_database() {
    log_info "停止数据库服务..."
    DC="$(select_dc)"
    $DC down
    
    log_success "数据库服务已停止"
}

# 清理日志文件
clean_logs() {
    log_info "清理日志文件..."
    
    if [ "$1" = "--clean-logs" ]; then
        rm -f logs/*.log
        log_success "日志文件已清理"
    else
        log_info "保留日志文件 (使用 --clean-logs 参数清理)"
    fi
}

# 显示停止状态
show_status() {
    echo
    echo "=== 停止完成 ==="
    echo -e "${GREEN}✓ 所有服务已停止${NC}"
    echo
    
    # 检查是否还有相关进程
    REMAINING=$(ps aux | grep -E '(uvicorn|vite|node.*vite)' | grep -v grep | wc -l)
    if [ $REMAINING -gt 0 ]; then
        log_warning "仍有 $REMAINING 个相关进程在运行"
        echo "运行以下命令查看："
        echo "ps aux | grep -E '(uvicorn|vite|node.*vite)' | grep -v grep"
    fi
}

# 主函数
main() {
    stop_frontend
    stop_backend
    stop_database
    clean_logs "$1"
    show_status
    
    log_success "ACRAC项目已完全停止！"
}

# 运行主函数
main "$@"
