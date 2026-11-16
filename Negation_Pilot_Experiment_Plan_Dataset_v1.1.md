# Negation Pilot 实验说明
## 基于 `sundowner-miles/negation-pilot` 的 Dataset v1.1

**文档用途：** 指导研究者使用当前已冻结的 Dataset v1.1 开展小规模模型 Pilot，并统一输入格式、实验分组、评价指标和结果报告口径。

**仓库：** <https://github.com/sundowner-miles/negation-pilot>  
**数据版本：** Dataset v1.1  
**配置文件：** `configs/pilot.yaml`  
**公开评测输入：** `data/generated/pilot.public.jsonl`  
**金标签文件：** `data/generated/pilot.gold.jsonl`

---

## 1. Pilot 目标与研究问题

本 Pilot 旨在考察大语言模型在有限论域形式逻辑推理中，是否能够正确理解否定，并区分逻辑蕴含、逻辑矛盾与信息不足。研究重点不是一般常识问答，也不是单纯识别句子中是否出现 “not”，而是判断模型能否在给定知识库和查询的条件下正确处理否定的逻辑作用。

建议围绕以下问题组织实验：

1. **三分类判断：** 模型能否区分 `TRUE`、`FALSE` 和 `UNKNOWN`？
2. **否定关键性：** 当否定参与推导（critical）或仅为旁路信息（distractor）时，模型的判断表现是否不同？
3. **否定位置与辖域：** 否定出现在事实、规则或查询中，以及作用于不同逻辑结构时，是否产生不同错误模式？
4. **推理深度：** 随着典范证明深度从 1 增加到 3、5，模型表现是否下降？
5. **等价形式：** 对逻辑等价但表面形式不同的表达，模型能否保持判断一致？
6. **否定消融：** 删除被研究的那个否定后，模型预测是否按逻辑变化方向发生变化？

本数据集只能支持对其覆盖的有限论域、经典逻辑和符号化句式进行结论，不应直接推广为模型对所有自然语言否定现象的总体能力。

## 2. 数据集与逻辑语义

### 2.1 数据规模

| 项目 | 数量 | 统计单位 |
|---|---:|---|
| 总样本 | 1,200 | samples |
| 基础案例 | 600 | base cases |
| 对照组 | 600 | pairs |
| 确定性对照 | 400 | pairs |
| UNKNOWN 对照 | 200 | pairs |
| TRUE / FALSE / UNKNOWN | 400 / 400 / 400 | samples |
| 严格受控对照 | 290 | pairs |
| 探索性对照 | 310 | pairs |

每个 pair 包含两条样本。400 个确定性 pair 各包含一条 TRUE 和一条 FALSE；200 个 UNKNOWN pair 的两条样本均为 UNKNOWN。

### 2.2 逻辑语义

每条样本都明确给出有限论域、知识库（KB）和查询（q）。论域是封闭且有限的；谓词信息采用开放世界蕴含语义，即未陈述的命题不能仅因缺少陈述就被视为 FALSE。

标签由 Z3 在量词对声明论域展开后计算，不由模型或自然语言生成器指定：

- `TRUE`：KB 蕴涵 q，即 `UNSAT(KB ∧ ¬q)`。
- `FALSE`：KB 蕴涵 ¬q，即 `UNSAT(KB ∧ q)`。
- `UNKNOWN`：KB 既不蕴涵 q，也不蕴涵 ¬q，即两侧都可满足。
- 若 KB 自身不可满足，该样本会被拒绝，不进入有效数据集。

因此，**“无法从 KB 推出 q”不等于 FALSE**。只有 KB 能推出 ¬q 时，标签才是 FALSE。

### 2.3 推理深度

`reasoning_depth` 表示典范证明中推理规则的应用次数：

| 深度 | 样本数 | 说明 |
|---|---:|---|
| 0 | 150 | 直接事实读取或直接读取已陈述的量化句 |
| 1 | 230 | 典范证明包含 1 次推理规则应用 |
| 3 | 210 | 典范证明包含 3 次推理规则应用 |
| 5 | 210 | 典范证明包含 5 次推理规则应用 |
| null | 400 | 没有典范证明；本数据中全部为 UNKNOWN |

深度 0 的 150 条样本全部是 FALSE；`null` 的 400 条样本全部是 UNKNOWN。深度比较应主要在有证明的 TRUE/FALSE 样本中进行，不能把 UNKNOWN 的 null 当作一个更高深度，也不能把深度 0 的结果解释为与深度 1/3/5 完全可比的多跳推理条件。

## 3. 实验变量与数据分布

### 3.1 变量定义

| 变量 | 数据字段 | 取值 | 实验含义 |
|---|---|---|---|
| 否定位置 | `negation_position` | `FACT` / `RULE` / `QUERY` | 被研究的 Not 出现在知识库事实、规则或查询中 |
| 否定辖域 | `negation_scope` | `ATOMIC_PREDICATE` / `RULE_ANTECEDENT` / `RULE_CONSEQUENT` / `QUANTIFIER` / `PROPOSITION` | Not 所作用的逻辑结构 |
| 否定形式 | `negation_form` | `atomic_literal` / `negated_disjunct` / `rule_antecedent` / `rule_consequent` / `negated_universal` / `existential_counterexample` | 否定的具体句法形式 |
| 推理深度 | `reasoning_depth` | `0` / `1` / `3` / `5` / `null` | 典范证明的推理规则应用次数 |
| 推理结果 | `label` | `TRUE` / `FALSE` / `UNKNOWN` | KB 与查询之间的逻辑关系 |
| 查询极性 | `query_polarity` | `POSITIVE` / `NEGATIVE` | 查询本身是否含 Not |
| 否定关键性 | `negation_critical` | `true` / `false` | 删除被研究的 Not 后，标签是否改变 |
| 推理类型 | `inference_type` | `modus_ponens`、`disjunctive_syllogism`、`fact_lookup`、`axiom_lookup`、组合推理、`no_proof` | 实际使用的推理操作 |
| 对照类型 | `pair_type` / `family` | 以 gold 文件中的枚举为准 | 两条样本之间的对照设计 |

`negation_scope`、`negation_form` 和 `inference_type` 是不同维度。例如，`negated_disjunct` 是否定形式，而 `disjunctive_syllogism` 是推理操作，不能混用。

### 3.2 否定位置

| 否定位置 | 样本数 |
|---|---:|
| FACT | 400 |
| RULE | 400 |
| QUERY | 400 |
| **合计** | **1,200** |

### 3.3 否定辖域

| 原始 `negation_scope` | 样本数 |
|---|---:|
| ATOMIC_PREDICATE | 600 |
| RULE_ANTECEDENT | 114 |
| RULE_CONSEQUENT | 204 |
| QUANTIFIER | 111 |
| PROPOSITION | 171 |
| **合计** | **1,200** |

如需在论文中使用更概括的展示分类，可另行合并为 Predicate、Rule、Quantifier、Proposition，但必须明确这是展示层级的合并统计，不能替换原始字段统计。

### 3.4 推理结果

| 标签 | 样本数 |
|---|---:|
| TRUE | 400 |
| FALSE | 400 |
| UNKNOWN | 400 |
| **合计** | **1,200** |

### 3.5 否定数量

每条样本均有一个被研究的目标否定；但全句中的 Not 总数不恒等于 1。负向查询可能额外包含一个查询否定。

- `negation_count`：1 个 Not 的样本 1,110 条；2 个 Not 的样本 90 条。
- `kb_negation_count`：0 个的样本 400 条；1 个的样本 800 条。
- `query_negation_count`：0 个的样本 710 条；1 个的样本 490 条。

因此，实验描述应写“每条样本有一个被研究的目标否定”，不应写成“每条样本总共只有一个否定”。

## 4. 数据划分与使用原则

### 4.1 Split 规模

| Split | 基础案例数 | 样本数 | 主要用途 |
|---|---:|---:|---|
| Train | 420 | 840 | 提示词开发、流程调试或训练用途（若研究设计确实需要） |
| Dev | 60 | 120 | 模型/提示词选择与开发阶段检查 |
| Test | 120 | 240 | 独立最终评价 |
| **Total** | **600** | **1,200** | |

划分以 canonical AST skeleton 为单位。同一 pair、同一 base case，以及 alpha-renaming 后相同的逻辑骨架不会跨 split。仓库验收报告记录 train/test 骨架重叠为 0。

### 4.2 已知划分限制

- Dev 没有 FACT 样本。
- Dev 没有 reasoning depth 0 和 depth 5。
- Test 覆盖当前数据中所有标签、否定位置和深度。
- 所有 split 的论域大小均为 3，句式包均为 `symbol`。

因此，不应声称三个 split 在每个变量上完全平衡。Dev 对 FACT、depth 0、depth 5 的模型选择能力有限；相关最终分组结果应以 Test 和全量描述性统计为依据，并明确报告样本数。

### 4.3 建议的使用规则

1. 在 Dev 上确定提示词、输出解析规则和模型参数。
2. 在正式 Test 评估前冻结提示词、模型版本、解码参数和解析程序。
3. Test 只用于最终评价；不要根据 Test 错误反复修改提示词后再把同一 Test 分数称为独立结果。
4. Train 不自动意味着需要微调。若本 Pilot 仅评估指令模型，可将 Train 用于流程测试或描述性分析，而不进行模型训练。
5. 若额外报告全量 1,200 条的结果，应标记为全量探索性结果，不与独立 Test 结果混为一谈。

## 5. Pilot 实验设计

### Experiment 1：三分类逻辑判断

**研究问题：** 模型能否区分蕴含、矛盾和未知，而不是将“未推出”错误地判断为 FALSE？

- 数据：全部 1,200 条；主要报告 Test 的 240 条。
- 输入：`pilot.public.jsonl` 中的 domain、knowledge_base、query 和 prompt。
- 目标：输出 `TRUE`、`FALSE` 或 `UNKNOWN` 中的一个标签。
- 指标：
  - Accuracy；
  - Macro-F1；
  - 每类 Precision、Recall、F1；
  - 3×3 confusion matrix；
  - 按标签的错误率。

重点检查 UNKNOWN 被误判为 FALSE 的比例，以及 TRUE/FALSE 之间的混淆。

### Experiment 2：否定关键性（Critical vs. Distractor）

**研究问题：** 当目标否定对推导结论是关键的，或只是旁路信息时，模型是否表现出不同的判断行为？

核心数据家族为 `rule_consequent_contrast`：

- 90 对，共 180 条样本；
- POSITIVE query：45 对；
- NEGATIVE query：45 对；
- 每对两条样本使用同一个查询；
- 每对中，一条是 critical，另一条是 distractor；
- 深度覆盖 1、3、5；每个深度下正向和负向查询各 15 对。

**重要标签结构：**

- 正向查询：distractor 对应 TRUE，critical 对应 FALSE。
- 负向查询：上述标签方向反转。
- 合并两种查询极性后，critical 和 distractor 条件各自都包含 TRUE 与 FALSE。
- 只看一种 query polarity 时，条件与 gold label 仍一一对应。

建议指标：

1. Critical 与 Distractor 的 Accuracy、错误率；
2. 每对两条样本的 pair accuracy（两条都答对才算该 pair 完全正确）；
3. 按 POSITIVE / NEGATIVE query polarity 分层报告；
4. 对配对的二元正确/错误结果，可使用 McNemar 检验；报告效应量和置信区间，不只报告 p 值。

**解释限制：** 不能把单一 query polarity 下 critical/distractor 的准确率差异直接解释为否定关键性的独立因果效应，因为此时它与标签方向绑定。主要解释应基于两种 polarity 的分层结果和合并结果。

### Experiment 3：否定位置与辖域

**研究问题：** 否定放在事实、规则或查询中，以及作用于不同逻辑结构时，模型是否出现不同的错误模式？

- 数据：按 `negation_position` 和 `negation_scope` 分组。
- 指标：每组样本数、Accuracy、Macro-F1（类别数足够时）、各标签召回率和混淆矩阵。
- 报告时同时给出每个格子的 n，不能只列百分比。

解释限制：

- QUERY 位置没有 TRUE 样本。
- 部分位置×范围组合在语法或当前生成约束下不适用。
- 因此位置和范围的差异可能同时受到标签构成和推理结构影响。应进行标签分层，避免把未控制的分布差异解释为纯粹位置效应。

### Experiment 4：推理深度

**研究问题：** 多步推理是否增加模型错误？

- 主要比较：reasoning depth 1、3、5。
- 主要分析样本：有典范证明的 TRUE/FALSE 样本。
- 单独报告 depth 0 的直接读取样本。
- UNKNOWN（depth null）单独分析，不纳入 1/3/5 的深度趋势计算。

指标：

- 各深度 Accuracy；
- 各深度 TRUE/FALSE 分层准确率；
- 错误率随深度的变化；
- 置信区间。

解释限制：depth 0 全部为 FALSE，而 depth 1/3/5 的标签分布并不完全相同。应报告标签分层结果，不要只凭总体准确率推断深度因果效应。

### Experiment 5：等价量词形式

**研究问题：** 对逻辑等价但 AST 和表面表达形式不同的句子，模型是否给出一致判断？

- 数据：81 个 `equivalent_form` pair，共 162 条样本。
- 两种形式包括否定全称与存在反例。
- 81 对均通过独立逻辑等价验证。
- 当前这 81 对属于 UNKNOWN 对照家族。

指标：

- pair 内预测一致率；
- 两个成员均预测正确的 pair accuracy；
- 不一致预测的方向和数量。

注意：预测一致不等于预测正确；必须同时报告一致率和正确率。

### Experiment 6：否定消融分析

**研究问题：** 模型是否对目标否定的逻辑作用敏感？

数据集已有 `negation_critical` 标记，且构造时通过删除目标 Not 后重新检查逻辑标签。Pilot 模型层面的消融需要另外构造模型输入：

1. 从 gold 中定位被研究的那个 Not；
2. 只删除该 Not，其他事实、规则、查询和文本保持不变；
3. 重新运行模型；
4. 将原始输入和消融输入的预测与 Z3 标签变化方向比较。

建议指标：

- 原始预测正确率与消融预测正确率；
- 原始预测到消融预测的标签转移矩阵；
- Critical 与 Distractor 的预测变化率；
- 预测变化方向与逻辑标签变化方向的一致率。

**注意：** 数据集的逻辑消融标记不等于模型已经做过消融实验。必须实际生成消融版 public 输入并运行模型，才能报告模型消融结果。若消融文本造成句法不自然或解析失败，应记录并排除/单独报告，不得静默修补。

## 6. 模型与推理设置

仓库当前提供数据生成、Z3 校验、统计和测试代码；仓库中没有配置特定 LLM 的推理服务、模型调用凭据或完整的模型评测 runner。因此，以下属于 Pilot 执行时需要研究者确定并记录的实验设置，不应误认为已由仓库自动实现。

### 6.1 模型选择

建议先使用两个规模不同、均支持指令跟随的模型进行小规模比较，例如：

- Qwen3.5-4B-Instruct；
- Qwen3.5-8B-Instruct。

正式运行前核实模型的实际可用版本、模型 ID、推理框架和上下文限制，并记录精确版本或 commit。若实际模型名称与上述名称不一致，以最终实际调用的模型为准。

### 6.2 控制变量

不同模型之间尽量保持以下设置一致：

- 完全相同的 public 输入和样本顺序；
- 完全相同的系统提示词和任务提示词；
- temperature、top_p、max_new_tokens 等解码参数；
- 是否使用 few-shot 示例；
- 输出解析规则；
- 推理框架及其版本；
- 每条样本的重试策略。

建议主实验使用 zero-shot、temperature=0（若服务支持），并限制输出长度。若模型服务不支持某项参数，应记录实际设置，不要声称参数已被控制。

### 6.3 模型输出格式

模型必须只返回一个标签：

```text
TRUE
```

或

```text
FALSE
```

或

```text
UNKNOWN
```

不符合格式的回答应记为 `invalid_output`，不要用人工猜测把它改成某个标签。若需要解析模型解释，应将 explanation 与最终 label 分开存储，评分只读取明确的最终标签。

### 6.4 建议的统一任务指令

```text
You are solving a formal logic entailment task.

The domain contains exactly the individuals listed in the prompt.
Use only the facts and rules in the knowledge base.
Do not assume that an unstated proposition is false.

Return exactly one label:
TRUE: the knowledge base entails the query.
FALSE: the knowledge base entails the negation of the query.
UNKNOWN: the knowledge base entails neither the query nor its negation.

Output only TRUE, FALSE, or UNKNOWN.
```

将该指令与 public 记录中的任务内容组合。不得向模型提供 gold label、binary_label、AST、proof_trace、negation_critical、pair comparison 或其他答案相关元数据。

## 7. 数据文件、字段与防止答案泄漏

### 7.1 公开输入与金标签

- `data/generated/pilot.public.jsonl`：模型评测输入。
- `data/generated/pilot.gold.jsonl`：金标签、逻辑 AST、证明轨迹、Z3 验证信息和实验审计元数据。

使用 `sample_id` 将模型输出与 gold 对齐。模型运行程序只能读取 public 文件；评分程序才可以读取 gold 文件。

public 输入不得向模型暴露：

- `label`、`binary_label`；
- `query_ast` 或其他 gold AST；
- `proof_trace`、`inference_steps`；
- `negation_critical`；
- `in_controlled_subset`、`logical_pair_validity`、`experimental_control_validity`；
- pair 对照审计结论或任何可直接泄露答案的字段。

仓库最终验收报告记录 public 泄漏检查通过。

### 7.2 建议保存的模型输出字段

每条模型预测至少保存：

| 字段 | 含义 |
|---|---|
| `sample_id` | 对齐 public/gold 的样本编号 |
| `model_name` | 模型名称 |
| `model_revision` | 模型版本或 commit |
| `prompt_version` | 提示词版本 |
| `raw_output` | 模型原始返回文本 |
| `predicted_label` | 解析后的 TRUE/FALSE/UNKNOWN 或 invalid_output |
| `latency_ms` | 推理耗时（若可获取） |
| `input_tokens` / `output_tokens` | token 数（若可获取） |
| `temperature` / `top_p` / `max_new_tokens` | 实际解码参数 |
| `run_id` | 本次实验运行编号 |

保存原始输出，确保后续能够审计解析错误和复算指标。

## 8. 运行前的数据检查

在仓库根目录安装：

```bash
pip install -e ".[dev]"
```

运行数据验证：

```bash
python -m negpilot.cli validate \
  --input data/generated/pilot.gold.jsonl \
  --config configs/pilot.yaml
```

重新生成分布统计：

```bash
python -m negpilot.cli statistics \
  --input data/generated/pilot.gold.jsonl \
  --config configs/pilot.yaml
```

运行单元测试：

```bash
python -m pytest
```

当前仓库 README 明确说明：`data/generated/` 是已发布的 Dataset v1.1；执行 `generate` 会重新构建 JSONL，并使用配额划分器，**不会保留当前 v1.1 的分层 split**。因此，正式 Pilot 前不要为了“检查”而直接运行：

```bash
python -m negpilot.cli generate --config configs/pilot.yaml
```

除非你确实准备重新生成并重新审计数据。应先备份当前版本，并在生成后重新执行完整验收。

## 9. 推荐执行顺序

### Phase 0：冻结实验条件

1. 固定 Dataset v1.1，不修改 gold/public。
2. 运行 validate、statistics 和 pytest。
3. 保存 Git commit、配置文件、数据文件哈希和验收报告。
4. 确定模型精确版本、提示词版本、解码参数和输出解析程序。

### Phase 1：小规模 Smoke Test

每个模型先选取少量样本，检查：

- 模型是否能读取有限论域和符号句式；
- 是否严格输出三个标签之一；
- JSONL 输入输出能否正确对齐；
- 是否出现截断、空输出、格式错误或超时；
- 评分脚本是否正确处理 UNKNOWN 和 invalid_output。

Smoke Test 用于排查执行问题，不作为正式性能结论。不要只挑选容易样本后把结果当成代表性表现。

### Phase 2：Dev 调试

在 Dev 上检查提示词清晰度、输出格式和解析程序。可以调整提示词，但要记录每次版本变化。由于 Dev 缺少 FACT、depth 0 和 depth 5，不能依靠 Dev 完成这些子类的调参。

### Phase 3：冻结并运行 Test

冻结模型、提示词、参数和解析器后，对 240 条 Test 样本运行一次正式评测。若有服务故障，只按预先声明的重试规则重试，并保留失败记录。

### Phase 4：专题分析

按预先定义的实验分析：

- 三分类整体表现；
- 否定关键性 90 对；
- 否定位置与辖域；
- 深度 1/3/5；
- 等价形式 81 对；
- 如已实现模型输入消融，再进行否定消融分析。

专题分析必须同时报告样本数、pair 数、效应量和不确定性范围。小样本子组结果应标为探索性。

## 10. 统计分析与结果报告

### 10.1 必报指标

**三分类：**

- Accuracy；
- Macro-F1；
- 每类 Precision / Recall / F1；
- Confusion matrix；
- invalid output 数量和比例。

**配对对照：**

- pair accuracy（两条成员均正确的 pair 比例）；
- 两条件各自准确率；
- 成对正确/错误转移表；
- McNemar 检验（适用时）；
- 效应量及置信区间。

**分组分析：**

- 按否定位置、辖域、推理深度、query polarity、criticality 分组；
- 每组同时报告 n；
- 对类别构成不平衡的分组，增加按 gold label 分层的结果。

### 10.2 统计注意事项

1. 同一 pair 的两个成员不是独立观测。配对实验应使用配对统计方法，不要把两条样本当成两个完全独立样本。
2. 600 对中只有 290 对是严格受控对照。310 对探索性对照可以描述模型错误现象，但不应用来单独支持某一个变量的因果结论。
3. 否定关键性分析要同时报告正向和负向 query polarity。只报告其中一种会与标签方向混淆。
4. 深度 0 全部为 FALSE，UNKNOWN 全部为 null。不要将深度差异和标签差异混为一谈。
5. QUERY 位置没有 TRUE，FACT 位置没有部分辖域类型；对结构性空格不做补零推断，也不要将其写成模型表现为 0。
6. 81 对等价形式的预测一致率与正确率必须分别报告。
7. 如果比较多个模型或多个子组，应明确多重比较策略；Pilot 阶段可以以效应量和置信区间为主，避免过度依赖显著性检验。

### 10.3 建议的结果表

| Model | N | Accuracy | Macro-F1 | TRUE F1 | FALSE F1 | UNKNOWN F1 | Invalid output |
|---|---:|---:|---:|---:|---:|---:|---:|
| Model A |  |  |  |  |  |  |  |
| Model B |  |  |  |  |  |  |  |

| Analysis | Group A | Group B | N / pairs | Metric | Result |
|---|---|---|---:|---|---|
| Criticality | Critical | Distractor |  | Accuracy / pair accuracy |  |
| Query polarity | Positive | Negative |  | Accuracy |  |
| Depth | 1 hop | 3 hops |  | Accuracy |  |
| Depth | 3 hops | 5 hops |  | Accuracy |  |
| Equivalent form | Negated universal | Existential counterexample | 81 pairs | Prediction consistency |  |

以上表格是报告模板，不代表已经获得任何模型实验结果。

## 11. 复现与归档要求

每次实验至少归档：

```text
pilot_runs/
  <run_id>/
    run_config.yaml
    prompt.txt
    predictions.jsonl
    metrics.json
    confusion_matrix.csv
    pair_analysis.json
    subgroup_analysis.json
    run_log.txt
```

同时记录：

- 仓库 commit；
- Dataset v1.1 文件哈希；
- 模型名称与 revision；
- 推理框架及版本；
- 提示词全文与版本；
- 解码参数；
- 运行日期；
- 失败、重试和 invalid output 记录。

不要覆盖原始预测文件。修正解析程序或统计程序后，应保留原始输出并重新生成派生指标。

## 12. 当前仓库能力与待实现事项

根据当前仓库结构和 README：

**仓库已经提供：**

- 逻辑 AST 和有限论域语义；
- Z3 标签计算与校验；
- 样本生成和数据验证；
- pair 审计与受控/探索性分类；
- split 和骨架泄漏检查；
- 统计报告生成；
- public/gold 分离；
- pytest 测试。

**正式运行 LLM Pilot 前仍需准备：**

- 模型 API 或本地推理服务；
- 批量读取 `pilot.public.jsonl` 并调用模型的 runner；
- 原始输出保存和标签解析程序；
- 预测与 gold 对齐的评分脚本；
- 配对、分组和消融分析脚本；
- 若开展模型消融，生成消融版 public 输入的程序。

因此，仓库中的 `validate` 和 `statistics` 是数据集检查工具，不是模型推理评测命令。完成数据验收不等于已经完成模型 Pilot。

## 13. 当前数据集已知限制

1. Dev 没有 FACT、depth 0 和 depth 5。
2. 只看一种 query polarity 时，criticality 与标签方向绑定。
3. 310 对探索性 pair 同时改变了不止一个因素，不适合用于单变量因果结论。
4. 没有同一 KB 上分别询问 q 与 NOT(q) 的 query-polarity pair。
5. 数据使用有限论域、经典逻辑和封闭的符号句式模板，不是开放英语否定理解的全面测试。
6. 当前各 split 均为论域大小 3、symbol 句式，不能据此评价模型对更大论域或自然语言改写的泛化。

这些限制不妨碍开展当前范围内的 Pilot，但必须在实验报告和论文中明确说明。

---

## 参考文件

- [仓库中文 README](https://github.com/sundowner-miles/negation-pilot/blob/main/README.zh.md)
- [Pilot 配置](https://github.com/sundowner-miles/negation-pilot/blob/main/configs/pilot.yaml)
- [Dataset v1.1 数据说明](https://github.com/sundowner-miles/negation-pilot/blob/main/reports/dataset_v1.1_data_description.md)
- [Dataset v1.1 最终验收报告](https://github.com/sundowner-miles/negation-pilot/blob/main/reports/final_acceptance_report.md)
- [Pilot 验证报告](https://github.com/sundowner-miles/negation-pilot/blob/main/reports/pilot_report.zh.md)
- [CLI 实现](https://github.com/sundowner-miles/negation-pilot/blob/main/src/negpilot/cli.py)
- [Schema 定义](https://github.com/sundowner-miles/negation-pilot/blob/main/src/negpilot/schema.py)
