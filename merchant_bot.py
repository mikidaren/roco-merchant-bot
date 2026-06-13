#!/usr/bin/env python3
"""
洛克王国手游 - 远行商人 QQ 推送机器人
=======================================
数据源: rocokingdomworld.org (聚合好游快爆等数据)
协议: OneBot v11 (兼容 NapCatQQ / Lagrange / go-cqhttp)
定时: 每轮刷新时自动推送当前在售商品
"""

import json
import time
import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import schedule

# ─── 配置 ───────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config.json"
BEIJING_TZ = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("roco-merchant")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CFG = load_config()


# ─── OneBot API 封装 ─────────────────────────────────────

class OneBotClient:
    """轻量 OneBot v11 HTTP 客户端"""

    def __init__(self, base_url: str, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.headers = {}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def _post(self, action: str, payload: dict) -> dict:
        url = f"{self.base_url}/{action}"
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("retcode") != 0:
                log.warning(f"OneBot API 返回异常: {data}")
            return data
        except Exception as e:
            log.error(f"OneBot API 调用失败 [{action}]: {e}")
            return {"retcode": -1, "msg": str(e)}

    def send_group_msg(self, group_id: int, message: str):
        return self._post("send_group_msg", {"group_id": group_id, "message": message})

    def send_private_msg(self, user_id: int, message: str):
        return self._post("send_private_msg", {"user_id": user_id, "message": message})


bot = OneBotClient(CFG["onebot_url"], CFG.get("access_token", ""))


# ─── 远行商人数据获取 ────────────────────────────────────

def fetch_merchant_data() -> dict | None:
    """从 API 获取当前远行商人数据"""
    try:
        resp = requests.get(CFG["merchant_api"], timeout=15, headers={
            "User-Agent": "RocoMerchantBot/1.0"
        })
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"获取商人数据失败: {e}")
        return None


# ─── 消息格式化 ──────────────────────────────────────────

ROUND_NAMES = {
    1: "🌅 早班 (08:00-12:00)",
    2: "☀️ 午班 (12:00-16:00)",
    3: "🌇 晚班 (16:00-20:00)",
    4: "🌙 夜班 (20:00-00:00)",
}


def format_merchant_message(data: dict) -> str:
    """将商人数据格式化为 QQ 消息"""
    now = datetime.now(BEIJING_TZ)
    current_round = data.get("round", "?")
    round_label = ROUND_NAMES.get(current_round, f"第{current_round}轮")
    status = data.get("status", "unknown")

    if status != "open":
        return (
            f"🏪 【洛克王国·远行商人】\n"
            f"⏰ {now.strftime('%Y-%m-%d %H:%M')}\n"
            f"❌ 商人当前未营业\n"
            f"下次刷新: {data.get('nextRefreshBeijing', '未知')}"
        )

    items = data.get("items", [])
    next_refresh = data.get("nextRefreshBeijing", "未知")
    position = data.get("merchantPosition", "")

    lines = [
        f"🏪 【洛克王国·远行商人】",
        f"⏰ {now.strftime('%Y-%m-%d %H:%M')}  |  {round_label}",
    ]

    if position:
        lines.append(f"📍 位置: {position}")

    lines.append(f"🔄 下次刷新: {next_refresh}")
    lines.append("")
    lines.append("📦 当前在售商品：")
    lines.append("")

    for i, item in enumerate(items, 1):
        name = item.get("name", "未知")
        price = item.get("priceRaw", item.get("price", "?"))
        limit = item.get("limit", "?")
        category = item.get("category", "")

        # 高亮稀有/贵重物品
        price_num = 0
        try:
            price_num = int(item.get("price", "0"))
        except ValueError:
            pass

        prefix = "⭐" if price_num >= 100000 else "•"

        line = f"{prefix} {name}  💰{price}贝  📦限{limit}个"
        if category:
            line += f"\n   🏷️{category}"
        lines.append(line)

    lines.append("")
    lines.append("💡 提示: 每4小时刷新一轮，8/12/16/20点后查看")

    return "\n".join(lines)


# ─── 推送逻辑 ────────────────────────────────────────────

last_push_round = None  # 避免同一轮重复推送


def push_merchant_info():
    """获取数据并推送到所有目标"""
    global last_push_round

    log.info("开始获取远行商人数据...")
    data = fetch_merchant_data()
    if not data:
        log.warning("获取数据失败，跳过本次推送")
        return

    current_round = data.get("round")
    if current_round == last_push_round:
        log.info(f"第{current_round}轮已推送过，跳过")
        return

    message = format_merchant_message(data)
    log.info(f"推送第{current_round}轮商人信息...")

    # 推送到群
    for group_id in CFG.get("target_groups", []):
        bot.send_group_msg(group_id, message)
        log.info(f"  → 群 {group_id} 已推送")

    # 推送到私聊
    for user_id in CFG.get("target_users", []):
        bot.send_private_msg(user_id, message)
        log.info(f"  → 用户 {user_id} 已推送")

    last_push_round = current_round
    log.info("推送完成")


# ─── 手动查询命令响应（可选）────────────────────────────

def handle_manual_query():
    """供外部调用：获取当前商人信息文本"""
    data = fetch_merchant_data()
    if not data:
        return "❌ 获取商人数据失败，请稍后再试"
    return format_merchant_message(data)


# ─── 定时任务调度 ─────────────────────────────────────────

def setup_schedule():
    """设置定时推送任务"""
    push_times = CFG.get("push_times", ["08:00", "12:00", "16:00", "20:00"])
    for t in push_times:
        schedule.every().day.at(t).do(push_merchant_info)
        log.info(f"  已注册定时推送: {t}")


def run_scheduler():
    """运行调度循环"""
    interval = CFG.get("check_interval_seconds", 60)
    log.info(f"调度器启动，检查间隔 {interval}s")
    while True:
        schedule.run_pending()
        time.sleep(interval)


# ─── 优雅退出 ────────────────────────────────────────────

def signal_handler(sig, frame):
    log.info("收到退出信号，正在停止...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ─── 入口 ────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 50)
    log.info("洛克王国·远行商人 QQ 推送机器人 v1.0")
    log.info("=" * 50)
    log.info(f"OneBot 地址: {CFG['onebot_url']}")
    log.info(f"推送时间: {CFG.get('push_times')}")
    log.info(f"目标群: {CFG.get('target_groups')}")
    log.info(f"目标用户: {CFG.get('target_users')}")

    # 首次启动立即推送一次
    log.info("首次启动，立即推送当前商人信息...")
    push_merchant_info()

    # 设置定时任务
    setup_schedule()

    # 运行调度器
    run_scheduler()
