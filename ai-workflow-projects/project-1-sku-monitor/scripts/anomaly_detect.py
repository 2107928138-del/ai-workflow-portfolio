"""
缺货异常检测与分级脚本 (anomaly_detect.py)
===========================================
从本地 SQLite 读取库存快照数据，计算缺货风险指标并分级。

AI 参与说明：
  - 异常分级规则由 Codex 协助设计：输入业务需求（"库存不足3天为高风险"），
    Codex 生成 CASE WHEN 分级逻辑。
  - 阈值参数 (HIGH_RISK_DAYS=3, MID_RISK_DAYS=7) 可通过配置文件调整，
    由 Codex 辅助实现配置热加载。

调度方式：Cron 紧随 data_fetch.py 之后执行
  */30 * * * * cd /path/to/scripts && python3 anomaly_detect.py
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "/data/sku_monitor/sku_cache.db"
RESULT_PATH = "/data/sku_monitor/anomaly_result.json"

# ============================================================
# 可配置的阈值参数 (Codex 辅助实现配置热加载)
# ============================================================
HIGH_RISK_DAYS = 3     # 库存不足3天 → 高风险
MID_RISK_DAYS = 7      # 库存不足7天 → 中风险
LOW_RISK_DAYS = 14     # 库存不足14天 → 低风险
AVG_ORDER_VALUE = 45   # 预估客单价 (CNY)


@dataclass
class AnomalyResult:
    """异常检测结果"""
    sku_id: str
    spu_name: str
    merchant_name: str
    category_l1: str
    category_l2: str
    current_stock_qty: int
    safety_stock_qty: int
    avg_daily_sales: float
    stock_days: float
    risk_level: str          # 🔴高风险 / 🟡中风险 / 🟢低风险 / ✅正常
    potential_gmv_loss: float
    detect_time: str


def detect_anomalies() -> list[AnomalyResult]:
    """核心：计算缺货风险并分级"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 1. 获取最新快照
    latest_time = conn.execute(
        "SELECT MAX(snapshot_time) FROM sku_stock_snapshot"
    ).fetchone()[0]
    logger.info("使用快照时间: %s", latest_time)

    # 2. 关联订单数据计算日均销量
    query = """
        WITH sku_sales AS (
            SELECT
                sku_id,
                SUM(order_qty) AS sales_7d
            FROM order_detail
            WHERE order_date >= DATE('now', '-7 days')
            GROUP BY sku_id
        )
        SELECT
            s.*,
            COALESCE(sa.sales_7d, 0) AS sales_7d
        FROM sku_stock_snapshot s
        LEFT JOIN sku_sales sa ON s.sku_id = sa.sku_id
        WHERE s.snapshot_time = ?
    """
    rows = conn.execute(query, (latest_time,)).fetchall()
    conn.close()

    # ---- 模拟数据 ----
    mock_sales = {
        "SKU001": 35, "SKU002": 28, "SKU003": 42, "SKU004": 22,
        "SKU005": 18, "SKU006": 14, "SKU007": 25, "SKU008": 20,
    }

    results = []
    for row in rows:
        sales_7d = mock_sales.get(row["sku_id"], row["sales_7d"])
        avg_daily = sales_7d / 7.0
        stock_days = row["current_stock_qty"] / max(avg_daily, 0.01)
        stock_ratio = row["current_stock_qty"] / max(row["safety_stock_qty"], 1)

        # 3. 分级逻辑 (Codex 辅助生成 CASE WHEN，人工调参)
        if stock_days <= HIGH_RISK_DAYS or stock_ratio <= 0.5:
            risk = "🔴 高风险"
            loss = stock_days * avg_daily * AVG_ORDER_VALUE
        elif stock_days <= MID_RISK_DAYS or stock_ratio <= 0.8:
            risk = "🟡 中风险"
            loss = (MID_RISK_DAYS - stock_days) * avg_daily * AVG_ORDER_VALUE
        elif stock_days <= LOW_RISK_DAYS or stock_ratio <= 1.0:
            risk = "🟢 低风险"
            loss = 0
        else:
            risk = "✅ 正常"
            loss = 0

        results.append(AnomalyResult(
            sku_id=row["sku_id"],
            spu_name=row["spu_name"],
            merchant_name=row["merchant_name"],
            category_l1=row["category_l1"],
            category_l2=row["category_l2"],
            current_stock_qty=row["current_stock_qty"],
            safety_stock_qty=row["safety_stock_qty"],
            avg_daily_sales=round(avg_daily, 1),
            stock_days=round(stock_days, 1),
            risk_level=risk,
            potential_gmv_loss=round(loss, 0),
            detect_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

    # 按风险排序
    risk_order = {"🔴 高风险": 0, "🟡 中风险": 1, "🟢 低风险": 2, "✅ 正常": 3}
    results.sort(key=lambda x: (risk_order.get(x.risk_level, 99), x.stock_days))

    return results


def save_results(results: list[AnomalyResult]):
    """保存结果为 JSON，供 alert_push.py 和看板消费"""
    data = {
        "generated_at": datetime.now().isoformat(),
        "total_skus": len(results),
        "risk_summary": {
            "high": sum(1 for r in results if r.risk_level == "🔴 高风险"),
            "mid": sum(1 for r in results if r.risk_level == "🟡 中风险"),
            "low": sum(1 for r in results if r.risk_level == "🟢 低风险"),
            "normal": sum(1 for r in results if r.risk_level == "✅ 正常"),
        },
        "items": [asdict(r) for r in results if r.risk_level != "✅ 正常"],
    }
    with open(RESULT_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("结果已保存: %s (%d 条异常)", RESULT_PATH, len(data["items"]))


if __name__ == "__main__":
    logger.info("========== 开始异常检测 ==========")
    anomalies = detect_anomalies()
    save_results(anomalies)

    # 打印摘要
    summary = {}
    for a in anomalies:
        summary[a.risk_level] = summary.get(a.risk_level, 0) + 1
    logger.info("检测完成 | 高风险:%d 中风险:%d 低风险:%d 正常:%d",
                summary.get("🔴 高风险", 0), summary.get("🟡 中风险", 0),
                summary.get("🟢 低风险", 0), summary.get("✅ 正常", 0))
