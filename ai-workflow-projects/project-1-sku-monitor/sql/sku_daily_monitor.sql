-- ============================================================
-- SKU 维度日度缺货率监控查询
-- 用途：每日自动运行，输出当前存在缺货风险的 SKU 清单
-- 调度：Cron 每日 08:00、14:00、20:00 执行
-- 说明：本 SQL 由 Codex 辅助生成，涵盖多表关联与窗口函数
-- ============================================================

WITH sku_base AS (
    -- 1. 获取近7天有销量的活跃 SKU 基础信息
    SELECT
        o.sku_id,
        o.spu_name,
        o.category_l1,
        o.category_l2,
        o.merchant_id,
        o.merchant_name,
        o.safety_stock_qty,           -- 安全库存阈值
        o.current_stock_qty,          -- 当前库存
        SUM(d.order_qty) AS sales_7d, -- 近7天销量
        COUNT(DISTINCT d.order_date) AS active_days_7d
    FROM dim_sku_info o
    INNER JOIN dwd_order_detail_di d
        ON o.sku_id = d.sku_id
        AND d.order_date >= DATE_SUB(CURRENT_DATE, 7)
    WHERE o.status = 'ONLINE'
    GROUP BY o.sku_id, o.spu_name, o.category_l1, o.category_l2,
             o.merchant_id, o.merchant_name,
             o.safety_stock_qty, o.current_stock_qty
),

sku_metrics AS (
    -- 2. 计算缺货风险指标
    SELECT
        *,
        ROUND(sales_7d / 7.0, 1) AS avg_daily_sales,     -- 日均销量
        ROUND(current_stock_qty * 1.0 / NULLIF(sales_7d / 7.0, 0), 1) AS stock_days,  -- 可售天数
        ROUND(current_stock_qty * 1.0 / NULLIF(safety_stock_qty, 0), 2) AS stock_ratio -- 库存/安全库存比
    FROM sku_base
),

risk_classify AS (
    -- 3. 缺货风险分级
    SELECT
        *,
        CASE
            WHEN stock_days <= 3  OR stock_ratio <= 0.5 THEN '🔴 高风险'
            WHEN stock_days <= 7  OR stock_ratio <= 0.8 THEN '🟡 中风险'
            WHEN stock_days <= 14 OR stock_ratio <= 1.0 THEN '🟢 低风险'
            ELSE '✅ 正常'
        END AS risk_level,
        CASE
            WHEN stock_days <= 3  THEN stock_days * avg_daily_sales * 45  -- 预估影响 GMV (客单价按45算)
            WHEN stock_days <= 7  THEN (7 - stock_days) * avg_daily_sales * 45
            ELSE 0
        END AS potential_gmv_loss
    FROM sku_metrics
)

-- 4. 最终输出：筛选有风险的 SKU，按严重程度排序
SELECT
    merchant_name,
    spu_name,
    sku_id,
    category_l1,
    category_l2,
    current_stock_qty,
    safety_stock_qty,
    avg_daily_sales,
    stock_days,
    stock_ratio,
    risk_level,
    ROUND(potential_gmv_loss, 0) AS potential_gmv_loss_cny
FROM risk_classify
WHERE risk_level != '✅ 正常'
ORDER BY
    CASE risk_level
        WHEN '🔴 高风险' THEN 1
        WHEN '🟡 中风险' THEN 2
        WHEN '🟢 低风险' THEN 3
    END,
    stock_days ASC
LIMIT 500;
