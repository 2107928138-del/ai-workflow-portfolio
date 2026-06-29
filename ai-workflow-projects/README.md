# AI 自动化工作流项目集

> 吴天琦 | 速卖通供应链运营 | 2025

## 项目概览

本项目集包含在阿里巴巴速卖通供应链运营岗位期间搭建的三个 AI 自动化工作流系统，
展示了从「问题发现 → 数据采集 → AI 辅助开发 → 自动化执行 → 结果推送」的完整能力。

| 项目 | 核心能力 | 技术栈 |
|------|---------|--------|
| 项目一：SKU 缺货率智能监控 | 数据采集 + 异常检测 + 自动预警 | SQL, Python, Pandas, Codex, FBI, Crontab |
| 项目二：日报/周报 AI 自动生成 | 指标计算 + AI 分析 + 模板渲染 + 自动推送 | Python, Jinja2, Codex, SMTP, Cron |
| 项目三：商家库存编辑审批自动化 | 低代码审批流 + API 集成 + 分级路由 | 宜搭, Codex, REST API, 钉钉/企微 |

## 目录结构

```
ai-workflow-projects/
├── README.md                         # 本文件
├── project-1-sku-monitor/            # 项目一：SKU 缺货率智能监控
│   ├── README.md                     #   项目说明
│   ├── sql/                          #   SQL 查询模板库
│   ├── scripts/                      #   Python 自动化脚本
│   ├── dashboard/                    #   FBI 看板配置
│   └── samples/                      #   预警消息样例
├── project-2-report-automation/      # 项目二：日报/周报 AI 自动生成
│   ├── README.md                     #   项目说明
│   ├── scripts/                      #   Python 报告引擎
│   ├── templates/                    #   Jinja2 报告模板
│   ├── config/                       #   配置文件
│   └── samples/                      #   生成的报告样例
└── project-3-approval-flow/          # 项目三：商家库存编辑审批自动化
    ├── README.md                     #   项目说明
    ├── yida/                         #   宜搭表单 & 审批流配置
    ├── scripts/                      #   API 回写脚本
    └── samples/                      #   通知模板样例
```

## 面试使用指南

1. **展示架构**：每个项目的 `README.md` 包含工作流架构图和 AI 参与环节说明
2. **展示代码**：打开 `scripts/` 下的 Python 文件，展示实际代码质量
3. **展示 SQL**：打开 `sql/` 下的 SQL 文件，展示多表关联与窗口函数能力
4. **展示模板**：打开 `project-2/templates/` 下的 HTML 报告模板
5. **展示产出**：打开 `project-2/samples/` 下的报告样例
