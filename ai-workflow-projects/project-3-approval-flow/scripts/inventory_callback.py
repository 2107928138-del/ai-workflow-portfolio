"""
库存 API 回写脚本 (inventory_callback.py)
=========================================
宜搭审批通过后，由 Webhook 触发本脚本，
将审批通过的库存变更写入库存系统。

AI 参与说明：
  - 本脚本由 Codex 辅助编写，包括：
    · HTTP 请求封装 (requests + retry)
    · HMAC 签名计算 (API 鉴权)
    · 事务日志记录
    · 异常处理与告警

部署方式：Flask 微服务 / 阿里云函数计算 (FC)
触发方式：宜搭审批通过 → Webhook POST → 本脚本
"""

import hashlib
import hmac
import json
import logging
import time
import requests
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# 配置 (Codex 辅助整理)
# ============================================================
INVENTORY_API_BASE = "https://inventory-api.internal.aliexpress.com"
API_SECRET = "sk-xxxxx"  # 生产环境从密钥管理服务获取
MAX_RETRIES = 3
RETRY_DELAY = 5  # 秒


# ============================================================
# API 鉴权 (Codex 辅助实现 HMAC 签名)
# ============================================================
def generate_signature(payload: dict, secret: str) -> str:
    """生成 HMAC-SHA256 请求签名"""
    message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ============================================================
# 库存回写
# ============================================================
def update_activity_stock(
    activity_id: str,
    merchant_id: str,
    sku_updates: list[dict],
    approved_by: str,
) -> dict:
    """
    调用库存系统 API 更新活动库存。

    Args:
        activity_id: 活动ID
        merchant_id: 商家ID
        sku_updates: [{"sku_id": "SKU001", "new_stock": 500}, ...]
        approved_by: 审批人

    Returns:
        API 响应
    """
    url = f"{INVENTORY_API_BASE}/v1/activity/{activity_id}/stock"
    payload = {
        "merchant_id": merchant_id,
        "sku_updates": sku_updates,
        "approved_by": approved_by,
        "approved_at": datetime.now().isoformat(),
        "source": "yida_approval_flow",
    }

    headers = {
        "Content-Type": "application/json",
        "X-Signature": generate_signature(payload, API_SECRET),
        "X-Request-Id": f"yda_{int(time.time() * 1000)}",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("回写请求 (第%d次): %d SKU → 活动 %s", attempt, len(sku_updates), activity_id)
            resp = requests.put(url, json=payload, headers=headers, timeout=30)
            result = resp.json()

            if resp.status_code == 200 and result.get("success"):
                logger.info("回写成功: %s", result.get("message"))
                return {"success": True, "data": result}
            else:
                logger.warning("回写失败 (HTTP %d): %s", resp.status_code, result)
        except Exception as e:
            logger.error("回写异常 (第%d次): %s", attempt, e)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    # 全部重试失败 → 告警
    logger.critical("库存回写最终失败，需人工介入！活动:%s 商家:%s", activity_id, merchant_id)
    return {"success": False, "error": "库存回写失败，已触发告警"}


# ============================================================
# 事务日志 (追溯审计)
# ============================================================
def log_transaction(data: dict, result: dict):
    """记录每次回写操作，用于审计追溯"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "activity_id": data.get("activity_id"),
        "merchant_id": data.get("merchant_id"),
        "sku_count": len(data.get("sku_updates", [])),
        "approved_by": data.get("approved_by"),
        "result": result,
    }
    # 生产环境写入数据库或日志系统
    logger.info("TRANSACTION_LOG: %s", json.dumps(log_entry, ensure_ascii=False))


# ============================================================
# Webhook 入口 (宜搭审批通过后调用)
# ============================================================
def handle_approval_callback(event: dict) -> dict:
    """
    处理宜搭审批通过后的 Webhook 回调。

    宜搭传入的 event 格式:
    {
        "formInstanceId": "xxx",
        "approvalResult": "agree",
        "formData": {
            "merchant_id": "M1001",
            "activity_name": "双12年终盛典",
            "total_change": 150,
            "sku_list": [
                {"sku_id": "SKU001", "requested_stock": 450},
                ...
            ]
        },
        "approver": "张三",
        "approvalTime": "2025-12-10T14:30:00"
    }
    """
    form_data = event.get("formData", {})
    merchant_id = form_data.get("merchant_id")
    activity_id = form_data.get("activity_name")  # 实际为 activity_id
    approver = event.get("approver", "system")

    # 构建 SKU 更新列表
    sku_updates = [
        {"sku_id": item["sku_id"], "new_stock": item["requested_stock"]}
        for item in form_data.get("sku_list", [])
    ]

    if not sku_updates:
        logger.warning("回调数据无 SKU 列表")
        return {"success": False, "error": "无 SKU 数据"}

    # 执行回写
    result = update_activity_stock(activity_id, merchant_id, sku_updates, approver)

    # 记录审计日志
    log_transaction({
        "activity_id": activity_id,
        "merchant_id": merchant_id,
        "sku_updates": sku_updates,
        "approved_by": approver,
    }, result)

    return result


# ============================================================
# 本地测试
# ============================================================
if __name__ == "__main__":
    # 模拟宜搭 Webhook 回调
    mock_event = {
        "formInstanceId": "INST-20251210-001",
        "approvalResult": "agree",
        "formData": {
            "merchant_id": "M1001",
            "activity_name": "double12_2025",
            "sku_list": [
                {"sku_id": "SKU001", "requested_stock": 450},
                {"sku_id": "SKU002", "requested_stock": 300},
            ],
        },
        "approver": "张三 (运营经理)",
        "approvalTime": "2025-12-10T14:30:00",
    }

    result = handle_approval_callback(mock_event)
    print("回写结果:", json.dumps(result, ensure_ascii=False, indent=2))
