#!/usr/bin/env bash
# 自动部署脚本 — 由 GitHub Webhook 触发
# 用法: ./deploy.sh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始自动部署..."

echo "[1/2] 拉取最新代码..."
git pull origin master

echo "[2/2] 重启服务（start.sh 会自动处理依赖和数据库）..."
sudo systemctl restart auto-deploy

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 部署完成"
