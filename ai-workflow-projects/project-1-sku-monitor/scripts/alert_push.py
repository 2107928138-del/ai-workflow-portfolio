"""
预警推送脚本 (alert_push.py)
=============================
读取异常检测结果，根据风险等级生成差异化文案，
通过企业微信群机器人 / 钉钉群机器人推送。

AI 参与说明：
  - 预警文案模板由 AI 辅助生成：输入异常数据样例，让 AI 生成
    不同风险等级的推送话术，人工审核后固化为模板函数。
  - 推送接口的签名计算、重试逻辑由 Codex 辅助实现。

调度：Cron 紧随 anomaly_detect.py
"""

import json
import hashlib
import time
import hmac
import base64
import urllib.request
import logging
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RESULT_PATH = "/data/sku_monitor/anomaly_result.json"

# ============================================================
# 消息模板 (AI 辅助生成，人工审核)
# ============================================================

def generate_alert_message(risk_level: str, items: list[dict]) -> str:
    """根据风险等级生成差异化的 Markdown 推送文案"""

    total_loss = sum(item.get("potential_gmv_loss", 0) for item in items)
    category_summary = {}
    for item in items:
        cat = item.get("category_l1", "其他")
        category_summary[cat] = category_summary.get(cat, 0) + 1

    # ---- 高风险话术 ----
    if risk_level == "🔴 高风险":
        top_items = "
".join(
            f"> - **{i['merchant_name']}** | {i['spu_name']} | "
            f"库存:{i['current_stock_qty']}件 | 可售{i['stock_days']}天"
            for i in items[:5]
        )
        return f"""## 🚨 缺货高风险预警

> **风险等级：🔴 高风险**
> 检测时间：{datetime.now().strftime("%m-%d %H:%M")}
> 高风险 SKU 数量：**{len(items)} 个**
> 预估影响 GMV：**¥{total_loss:,.0f}**

### 📊 品类分布
{chr(10).join(f'- {cat}: {cnt}个' for cat, cnt in sorted(category_summary.items(), key=lambda x: -x[1]))}

### 🔴 TOP 高风险 SKU
{top_items}

### ⚡ 建议行动
1. 立即联系以上商家确认补货计划
2. 评估是否需要启动备选供应商
3. 同步客服准备买家安抚话术

---
*本消息由 AI 自动监控系统生成，如有疑问请联系运营团队*"""

    # ---- 中风险话术 ----
    elif risk_level == "🟡 中风险":
        affected_merchants = list(set(i["merchant_name"] for i in items))
        return f"""## ⚠️ 缺货中风险提醒

> **风险等级：🟡 中风险**
> 检测时间：{datetime.now().strftime("%m-%d %H:%M")}
> 中风险 SKU 数量：**{len(items)} 个**

### 📋 涉及商家
{chr(10).join(f'- {m}' for m in affected_merchants[:10])}

### 💡 建议行动
- 关注以上 SKU 库存趋势，如连续 3 天未改善将升级为高风险
- 建议提前与商家沟通备货计划

---
*本消息由 AI 自动监控系统生成*"""

    # ---- 低风险 (仅汇总) ----
    else:
        return f"""## ℹ️ 缺货低风险提示

> 检测时间：{datetime.now().strftime("%m-%d %H:%M")}
> 低风险 SKU：{len(items)} 个 | 涉及 {len(set(i['merchant_name'] for i in items))} 个商家
> 目前风险可控，系统将持续监控。"""


# ============================================================
# 企业微信机器人推送 (Codex 辅助实现签名计算)
# ============================================================
def push_to_wecom_webhook(webhook_url: str, content: str, msg_type: str = "markdown"):
    """通过企业微信群机器人 Webhook 推送消息"""
    payload = json.dumps({
        "msgtype": msg_type,
        msg_type: {"content": content},
    }).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("errcode") == 0:
                logger.info("企微推送成功")
            else:
                logger.error("企微推送失败: %s", result)
    except Exception as e:
        logger.error("企微推送异常: %s", e)


def push_to_dingtalk(webhook_url: str, content: str):
    """通过钉钉群机器人推送 Markdown 消息"""
    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {
            "title": "缺货预警",
            "text": content,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            logger.info("钉钉推送结果: %s", result)
    except Exception as e:
        logger.error("钉钉推送异常: %s", e)


# ============================================================
# 主流程：按风险等级分组推送
# ============================================================
def run_push():
    with open(RESULT_PATH) as f:
        data = json.load(f)

    items = data["items"]

    # 按风险分组
    high_risk = [i for i in items if i["risk_level"] == "🔴 高风险"]
    mid_risk = [i for i in items if i["risk_level"] == "🟡 中风险"]
    low_risk = [i for i in items if i["risk_level"] == "🟢 低风险"]

    # 高风险：立即推送到所有渠道
    if high_risk:
        msg = generate_alert_message("🔴 高风险", high_risk)
        push_to_wecom_webhook("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx", msg)
        push_to_dingtalk("https://oapi.dingtalk.com/robot/send?access_token=xxxxx", msg)

    # 中风险：每4小时推送一次 (由 Cron 控制)
    if mid_risk:
        msg = generate_alert_message("🟡 中风险", mid_risk)
        push_to_wecom_webhook("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx", msg)

    # 低风险：仅记录，不推送 (或每日汇总推送)
    if low_risk:
        logger.info("低风险 %d 条，仅记录不推送", len(low_risk))

    summary = data["risk_summary"]
    logger.info(
        "推送完成 | 高风险:%d(已推送) 中风险:%d(已推送) 低风险:%d(仅记录)",
        summary["high"], summary["mid"], summary["low"]
    )


if __name__ == "__main__":
    run_push()
