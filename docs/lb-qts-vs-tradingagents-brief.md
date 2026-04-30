# lb-qts 与 TradingAgents 对比简报

生成时间：2026-04-28 22:37 CST

## 1. 一句话结论

`lb-qts` 和 `TradingAgents` **高度类似**，都属于 **LLM / Agent 驱动的金融投研与交易决策系统**。

但二者侧重点不同：

- **TradingAgents**：更像一个通用、代码化、产品化的多 Agent 金融交易框架。
- **lb-qts**：更像一个围绕个人交易方法论、LongPort 数据、飞书知识库和 Prompt 工作流构建的投研 Agent 工作台。

简化理解：

```text
TradingAgents = 通用多 Agent 金融框架
lb-qts        = 个人化 Prompt 驱动投研系统
```

---

## 2. 项目路径

### TradingAgents

```text
<TRADINGAGENTS_ROOT>
```

### lb-qts

```text
<PROJECT_ROOT>
```

---

## 3. 核心定位对比

| 维度 | TradingAgents | lb-qts |
|---|---|---|
| 系统定位 | 多 Agent LLM 金融交易框架 | 多 Agent 量化分析 / 投研 Agent 系统 |
| 技术形态 | Python package + LangGraph + CLI | Prompt 工程 + Python scripts + MCP + 文件产物 |
| 核心目标 | 模拟交易公司分工，生成投资决策 | 对标的做数据准备、推理、报告、飞书同步 |
| 数据源 | yfinance / Alpha Vantage | LongPort MCP / yfinance / 飞书知识库 |
| 输出结果 | Portfolio decision / rating / logs | deduction 推理、report 正式报告、飞书 Wiki 同步 |
| 决策等级 | Buy / Overweight / Hold / Underweight / Sell | 强力做多 / 推荐做多 / 看多 / 中性 / 看空 / 推荐做空 / 强力做空 |

---

## 4. 架构相似点

两者都采用类似的多 Agent 投研链路：

```text
数据输入
  -> 多维分析
  -> 推理/辩论
  -> 风控/交易计划
  -> 最终评级或报告
```

### TradingAgents 流程

```text
Market / Social / News / Fundamentals Analysts
  -> Bull / Bear Researchers
  -> Research Manager
  -> Trader
  -> Risk Analysts
  -> Portfolio Manager
  -> Final Decision
```

### lb-qts 流程

```text
阶段一：数据准备
  -> Data Agent
  -> Fundamental Agent
  -> 技术指标计算
  -> LLM context 生成
  -> 数据门禁

阶段二：推理分析
  -> Reasoning Agent
  -> 多维加权分析
  -> 六/七步交易决策链

阶段三：报告同步
  -> Execution Agent
  -> 正式报告
  -> 飞书 Wiki 同步

旁路：
  -> Review Agent
  -> YouTube Insight Agent
  -> learned_rules / challenges 自我进化
```

---

## 5. lb-qts 的特点

### 5.1 Prompt 工程更重

lb-qts 的核心在：

```text
AGENTS.md
agents/main/*.md
agents/workers/*.md
agents/policies/*.md
agents/learned_rules.md
```

本地看到的 Agent/Policy Markdown 约 17 个，说明它主要通过 Prompt 和运行约束组织 Agent 行为。

### 5.2 方法论更个性化

`agents/policies/trading_playbook.md` 是核心交易方法论，包含：

- 市场体制识别
- 多周期 Top-Down 框架
- 价格结构分析
- 趋势、动量、波动率、量能、资金流、支撑阻力
- 交易机会分类
- 风险优先七步法
- 仓位、止损、RR 约束
- 常见思维陷阱

这部分比 TradingAgents 更贴近个人交易体系。

### 5.3 数据和产物更贴近实际工作流

lb-qts 使用：

```text
LongPort MCP
Yahoo Finance
data/<symbol>/
deduction/<symbol>/
report/<symbol>/
飞书 Wiki
YouTube 知识库
```

本地已有不少产物：

- `data` 下约 43 个标的目录
- `report` 下约 41 个标的目录
- `deduction` 下约 47 个标的目录

说明它不是空架子，已经实际跑过多批标的。

---

## 6. TradingAgents 的特点

### 6.1 工程产品化更完整

TradingAgents 有：

- `pyproject.toml`
- CLI 入口
- tests
- Docker
- LangGraph checkpoint
- 多 LLM provider client
- structured output schema
- memory log
- package script entrypoint

它更像一个可安装、可复用、可分发的开源产品。

### 6.2 编排更确定

TradingAgents 使用 LangGraph，把 Agent 节点和边写进代码：

```text
node -> edge -> condition -> next node
```

lb-qts 主要靠 Prompt 约束 Agent 执行：

```text
必须读哪些文件
必须运行哪些脚本
必须写哪些产物
必须遵守哪些门禁
```

所以 TradingAgents 的执行确定性更强，lb-qts 的灵活性更强。

---

## 7. 最大区别

### TradingAgents 更像“产品”

```text
通用型
代码化
LangGraph 编排
CLI 可运行
Provider 抽象完善
```

### lb-qts 更像“工作台”

```text
个人化
Prompt 驱动
方法论沉淀
数据/报告/飞书联动
适合持续迭代交易规则
```

---

## 8. 融合建议

不建议直接用 TradingAgents 替换 lb-qts。

更合理的是：

```text
保留 lb-qts 的：
- trading_playbook
- learned_rules
- LongPort MCP 数据链路
- 飞书同步
- YouTube insight 学习机制
- 中文报告体系

借鉴 TradingAgents 的：
- LangGraph 编排
- structured output
- checkpoint resume
- CLI / Web UI
- 多 LLM provider abstraction
- memory log / reflection 机制
```

目标是把 lb-qts 从当前的 Prompt 工作区，升级成更稳定的个人投研 Agent 平台。

---

## 9. 最终判断

`lb-qts` 和 `TradingAgents` **确实是同类项目**。

但是：

```text
TradingAgents = 通用型、产品化、多 Agent 金融交易框架
lb-qts        = 个人化、Prompt 化、方法论驱动的多 Agent 投研系统
```

如果后续继续建设，lb-qts 最值得保留的是交易方法论和个人知识沉淀；最值得补强的是代码化编排、结构化输出和可恢复执行。