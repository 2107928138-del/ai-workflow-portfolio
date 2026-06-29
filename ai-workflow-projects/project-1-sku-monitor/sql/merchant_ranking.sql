-- ============================================================
-- 高风险商家排行榜
-- 用途：按商家维度聚合缺货 SKU 数量，输出 TOP 问题商家
-- ============================================================

WITH risk_skus AS (
    -- 复用 sku_daily_monitor.sql 的 risk_classify CTE 逻辑
    -- ...（省略重复 CTE，实际生产环境中使用视图）
    SELECT
        merchant_id,
        merchant_name,
        risk_level,
        COUNT(*) AS risk_sku_count,
        SUM(potential_gmv_loss) AS total_gmv_loss
    FROM vw_sku_risk_daily  -- 生产环境已固化为视图
    WHERE risk_level != '✅ 正常'
    GROUP BY merchant_id, merchant_name, risk_level
)

SELECT
    merchant_name,
    SUM(CASE WHEN risk_level = '🔴 高风险' THEN risk_sku_count ELSE 0 END) AS high_risk_cnt,
    SUM(CASE WHEN risk_level = '🟡 中风险' THEN risk_sku_count ELSE 0 END) AS mid_risk_cnt,
    SUM(CASE WHEN risk_level = '🟢 低风险' THEN risk_sku_count ELSE 0 END) AS low_risk_cnt,
    SUM(risk_sku_count) AS total_risk_cnt,
    ROUND(SUM(total_gmv_loss), 0) AS total_gmv_loss_cny
FROM risk_skus
GROUP BY merchant_name
ORDER BY high_risk_cnt DESC, total_risk_cnt DESC
LIMIT 20;
