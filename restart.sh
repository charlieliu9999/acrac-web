#!/bin/bash

# ACRAC项目快速重启脚本

set -e

echo "=== ACRAC项目快速重启脚本 ==="
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

# 主函数
main() {
    log_info "正在重启ACRAC项目..."
    
    # 停止所有服务
    log_info "停止现有服务..."
    ./stop.sh
    
    echo
    log_info "等待3秒后重新启动..."
    sleep 3
    
    # 重新启动
    log_info "重新启动服务..."
    ./start.sh
    
    log_success "ACRAC项目重启完成！"
}

# 检查脚本权限
if [ ! -x "./start.sh" ] || [ ! -x "./stop.sh" ]; then
    log_error "start.sh 或 stop.sh 没有执行权限"
    log_info "正在添加执行权限..."
    chmod +x start.sh stop.sh restart.sh
    log_success "执行权限已添加"
fi

# 运行主函数
main "$@"