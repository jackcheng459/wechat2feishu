#!/bin/bash

# WeChat2Feishu 一键安装脚本
# 适用系统：macOS, Linux

echo "🚀 欢迎使用 WeChat2Feishu 自动安装程序"
echo "--------------------------------------"

# 1. 检查 Python 环境
if ! command -v python3 &> /dev/null
then
    echo "❌ 错误：未检测到 Python3。请先前往 python.org 下载安装。"
    exit 1
fi

echo "📦 正在创建运行环境 (venv)..."
python3 -m venv .venv

echo "📥 正在安装必要插件 (dependencies)..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "🌐 正在安装网页采集引擎 (Playwright)..."
playwright install chromium

echo "--------------------------------------"
echo "✅ 安装成功！"
echo "👉 下一步：请修改项目中的 .env 文件，填入您的飞书 App 信息。"
echo "👉 然后运行：python auth.py login 进行首次授权。"
