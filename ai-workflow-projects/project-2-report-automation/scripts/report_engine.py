"""
报告生成引擎 (report_engine.py)
===============================
日报/周报 AI 辅助自动生成系统的核心引擎。

AI 参与说明：
  - 本脚本约 80% 代码由 Codex 辅助生成，包括：
    · 指标计算函数 (calc_*) 
    · FBI API 图表截图调用
    · Jinja2 模板渲染
    · SMTP 邮件发送
  - 人工工作：定义指标体系、审核 AI 生成的分析文案、
    调整 Jinja2 模板样式。

调度方式：
  日报: 0 8 * * * /usr/bin/python3 report_engine.py --mode daily
  周报: 0 9 * * 1 /usr/bin/python3 report_engine.py --mode weekly
"""

import argparse
import json
import os
import smtplib
import sqlite3
import yaml
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(PROJECT_DIR, "templates")
CONFIG_PATH = os.path.join(PROJECT_DIR, "config", "config.yaml")

# 加载配置
with open(CONFIG_PATH) as f:
    config = yaml.safe_load(f)


# ============================================================
# 1. 数据采集层 (Codex 辅助实现 SQL 和 API 调用)
# ============================================================

def fetch_kpi_data(mode: str) -> dict:
    """
    从数据源获取指标原始数据。
    生产环境: ODPS SQL + FBI API
    以下为模拟数据。
    """
    today = datetime.now().strftime("%Y-%m-%d")

    if mode == "daily":
        return {
            "report_date": today,
            "period_label": datetime.now().strftime("%m月%d日"),
            # 核心指标
            "total_gmv": 1285000,
            "total_orders": 3240,
            "avg_order_value": 39.7,
            # 缺货率
            "out_of_stock_rate": 3.2,
            "out_of_stock_rate_wow": -0.5,  # 环比变化 (百分点)
            "high_risk_sku_count": 8,
            "mid_risk_sku_count": 12,
            "high_risk_sku_wow": -2,  # 环比减少2个
            # 履约
            "on_time_delivery_rate": 94.5,
            "on_time_delivery_rate_wow": 1.2,
            "avg_delivery_days": 5.8,
            "avg_delivery_days_wow": -0.3,
            # 异常商家
            "abnormal_merchant_count": 5,
            "abnormal_merchant_wow": -1,
            "total_merchants": 120,
            # 改善进展
            "improved_sku_count": 15,
            "improved_merchant_count": 3,
            # TOP 问题
            "top_risk_merchants": [
                {"name": "绅士男装馆", "risk_skus": 3, "main_issue": "库存不足"},
                {"name": "潮流服饰旗舰店", "risk_skus": 2, "main_issue": "发货延迟"},
                {"name": "萌宠乐园", "risk_skus": 2, "main_issue": "库存不足"},
            ],
            # 图表截图 (FBI API 返回的图片 URL/Base64)
            "chart_images": {
                "trend": "/charts/trend_20251215.png",
                "merchant_ranking": "/charts/merchant_ranking_20251215.png",
            },
        }

    elif mode == "weekly":
        return {
            "report_date": today,
            "week_label": "第50周 (12.09-12.15)",
            "start_date": "2025-12-09",
            "end_date": "2025-12-15",
            # 核心指标 (周度)
            "total_gmv": 8950000,
            "total_gmv_wow": 3.5,
            "total_orders": 22680,
            "total_orders_wow": 2.8,
            "avg_order_value": 39.5,
            "avg_order_value_wow": 0.7,
            # 缺货率
            "out_of_stock_rate_avg": 3.0,
            "out_of_stock_rate_wow": -0.8,
            "out_of_stock_trend": [3.8, 3.5, 3.2, 3.1, 2.9, 2.8, 3.0],
            # 履约
            "on_time_delivery_rate": 94.8,
            "on_time_delivery_rate_wow": 0.5,
            # 商家治理
            "total_contacted_merchants": 18,
            "improved_merchants": 12,
            "improvement_rate": 66.7,
            # TOP 改善/问题
            "best_improved": [
                {"name": "潮流服饰旗舰店", "before": 8, "after": 2, "action": "紧急补货 200件"},
                {"name": "数码先锋店", "before": 5, "after": 0, "action": "调整安全库存阈值"},
            ],
            "worst_merchants": [
                {"name": "绅士男装馆", "risk_days": 5, "reason": "供应商产能不足"},
            ],
        }


# ============================================================
# 2. AI 分析洞察生成 (Codex 辅助设计 Prompt 模板)
# ============================================================

def generate_ai_insights(data: dict, mode: str) -> dict:
    """
    将指标数据输入 Prompt，AI 自动生成分析段落。
    
    实际实现:
      import openai
      response = openai.chat.completions.create(
          model="gpt-4",
          messages=[{"role": "system", "content": PROMPT_SYSTEM},
                    {"role": "user", "content": f"以下是今日供应链数据:\n{json.dumps(data)}"}]
      )
      return parse_insights(response.choices[0].message.content)
    
    以下为模拟 AI 生成的洞察（模拟真实 AI 输出风格）。
    """
    if mode == "daily":
        return {
            "headline": "缺货率持续改善，高风险SKU降至8个",
            "key_findings": [
                {
                    "title": "缺货治理效果持续显现",
                    "body": "今日缺货率 3.2%，环比下降 0.5 个百分点。高风险 SKU 从上周的 10 个降至 8 个，"
                           "其中「潮流服饰旗舰店」通过紧急补货已将 3 个高风险 SKU 降为中风险。"
                           "但「绅士男装馆」的 POLO 衫系列仍处于高风险状态，建议继续跟进。",
                },
                {
                    "title": "履约时效小幅提升",
                    "body": "今日准时发货率 94.5%，环比提升 1.2 个百分点。平均发货时长 5.8 天，"
                           "环比缩短 0.3 天。履约改善主要来自上周定向沟通的 3 家问题商家。",
                },
                {
                    "title": "需关注：宠物用品品类库存压力增大",
                    "body": "猫砂、猫粮两大 SKU 库存持续走低，日均销量高于补货速度。"
                           "建议提前与「萌宠乐园」沟通双十二备货计划，避免大促期间断货。",
                },
            ],
            "next_focus": [
                "跟进「绅士男装馆」POLO 衫补货进度",
                "与宠物品类 TOP 商家沟通大促备货",
                "验证「潮流服饰旗舰店」改善效果是否持续",
            ],
        }
    else:
        return {
            "headline": "本周缺货率降至 3.0%，18 家问题商家完成沟通，改善率 66.7%",
            "week_summary": (
                "本周供应链运营整体向好。缺货率从周初的 3.8% 降至周末的 3.0%，"
                "降幅 0.8 个百分点。共完成 18 家商家定向沟通，其中 12 家已见改善，改善率 66.7%。"
                "GMV 环比增长 3.5%，履约时效稳定在 94.8%。"
            ),
            "category_analysis": {
                "女装": "缺货率从 4.2% 降至 2.8%，已恢复正常水平",
                "男装": "缺货率 5.1%，仍高于平台均值，需持续关注",
                "3C数码": "库存充足，缺货率仅 1.2%",
                "宠物用品": "缺货率 4.5%，呈上升趋势，建议重点关注",
            },
            "recommendations": [
                "男装品类建议启动专项治理，考虑引入备选供应商机制",
                "宠物用品大促前需完成至少 2 周安全库存储备",
                "建议将「改善率」纳入商家考核体系，激励商家主动优化库存管理",
            ],
        }


# ============================================================
# 3. Jinja2 模板渲染 (Codex 辅助编写 HTML/CSS)
# ============================================================
def render_report(data: dict, insights: dict, mode: str) -> str:
    """使用 Jinja2 渲染 HTML 报告"""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template_name = "daily_report.html" if mode == "daily" else "weekly_report.html"
    template = env.get_template(template_name)

    return template.render(
        data=data,
        insights=insights,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ============================================================
# 4. 邮件推送 (Codex 辅助实现 SMTP + 附件)
# ============================================================
def send_email(html_content: str, mode: str, pdf_path: Optional[str] = None):
    """通过 SMTP 发送 HTML 报告邮件"""
    smtp_config = config["email"]

    msg = MIMEMultipart("alternative")
    subject = f"【速卖通供应链】{'日报' if mode == 'daily' else '周报'} - {datetime.now().strftime('%Y%m%d')}"
    msg["Subject"] = subject
    msg["From"] = smtp_config["from"]
    msg["To"] = ", ".join(smtp_config["to"])

    # HTML 正文（邮件客户端内嵌显示）
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # PDF 附件（可选）
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="report_{datetime.now().strftime("%Y%m%d")}.pdf"',
            )
            msg.attach(part)

    try:
        with smtplib.SMTP_SSL(smtp_config["host"], smtp_config["port"]) as server:
            server.login(smtp_config["username"], smtp_config["password"])
            server.sendmail(msg["From"], smtp_config["to"], msg.as_string())
        logger.info("邮件发送成功: %s", subject)
    except Exception as e:
        logger.error("邮件发送失败: %s", e)


# ============================================================
# 主流程
# ============================================================
def run(mode: str = "daily"):
    logger.info("========== 开始生成%s ==========", "日报" if mode == "daily" else "周报")

    # Step 1: 取数
    data = fetch_kpi_data(mode)
    logger.info("数据采集完成，共 %d 项指标", len(data))

    # Step 2: AI 分析
    insights = generate_ai_insights(data, mode)
    logger.info("AI 分析洞察生成完成: %s", insights["headline"])

    # Step 3: 模板渲染
    html = render_report(data, insights, mode)
    logger.info("HTML 报告渲染完成 (%d 字符)", len(html))

    # Step 4: 保存 + 推送
    output_dir = os.path.join(PROJECT_DIR, "samples")
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{'daily' if mode == 'daily' else 'weekly'}_report_{datetime.now().strftime('%Y%m%d')}.html"
    output_path = os.path.join(output_dir, filename)
    with open(output_path, "w") as f:
        f.write(html)
    logger.info("报告已保存: %s", output_path)

    # Step 5: 邮件推送
    send_email(html, mode)

    logger.info("========== %s生成完成 ==========", "日报" if mode == "daily" else "周报")
    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    args = parser.parse_args()
    run(args.mode)
