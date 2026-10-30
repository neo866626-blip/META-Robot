# AlanDerp ASPIRE 相对原版的改进

AlanDerp 分支主要改进的是技能知识的组织、检索、审核和维护。它保留 ASPIRE 的执行与修复框架，在其上增加技能代码证据、标准技能、高层原则、能力树和跨树关系。目标是缓解技能库长期增长后的重复、冲突、失效和上下文成本问题；实际收益仍需对照实验验证。

## 比较范围

移植来源固定为 [AlanDerp 提交 0a36d7a](https://github.com/AlanDerp/ASPIRE/commit/0a36d7a02abad08943f2124146d783fb253677b7)。知识库扩展以前置提交 `680bad4df1dabe2463e20069e16f6978630fe1d7` 为基线，之后有 27 个提交，涉及 94 个文件。这是两个固定提交间的差异，不是与 NVIDIA 最新版本的差异数量。

[NVIDIA 项目主页](https://research.nvidia.com/labs/gear/aspire/)介绍的 ASPIRE 通过执行反馈修复机器人程序，保存经验证的可复用技能，并用进化搜索改进程序。主页也将技能长期管理不完整列为局限：技能可能过时、过于具体、重复，或误导新任务。AlanDerp 的扩展主要针对这一问题。

本次核对的 NVIDIA main 为 [fa00f0e](https://github.com/NVlabs/ASPIRE/commit/fa00f0ef2bc1d91d594b9aa502c22133c9f538f7)，已发布 v1.0。AlanDerp 与它的演进路径不同，不能理解成包含官方最新功能的全面升级版，也不能把从早期共同祖先开始的所有差异都归为 AlanDerp 的原创。

## 具体改进

| 方面 | 原版机制与问题 | AlanDerp 新增机制 | 价值与边界 |
| --- | --- | --- | --- |
| 技能来源 | 保存修复经验与技能，长期证据治理仍有限 | SkillCodeInstance 记录执行代码、来源哈希、AST/API 指纹和数据分区 | 可以追溯经验来源；单条总结不能直接成为已验证原则 |
| 重复整合 | 技能库随任务扩张 | 冻结检查点后审计重复，经显式审查整合标准技能 | 为去重提供复核流程；阈值只提名候选 |
| 高层抽象 | 已有可复用技能与上下文指导 | 从多个标准技能归纳原则，记录条件、可观察效果、例外、应对动作和可证伪条件 | 尝试将局部经验压缩成决策规则，仍保留代码证据 |
| 知识结构 | 原有技能库与工作流继续保留 | 纵向能力树加跨树依赖、顺序、冲突和例外关系 | 表达技能间结构；图结构本身也增加维护开销 |
| 检索 | 原版上下文与技能检索保留 | 先选原则，再有限下钻技能，检查范围、API、例外、证据和预算 | 希望减少无关上下文，实际收益待验证 |
| 激活审核 | 原版技能保存流程保留 | 原则、树与关系须经提议、审查、提升，并绑定精确版本和证据 | 直接写状态不能替代正规激活路径 |
| 失效维护 | 长期记忆失效和误导问题尚未完全解决 | 追加式失效事件、影响范围与支持强度传播，以及重复、冲突、过度连接节点审计 | 帮助定位受影响知识；维护成本优势待测量 |
| 运行接入 | 继续使用原执行、修复与评估框架 | off、shadow、正式注入模式，记录知识组合哈希及运行遥测 | 支持分阶段接入；当前证据只支持默认 off |
| 实验审计 | 原版有自身机器人评测 | A–F 对照、预注册冻结、真实与合成语料分离、固定预算种子、成本账本和结论审计 | 用来检验抽象机制，框架完成不代表实验完成 |

主要实现为 [cap/knowledge](../aspire/sim/cap/knowledge/)，策略和权威数据位于 [knowledge](../aspire/sim/knowledge/)。SQLite 索引与 Markdown 展示是可重建视图，YAML/JSONL 和 Git 历史保留来源证据。

## 谓词新增与修改的代码证据

**有明确新增，也有后续收紧。** 相对 `680bad4` 基线，分支新增了 84 行的 `aspire/sim/cap/knowledge/predicates.py`。它是知识层的结构化条件求值器，用于判断原则是否适用、例外是否命中、跨树关系是否启用；不能据此声称新增了视觉谓词识别模型或完整的符号规划器。

### 提交证据

- [7fe24fb Implement upward-abstraction knowledge forest](https://github.com/AlanDerp/ASPIRE/commit/7fe24fbfa3bd7ff94248624011d6dbc68837ceb7)：首次新增 `predicates.py`；本地 `git diff 680bad4 0a36d7a -- aspire/sim/cap/knowledge/predicates.py` 显示 `new file mode 100644`。该文件在固定版本前没有后续修改，但调用与审核约束继续演进。
- [632eb0a Require explicit exception guards](https://github.com/AlanDerp/ASPIRE/commit/632eb0a366f97310b9308a83b16a8f6103942163)：修改 `models.py`、`review.py`、`overlay_review.py` 和测试，要求原则例外的 `when` 是非空字典，并拒绝缺少显式 `guard` 的 `exception-to` 关系提议。这是谓词使用约束的加强。

### 实现与调用证据

以下链接固定到本次移植的上游提交，避免行号随 main 变化：

| 证据位置 | 具体行为 |
| --- | --- |
| [predicates.py 第 16–25 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/predicates.py#L16-L25) | 读取事实，支持直接键名和 `state.object_grasped` 这样的嵌套路径 |
| [predicates.py 第 27–48 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/predicates.py#L27-L48) | 使用 True / False / None 三值逻辑，支持 all、any、not；None 表示事实不足，空条件返回 True |
| [predicates.py 第 52–84 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/predicates.py#L52-L84) | 支持 exists、eq、ne、in、contains、gt、gte、lt、lte、regex；正则表达式长度上限为 256 |
| [retrieval.py 第 212–225 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/retrieval.py#L212-L225) | 原则 when 必须严格为 True；False 或未知都会排除。例外 when 为 True 时，排除该原则 |
| [retrieval.py 第 459–470 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/retrieval.py#L459-L470) | 跨树边 guard 必须严格为 True 才处理；命中的 exception-to 会屏蔽目标及其下属分支 |
| [models.py 第 360–371 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/models.py#L360-L371) | 经审查的原则例外必须包含 id、非空字典 when、非空文本 response |
| [overlay_review.py 第 32–39 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/cap/knowledge/overlay_review.py#L32-L39) | exception-to 关系在提议阶段就必须具有显式 guard |

例如，上游测试使用这个谓词：

```json
{"fact": "state.object_grasped", "op": "eq", "value": true}
```

当 `facts` 为 `{}` 时返回 None；当 `facts` 为 `{"state":{"object_grasped":true}}` 时返回 True。它评估调用方提供的事实，本身不从图像或机器人传感器推断“已抓住物体”。

### 测试证据与语义边界

2026-10-30 单独重新执行以下四个上游原有测试，全部通过：

| 测试与代码链接 | 证明内容 |
| --- | --- |
| [test_predicate_unknown_is_not_true，第 248 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/tests/test_knowledge.py#L248-L251) | 缺失事实返回未知；嵌套事实满足条件时为真 |
| [test_overlay_exception_proposal_requires_an_explicit_guard，第 1645 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/tests/test_knowledge.py#L1645-L1659) | 无 guard 的例外边提议被拒绝 |
| [test_guarded_overlay_exception_blocks_target_branch，第 1734 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/tests/test_knowledge.py#L1734-L1772) | 命中的跨树例外阻断原则分支，保留替代技能及审查指导 |
| [test_exception_blocks_principle_and_uses_canonical_fallback，第 1916 行](https://github.com/AlanDerp/ASPIRE/blob/0a36d7a02abad08943f2124146d783fb253677b7/aspire/sim/tests/test_knowledge.py#L1916-L1942) | 命中的原则例外触发标准技能回退，指导文本进入 Portfolio |

不能把三值逻辑概括为“所有未知都阻断”：原则适用条件未知会拒绝原则；跨树 guard 未知会跳过该边；原则例外未知不会触发例外。空谓词在求值器中返回 True，因此显式例外约束有实际作用。此外，`response` 被验证为非空字符串并进入知识指导，并非在这一层自动编译执行的动作程序。

基线中本来就存在名为 `target_pose_predicate` 的机器人目标位姿回调，故不应说原版完全没有谓词概念。这里有证据支持的新增是上述知识层谓词语言及其检索、例外审核接入；四项测试也不构成真实机器人效果提升的证据。

## 工作流程

整合方向是：实际执行代码 → 冻结检查点 → 重复审计与审查 → 标准技能 → 原则提议与证据审查 → 能力树及跨树关系的审查与激活。

运行时从任务出发，选择相关能力树和原则，检查例外与冲突，下钻少量可执行技能，再编译为执行智能体可见的知识组合（Portfolio）。证据失效、预算不满足或无适用知识时，拒绝相关内容或记录回退原因。

例如，多项任务的抓取代码可能共同支持一条抓取原则。新任务先检查原则适用条件，再选择实现；命中经审核的例外时，系统将例外及应对动作传给执行智能体。这是机制示意，不是已经完成的机器人实验结果。

## A 到 F 对照

| 组别 | 知识形式 | 要检验的因素 |
| --- | --- | --- |
| A | 平铺技能代码 | 代码级参照 |
| B | 标准技能 | 去重与标准化 |
| C | 摘要树 | 普通总结压缩 |
| D | 原则树 | 原则是否比普通摘要更有效 |
| E | 能力森林与跨树关系 | 跨能力关系的增益 |
| F | 去掉例外的原则树 | 例外约束是否减少负迁移 |

这些是分支内部的对照设计，A 组不能直接等同于 NVIDIA 官方全部评测流程。框架要求同等上下文和预算约束，并区分真实执行语料与合成压力语料。

## 已实现与未验证的界限

本次移植后，五个知识库测试模块的 79 项测试全部通过，覆盖整合、命令行端到端流程、预注册、运行时知识接入和技能提升记录。这说明工程路径能在受控测试中工作。

分支自己的[实现状态](../aspire/sim/docs/knowledge-blueprint-status.md)和[完成度审计](../aspire/sim/docs/knowledge-completion-audit.md)列出了缺少的证据：真实开发语料、正式冻结的实验输入、双人独立标注的原则样本、20 个任务的检索比较、固定预算的 LIBERO A–F 留出实验，以及真实维护成本记录。本次重新运行完成度审计也得到 incomplete，最高可用模式为 off。

因此，可以说该分支增加了可追溯的知识抽象与治理能力；不能说它已证明比原版成功率更高、token 更少、运行更快或维护更便宜。NVIDIA 官网展示的原版成绩也不能作为新增机制的收益证明。

## 本次迁移的新增内容

META-Robot 保留 AlanDerp 的源码、历史、七个子模块固定引用和原许可，增加中文入口、此对比说明与移植记录。初始移植没有修改机器人算法，也没有合并 NVIDIA v1.0 的后续功能。后续 META-Robot 开发新增了 `meta_robot/action_predicates/`，实现论文中的动作级谓词持久库、技能关联与执行前后状态追踪；相关代码区别于本页分析的 AlanDerp 原始版本，详见 [META-Robot 方法与代码对应](../docs/paper-to-code.md)。

后续若要验证价值，应按照[实验指南](../aspire/sim/docs/knowledge-experiment-runbook.md)采集真实开发证据、完成审查和版本冻结，再运行固定配置的对照实验。
