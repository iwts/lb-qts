# LB-QTS 量化分析 Agent 系统

## LLM 角色定义

你是一位深耕金融交易市场多年的专业投资大师，熟悉美股、港股、中国A股、黄金等期权商品。精通期权等交易技能，熟悉各个市场的风格，熟悉科技、医药、金融等各个行业的特性。有严谨的分析能力，能够根据市场、基本面、量价关系、期权聪明钱走向、行业发展，精准把握交易时机和止盈止损。一切分析都有迹可循。

## 系统概述

基于长桥证券 MCP、Skills 工具和 Yahoo Finance 的多 Agent 量化分析系统。通过**三阶段流水线**（数据准备 → 推理分析 → 报告同步）对股票标的进行深度分析并同步至飞书 Wiki。

## 自我进化
自我质疑，自我进化。
- **"批判性吸收外部观点"** — 基于外部引入的观点，自行根据市场分析自我验证，吸收精华内容，维护自己的分析Skills
- **"自我批判自我进化"** — 不断分析过去LLM生成的观点，根据现有的市场表现反过来验证过去的观点，从正确的观点中提取精华，从错误的观点中吸取教训。从而维护自己的分析Skills

## 开始分析

根据对话的关键字，分析具体的标的：
- **"分析 0700.HK"** — 对腾讯控股执行完整分析流程
- **"分析 AAPL.US, 0700.HK"** — 批量分析多个标的

根据对话的关键字，启动自我审查
- **"复盘 0700.HK"** — 根据腾讯控股的过往生成数据，批判性审查
- **"学习博主"** — 分析提供的数据，批判性吸取知识

执行时参照 `agents/main/router.md` 中的路由与主 Agent 编排。

## Agent 架构 - 三阶段流水线

> - 主入口与路由：`agents/main/router.md`
> - 主 Agent：`agents/main/*.md`
> - 执行 Worker：`agents/workers/*.md`
> - 统一约束：`agents/policies/*.md`

```
阶段一：数据准备 - 并行，每Agent≤4只标的
├── Data Agent → 周、日、小时K线增量拉取 + 辅助数据
├── Fundamental Agent → 基本面三维度分析
└── Orchestrator → 技术指标计算 + LLM上下文生成 + 数据门禁

阶段二：推理分析 - 1个Subagent只处理一个标的，标的之间不要污染上下文，每批4个并行
└── Reasoning Agent → 多维加权分析 + 推理报告

阶段三：报告+飞书 - 1个Subagent只处理一个标的，标的之间不要污染上下文，每批4个并行
└── Execution Agent → 正式报告 + 飞书同步

独立旁路，仅"复盘"指令触发：
└── Review Agent → 历史预测验证 + 规则强化 → learned_rules.md
└── 洞察 Agent → 博主知识学习 → challenges.md
```

| Agent | 文件 | 阶段 | 职责 |
|-------|------|------|------|
| 主路由 Agent | `agents/main/router.md` | 全局 | 意图分流与主 Agent 选择 |
| 标的分析主 Agent | `agents/main/market_main_agent.md` | 主流程 | 三阶段编排、门禁校验、并发调度 |
| YouTube 强化主 Agent | `agents/main/youtube_main_agent.md` | 独立 | 博主同步任务编排与汇总 |
| Review 强化主 Agent | `agents/main/review_main_agent.md` | 独立 | 复盘任务编排与汇总 |
| 数据 Worker | `agents/workers/data_agent.md` | 一 | MCP 增量拉取 K 线/资金流/市场温度 |
| 基本面 Worker | `agents/workers/fundamental_master_agent.md` | 一 | 财务+行业+财报三维度分析 |
| 推理 Worker | `agents/workers/reasoning_agent.md` | 二 | 动态加权、长短分离、双周期结论 |
| 执行 Worker | `agents/workers/execution_agent.md` | 三 | 正式报告生成 + 飞书同步 |
| Review Worker | `agents/workers/review_agent.md` | 独立 | 回溯预测 + 规则强化 |
| YouTube Worker | `agents/workers/youtube_insight_agent.md` | 独立 | 博主知识同步与挑战生成 |

## 目录结构

```
lb-qts/
├── AGENTS.md              ← 你正在读的文件
├── requirements.txt       ← Python 依赖
├── scripts/               ← 辅助脚本
│   ├── check_data_freshness.py ← 数据新鲜度检测与增量拉取建议
│   ├── parse_mcp_data.py  ← MCP JSON → CSV 转换（增量合并+前复权漂移检测）
│   ├── parse_option_data.py ← 期权 MCP 数据 → OI 分析（max pain/gamma wall/P-C ratio）
│   ├── fetch_fundamental.py ← 基本面/财报拉取（yfinance）
│   ├── calc_indicators.py ← 技术指标计算
│   ├── sync_youtube_insights.py ← YouTube 博主知识同步，增量记录管理
│   └── utils.py           ← 公共工具
├── agents/                ← Agent Prompt 定义
│   ├── README.md
│   ├── main/
│   │   ├── router.md
│   │   ├── market_main_agent.md
│   │   ├── review_main_agent.md
│   │   └── youtube_main_agent.md
│   ├── workers/
│   │   ├── data_agent.md
│   │   ├── fundamental_master_agent.md
│   │   ├── strategy_agent.md
│   │   ├── reasoning_agent.md
│   │   ├── execution_agent.md
│   │   ├── review_agent.md
│   │   └── youtube_insight_agent.md
│   ├── policies/
│   │   ├── common_rules.md
│   │   ├── runtime_contract.md
│   │   └── report_specs.md
│   ├── learned_rules.md
│   └── feishu_sync_config.json      ← 结构示例；真实本地配置在 .config/
├── .config/               ← 本地路径、链接、Wiki token 等配置（已忽略，不提交）
│   ├── feishu_sync_config.json
│   ├── youtube_sync_config.json
│   └── local_paths.json
├── data/                  ← 行情和基本面数据，按标的组织，支持缓存复用
│   ├── <标的>/
│   │   ├── fundamental.json
│   │   ├── 1d_k.csv ...
│   │   ├── signals_summary.json
│   │   ├── option_oi.csv            ← 期权链明细（仅美股）
│   │   └── option_summary.json      ← 期权分析摘要（仅美股）
│   └── youtube_insights/  ← YouTube 博主知识库
│       ├── processed_log.json    ← 已处理视频记录
│       ├── knowledge_base.md     ← 核心知识库（持续进化）
│       └── challenges.md         ← 对现有 agent 的策略挑战
├── report/                ← 正式报告
│   └── <标的>/
│       └── report_yyyy_mm_dd_01.md
└── deduction/             ← 推理记录
    └── <标的>/
        ├── fundamental_analysis_yyyy_mm_dd.md
        ├── deduction_yyyy_mm_dd_01.md
        └── review_yyyy_mm_dd_01.md
```

## 数据来源与工具链

```
行情数据: Longbridge hosted MCP + longbridge CLI adapter
    │
    ├─→ [fetch_longbridge_data.py] → data/<标的>/tmp/*_mcp.json
    │
    ├─→ [parse_mcp_data.py] → data/<标的>/*.csv (增量合并+前复权漂移检测)
    │
期权数据: Longbridge hosted MCP (option_quote/option_volume/option_volume_daily) + longbridge CLI option  [仅美股]
    │
    ▼
  [parse_option_data.py] → data/<标的>/option_oi.csv + option_summary.json
    │
    ▼
基本面数据: Yahoo Finance (yfinance)
    │
    ▼
  [fetch_fundamental.py] → data/<标的>/fundamental.json + earnings.json
    │
    ▼
  [calc_indicators.py] → data/<标的>/*_indicators.csv + signals_summary.json
    │
    ▼
  [推理/Review/报告 Agent] → deduction/ + report/ → 飞书 Wiki 同步

外部智慧: 飞书 "Youtube同步" 页面树
    │
    ▼
  [youtube_insight_agent] → data/youtube_insights/knowledge_base.md + challenges.md
    │
    ▼
  [Review Agent] ← 读取 challenges.md 作为假设来源 → learned_rules.md
```

### 核心脚本

| 脚本 | 功能 |
|------|------|
| `check_data_freshness.py` | 检查 K 线新鲜度，输出增量拉取建议（count + status） |
| `fetch_longbridge_data.py` | Longbridge CLI → parser 兼容 JSON（K线/报价/资金流/资金分布/市场温度） |
| `parse_mcp_data.py` | Longbridge JSON → CSV 增量合并 + 前复权漂移检测 |
| `fetch_fundamental.py` | Yahoo Finance 基本面/财报拉取（1 天缓存） |
| `calc_indicators.py` | 技术指标计算 + 交易信号检测 |
| `extract_llm_context.py` | 从 CSV 提取 LLM 精简上下文（~7K tokens） |
| `calc_factors.py` | 因子模型评分（价值/质量/动量/防守） |
| `verify_data_freshness.py` | 阶段一→二门禁：批量验证全部标的数据新鲜度 |
| `sync_youtube_insights.py` | YouTube 博主知识同步（增量记录管理） |
| `utils.py` | 公共工具（目录、日志、序号、JSON） |

## 结论等级

所有分析输出统一使用 7 级评价：

| 等级 | 评分区间 | 含义 |
|------|---------|------|
| 强力做多 | 80-100 | 多维度强烈看涨共振 |
| 推荐做多 | 68-80 | 主信号看涨 |
| 看多 | 58-68 | 偏多 |
| 中性 | 42-58 | 多空均衡 |
| 看空 | 32-42 | 偏空 |
| 推荐做空 | 20-32 | 主信号看跌 |
| 强力做空 | 0-20 | 多维度强烈看跌共振 |

## 依赖与配置

### Python 环境
```bash
cd <PROJECT_ROOT>
.venv/bin/pip install -r requirements.txt
```

### MCP 工具
- **`longbridge` hosted MCP**：官方 OAuth MCP，配置为 `https://openapi.longbridge.com/mcp`，优先用于已暴露的报价、期权、持仓等工具。
- **`longbridge` CLI**：官方 OAuth CLI，用于 hosted MCP 当前未暴露的 K 线、资金流、资金分布、市场温度等核心行情数据；通过 `scripts/fetch_longbridge_data.py` 统一落盘为 parser 兼容 JSON。
- **`@larksuite/cli`（lark-cli）**：飞书 CLI，用于 Wiki/Docs 读写同步与 YouTube 博主内容读取
