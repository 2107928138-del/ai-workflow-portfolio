-- ============================================================
-- 品类缺货热力图数据
-- 用途：按一级 + 二级品类交叉分析缺货分布，支撑品类维度的运营决策
-- ============================================================

SELECT
    category_l1,
    category_l2,
    COUNT(DISTINCT sku_id) AS total_sku_cnt,
    COUNT(DISTINCT CASE WHEN risk_level != '✅ 正常' THEN sku_id END) AS risk_sku_cnt,
    ROUND(
        COUNT(DISTINCT CASE WHEN risk_level != '✅ 正常' THEN sku_id END) * 100.0
        / NULLIF(COUNT(DISTINCT sku_id), 0), 1
    ) AS risk_rate_pct,
    ROUND(AVG(stock_days), 1) AS avg_stock_days,
    ROUND(SUM(potential_gmv_loss), 0) AS total_gmv_loss_cny
FROM vw_sku_risk_daily
GROUP BY category_l1, category_l2
HAVING risk_sku_cnt > 0
ORDER BY risk_rate_pct DESC;
