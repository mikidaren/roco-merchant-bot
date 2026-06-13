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
    1: "🌅 早班 08-12",
    2: "☀️ 午班 12-16",
    3: "🌇 晚班 16-20",
    4: "🌙 夜班 20-00",
}

EXCLUDE_NAMES = {"残缺魔镜", "适格钥匙", "能力钥匙", "魔力果"}
EXCLUDE_KEYWORDS = {"粉尘"}


def fetch_merchant():
    resp = requests.get(API_URL, timeout=15, headers={"User-Agent": "RocoMerchantBot/1.0"})
    resp.raise_for_status()
    return resp.json()


def should_show(item):
    name = item.get("name", "")
    category = item.get("category", "")
    if name in EXCLUDE_NAMES:
        return False
    if any(kw in name or kw in category for kw in EXCLUDE_KEYWORDS):
        return False
    return True


def format_message(data: dict) -> tuple:
    now = datetime.now(BEIJING_TZ)
    current_round = data.get("round", "?")
    round_label = ROUND_NAMES.get(current_round, f"第{current_round}轮")

    if data.get("status") != "open":
        return f"❌ 未营业 {now.strftime('%m-%d %H:%M')}", ""

    items = [i for i in data.get("items", []) if should_show(i)]

    title = f"{round_label}  {now.strftime('%m-%d %H:%M')}"

    if not items:
        return title, "🏪 本轮无关注商品"

    lines = ["🏪 远行商人"]
    for item in items:
        name = item.get("name", "?")
        price = item.get("priceRaw", item.get("price", "?"))
        limit = item.get("limit", "?")
        lines.append(f"• {name}  {price}贝  限{limit}")

    return title, "\n".join(lines)


def push_serverchan(send_key: str, title: str, content: str):
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": content}, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0:
            print("✅ 推送成功")
        else:
            print(f"⚠️ 返回: {result}", file=sys.stderr)
    except Exception as e:
        print(f"❌ 推送失败: {e}", file=sys.stderr)


def main():
    key = os.environ.get("SERVERCHAN_KEY", "")
    if not key:
        print("❌ SERVERCHAN_KEY 未配置", file=sys.stderr)
        sys.exit(1)

    data = fetch_merchant()
    title, content = format_message(data)
    print(f"标题: {title}")
    print(content)
    print()
    push_serverchan(key, title, content)


if __name__ == "__main__":
    main()
