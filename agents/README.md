# Agents Layout (Harness-style)

## 目录分层

- `agents/main/`：主 Agent（入口层，按功能域分流）
- `agents/workers/`：执行 Agent（具体任务实现）
- `agents/policies/`：统一约束与产出规范
- `agents/profiles/`：投资经理风格与标的 mandate（Phase 3 引入）

## 主 Agent

- `main/router.md`：主路由规则
- `main/market_main_agent.md`：标的分析主链路
- `main/review_main_agent.md`：复盘强化主链路
- `main/youtube_main_agent.md`：YouTube 知识强化主链路

## Workers

- `workers/data_agent.md`
- `workers/fundamental_master_agent.md`
- `workers/strategy_agent.md`
- `workers/reasoning_agent.md`
- `workers/execution_agent.md`
- `workers/review_agent.md`
- `workers/youtube_insight_agent.md`

## Policies

- `policies/common_rules.md` — 通用约束（入口、文件系统、MCP、报告质量）
- `policies/runtime_contract.md` — 运行协议（状态、回传、失败处理）
- `policies/trading_playbook.md` — **交易方法论核心**：市场体制识别、多周期框架、七大分析维度、交易机会分类、风险优先七步法、基本面×技术面整合、常见思维陷阱
- `policies/report_specs.md` — 报告结构与质量标准（信息密度优先）

## Profiles

- `profiles/*.md` — 标的类型与投资经理风格：关注点、证据优先级、权重偏置、hard concerns、适合机会和常见误判
- profile 不承载通用方法论、输出格式、run manifest、全局硬规则或报告模板
- profile 文件由 Phase 3 引入，未落地前不得让现有 worker 默默依赖不存在的 profile
- `scripts/resolve_profile.py` 将 `data/<symbol>/symbol_profile.json` 解析为 `data/<symbol>/profile_resolution.json`
- `scripts/validate_profiles.py` 校验 profile 模板、标准标的映射和 profile 文件引用
- `scripts/validate_phase3_profile_effect.py` 校验真实 worker result 中 profile 权重差异是否落地

## 规则与方法论位阶（冲突时由高到低）

1. `learned_rules.md` — 实战沉淀的强制规则（例外条款）
2. `policies/trading_playbook.md` — 通用交易方法论
3. `policies/report_specs.md` — 报告格式
4. `profiles/*.md` — 风格和权重偏置
5. 各 worker 自身描述

新维护统一在 `main/`、`workers/`、`policies/`、`profiles/` 进行。
