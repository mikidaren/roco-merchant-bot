#!/usr/bin/env python3
"""
洛克王国·远行商人 微信推送脚本
供 GitHub Actions 调用，通过 Server酱 推送到微信
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

BEIJING_TZ = timezone(timedelta(hours=8))
API_URL = "https://rocokingdomworld.org/api/merchant/live"

ROUND_NAMES = {
    1: "🌅 早班 (08:00-12:00)",
    2: "☀️ 午班 (12:00-16:00)",
    3: "🌇 晚班 (16:00-20:00)",
    4: "🌙 夜班 (20:00-00:00)",
}


def fetch_merchant():
    resp = requests.get(API_URL, timeout=15, headers={"User-Agent": "RocoMerchantBot/1.0"})
    resp.raise_for_status()
    return resp.json()


def format_title(data: dict) -> str:
    """Server酱 标题（显示在微信通知栏）"""
    current_round = data.get("round", "?")
    round_label = ROUND_NAMES.get(current_round, f"第{current_round}轮")
    item_count = len(data.get("items", []))
    return f"🏪 远行商人 {round_label} | {item_count}件商品"


def format_message(data: dict) -> str:
    """Server酱 正文（Markdown 格式）"""
    now = datetime.now(BEIJING_TZ)
    current_round = data.get("round", "?")
    round_label = ROUND_NAMES.get(current_round, f"第{current_round}轮")
    status = data.get("status", "unknown")

    if status != "open":
        return (
            f"## ❌ 商人当前未营业\n\n"
            f"- 时间: {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"- 下次刷新: {data.get('nextRefreshBeijing', '未知')}"
        )

    items = data.get("items", [])
    next_refresh = data.get("nextRefreshBeijing", "未知")
    position = data.get("merchantPosition", "")

    lines = [
        f"## 🏪 洛克王国·远行商人",
        f"",
        f"- 时间: {now.strftime('%Y-%m-%d %H:%M')}",
        f"- 时段: {round_label}",
    ]
    if position:
        lines.append(f"- 位置: {position}")
    lines.append(f"- 下次刷新: {next_refresh}")
    lines.append("")
    lines.append("### 📦 当前在售商品")
    lines.append("")

    for item in items:
        name = item.get("name", "未知")
        price = item.get("priceRaw", item.get("price", "?"))
        limit = item.get("limit", "?")
        category = item.get("category", "")
        price_num = int(item.get("price", "0"))
        prefix = "⭐" if price_num >= 100000 else "•"

        line = f"{prefix} **{name}** — 💰{price}贝 | 限{limit}个"
        if category:
            line += f" `{category}`"
        lines.append(line)

    lines.append("")
    lines.append("---")
    lines.append("> 每4小时刷新一轮，8/12/16/20点后查看")
    return "\n".join(lines)


def push_serverchan(send_key: str, title: str, content: str):
    """通过 Server酱 推送到微信"""
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    payload = {
        "title": title,
        "desp": content,
    }
    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0:
            print(f"✅ Server酱推送成功")
        else:
            print(f"⚠️ Server酱返回: {result}", file=sys.stderr)
        return result
    except Exception as e:
        print(f"❌ Server酱推送失败: {e}", file=sys.stderr)
        return None


def main():
    push_method = os.environ.get("PUSH_METHOD", "serverchan")
    serverchan_key = os.environ.get("SERVERCHAN_KEY", "")

    print("📡 获取远行商人数据...")
    data = fetch_merchant()
    title = format_title(data)
    content = format_message(data)

    print(f"✅ 数据获取成功，第{data.get('round')}轮，共{len(data.get('items', []))}件商品")
    print()
    print(content)
    print()

    if push_method == "serverchan":
        if not serverchan_key:
            print("❌ SERVERCHAN_KEY 未配置", file=sys.stderr)
            sys.exit(1)
        print("📤 推送到微信...")
        push_serverchan(serverchan_key, title, content)
    else:
        print(f"⚠️ 未知推送方式: {push_method}", file=sys.stderr)
        sys.exit(1)

    print("✅ 完成")


if __name__ == "__main__":
    main()
