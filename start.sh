#!/bin/bash
# 洛克王国·远行商人 QQ 推送机器人 启动脚本
cd "$(dirname "$0")"

# 如果没有虚拟环境，创建一个
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo "🚀 启动远行商人推送机器人..."
python3 merchant_bot.py
