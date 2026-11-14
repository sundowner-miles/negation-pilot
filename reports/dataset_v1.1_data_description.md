# Dataset v1.1 数据集说明

本文根据 `data/generated/pilot.gold.jsonl` 逐条重新统计。样本数为 1,200，基础案例数为 600，对照对为 600。除特别声明外，表中单位都是样本数（samples）。pair 表会另行标明单位为对照对（pairs）。数字与 v1.0 快照的字段比对、以及存储的 Z3 标记，也直接来自这两个 gold 文件。

## 1. 数据集概述

Dataset v1.1 用于考察大语言模型在形式逻辑推理中如何理解和处理否定。它不是开放域事实问答集。每条样本给出一个有限论域、一组事实和规则，以及一条查询。模型需要判断知识库与查询之间的蕴含关系。

数据规模如下。

| 项目 | 数量 | 单位 |
| --- | ---: | --- |
| 样本 | 1,200 | samples |
| 基础案例 `base_case_id` | 600 | base cases |
| 对照对 `pair_id` | 600 | pairs |
| 每个基础案例包含的 pair | 1 | pair |
| 每个 pair 包含的样本 | 2 | samples |

语义是有限论域上的经典逻辑，采用开放世界蕴含。论域写在样本中，1,200 条的论域大小都是 3。句式包 `nl_pack` 都是 `symbol`。量词先在该论域上展开，再由 Z3 判定。知识库自身不可满足的样本不进入数据集。不能因为没有推出查询，就把样本标成 FALSE。

三种标签的定义是：

| 标签 | 定义 |
| --- | --- |
| TRUE | 知识库蕴涵查询。等价于 `UNSAT(KB ∧ ¬q)`，且 `SAT(KB ∧ q)`。 |
| FALSE | 知识库蕴涵查询的否定。等价于 `UNSAT(KB ∧ q)`，且 `SAT(KB ∧ ¬q)`。 |
| UNKNOWN | 既不能推出查询，也不能推出查询的否定。两边都可满足。 |

主要实验变量包括否定出现的位置、否定所作用的逻辑结构、典范证明的推理深度，以及目标否定是否参与该结论的推导。600 对对照分成严格受控对照 290 对和探索性对照 310 对。严格受控对照只改变事先声明的操作变量。探索性对照在逻辑上仍然有效，但同时改变了不止一个实验因素，不能单独当作因果证据。

当前文件的 `dataset_version` 都是 `1.1`。

## 2. 变量与取值说明

下表保留 gold 中的原始字段名和枚举值。可读名称只是说明，不替换字段里的值。

| 字段 | 原始取值 | 可读名称 | 含义与研究作用 |
| --- | --- | --- | --- |
| `negation_position` | `FACT` / `RULE` / `QUERY` | 事实 / 规则 / 查询 | 被研究的那个 Not 位于事实、规则或查询。用于比较否定出现的位置是否改变模型表现。`FACT` 不是改写后的 Context 标签；若论文需要英文称呼，应写作 fact in the knowledge base，并声明它对应原始值 `FACT`。 |
| `negation_scope` | `ATOMIC_PREDICATE` / `RULE_ANTECEDENT` / `RULE_CONSEQUENT` / `QUANTIFIER` / `PROPOSITION` | 原子谓词 / 规则前件 / 规则后件 / 量词 / 整句 | 被研究否定所作用的结构。这是辖域字段，不是 `negation_form`。 |
| `negation_form` | `atomic_literal` / `negated_disjunct` / `rule_antecedent` / `rule_consequent` / `negated_universal` / `existential_counterexample` | 原子字面量 / 否定析取项 / 规则前件 / 规则后件 / 否定全称 / 存在反例 | 被研究否定的句法形式。析取三段论不写在这个字段里。 |
| `negation_embedding` | `atomic` / `disjunction` / `rule_antecedent` / `rule_consequent` / `negated_universal` / `existential` | 结构位置 | Not 所在的句法位置。与 `negation_form` 一一对应，但名称不同。 |
| `inference_type` | 见下表 | 推理操作 | 典范证明实际使用的推理操作。与否定形式分开记录。 |
| `reasoning_depth` | `0` / `1` / `3` / `5` / `null` | 推理深度 | 典范证明中推理规则的应用次数。 |
| `label` | `TRUE` / `FALSE` / `UNKNOWN` | 推理结果 | 知识库对查询的蕴含判定。 |
| `query_polarity` | `POSITIVE` / `NEGATIVE` | 查询极性 | 查询本身是否含 Not。`NEGATIVE` 表示 `query_negation_count = 1`。 |
| `negation_critical` | `true` / `false` | critical / distractor | 删掉被研究的那个 Not 之后，标签是否改变。`true` 记为 critical，`false` 记为 distractor。这是单条样本属性。 |
| `family` | 见第 5 节 | 对照家族 | 一对样本所属的实验对照。 |
| `pair_type` | 见下表 | 对照类型 | 这一对在结构上做了哪一种比较。 |
| `in_controlled_subset` | `true` / `false` | 严格受控 / 探索性 | 这一对是否只改变声明过的操作变量。 |
| `split` | `train` / `dev` / `test` | 数据划分 | 样本所属划分。不表示必须用 train 做微调。 |

`negation_form` 与 `negation_scope` 的对应是固定的，但二者不是同一个维度。例如 `negated_disjunct` 的辖域是 `ATOMIC_PREDICATE`，`negated_universal` 的辖域是 `PROPOSITION`。不能用形式名去代替辖域名。

### 推理深度

| 值 | 样本数 | 含义 |
| --- | ---: | --- |
| `0` | 150 | 没有使用推理规则。结论来自直接读取一条事实，或直接读取一条已经写明的量化句。这 150 条全部是 FALSE。 |
| `1` | 230 | 典范证明使用一次推理规则。 |
| `3` | 210 | 典范证明使用三次推理规则。 |
| `5` | 210 | 典范证明使用五次推理规则。 |
| `null` | 400 | 没有典范证明。这 400 条全部是 UNKNOWN，`inference_type` 全部是 `no_proof`。 |

`null` 不是更深的推理，也不是推理失败后的残差。它表示在给定语义下，知识库既不蕴涵查询，也不蕴涵查询的否定，因此不存在把查询或查询的否定推出来的典范证明。深度 1、3、5 的数量并不相等，不能写成均匀分布。

### 否定数量

每条样本都有一个被研究的 Not。对 1,200 条样本定位该 Not 后，宿主公式均可归入上表中的六种形式，没有无法定位的样本。因此被研究的否定是每条一个。全部 Not 的个数并不总是 1：负向查询会再带一个 Not。

三个计数字段的关系在 1,200 条上都满足 `negation_count = kb_negation_count + query_negation_count`。

| 字段 | 取值 | 样本数 | 含义 |
| --- | --- | ---: | --- |
| `negation_count` | 1 | 1,110 | 全句中的 Not 总数为 1。 |
| `negation_count` | 2 | 90 | 全句中的 Not 总数为 2。这 90 条都是 `rule_consequent_contrast` 的负向查询成员。 |
| `kb_negation_count` | 0 | 400 | 知识库中没有 Not。被研究的否定在查询里。 |
| `kb_negation_count` | 1 | 800 | 知识库中有一个 Not。 |
| `query_negation_count` | 0 | 710 | 查询不含 Not，即 `POSITIVE`。 |
| `query_negation_count` | 1 | 490 | 查询含一个 Not，即 `NEGATIVE`。 |

三种实际组合是：

| `kb_negation_count` | `query_negation_count` | `negation_count` | 样本数 | 位置 |
| ---: | ---: | ---: | ---: | --- |
| 1 | 0 | 1 | 710 | `FACT` 或 `RULE`，查询为正向 |
| 0 | 1 | 1 | 400 | 全部是 `QUERY` |
| 1 | 1 | 2 | 90 | 全部是 `RULE`，且查询为负向 |

不能把 `negation_count` 写成恒等于 1。被研究的 Not 是每条一个；多出来的那一个只出现在上述 90 条负向查询里，而且同一对的两条样本都有它，所以它是控制变量，不是这对对照所操纵的差异。

### 推理类型

| `inference_type` | 样本数 | 含义 |
| --- | ---: | --- |
| `modus_ponens` | 490 | 证明使用肯定前件式。 |
| `no_proof` | 400 | 没有典范证明，对应全部 UNKNOWN。 |
| `modus_ponens_then_disjunctive_syllogism` | 100 | 先使用肯定前件式，最后一步是否定析取三段论。 |
| `fact_lookup` | 90 | 直接读取事实，深度为 0。 |
| `axiom_lookup` | 60 | 直接读取已写明的量化句，深度为 0。 |
| `disjunctive_syllogism` | 60 | 一步否定析取三段论。 |

合计 1,200。`disjunctive_syllogism` 只出现在 `inference_type`，不出现在 `negation_form`。对应的 160 条样本，形式都是 `negated_disjunct`。

### 对照类型

| `pair_type` | 样本数 | 对数 | 含义 |
| --- | ---: | ---: | --- |
| `negation_relocation` | 440 | 220 | 否定在一对的两个成员之间改换位置或附着点。 |
| `counterfactual_fact` | 378 | 189 | 对事实做反事实改写。 |
| `counterfactual_rule` | 180 | 90 | 对规则做反事实改写。 |
| `equivalent_form` | 162 | 81 | 否定全称与存在反例这两种等价写法。 |
| `query_target_contrast` | 40 | 20 | 原子查询的对象对照。 |

合计 1,200 条、600 对。数据中没有 `query_polarity` 这种 pair type。不存在“同一知识库上分别问 `q` 和 `NOT(q)`”的对照。

## 3. 数据集变量分布

### 3.1 总体分布

单位均为样本数。每一组之和都是 1,200。

| `label` | 样本数 |
| --- | ---: |
| TRUE | 400 |
| FALSE | 400 |
| UNKNOWN | 400 |

| `negation_position` | 样本数 |
| --- | ---: |
| FACT | 400 |
| RULE | 400 |
| QUERY | 400 |

| `reasoning_depth` | 样本数 |
| --- | ---: |
| 0 | 150 |
| 1 | 230 |
| 3 | 210 |
| 5 | 210 |
| null | 400 |

| `query_polarity` | 样本数 |
| --- | ---: |
| POSITIVE | 710 |
| NEGATIVE | 490 |

| `negation_critical` | 可读名称 | 样本数 |
| --- | --- | ---: |
| true | critical | 658 |
| false | distractor | 542 |

上表是全部 1,200 条上的样本属性。它把多个家族混在一起，不能直接当成 90 对关键性实验的边际分布。该实验的表在第 5.1 节。

| `negation_count` | 样本数 |
| --- | ---: |
| 1 | 1,110 |
| 2 | 90 |

`inference_type` 的分布已列在第 2 节。

### 3.2 否定范围的两种统计口径

这两张表回答的不是同一个问题。第一张统计原始字段 `negation_scope`。第二张按 `negation_form` 合并，只用于展示否定的句法家族。不能把两张表中同名或近名的行相加或互相替换。

**A. 原始 `negation_scope`**

| `negation_scope` | 样本数 |
| --- | ---: |
| ATOMIC_PREDICATE | 600 |
| RULE_ANTECEDENT | 114 |
| RULE_CONSEQUENT | 204 |
| QUANTIFIER | 111 |
| PROPOSITION | 171 |

合计 1,200。AST 审计中，形式与辖域的对应没有例外：

| `negation_form` | 宿主 | `negation_scope` | 样本数 |
| --- | --- | --- | ---: |
| `atomic_literal` | `Not(Atom)` | ATOMIC_PREDICATE | 440 |
| `negated_disjunct` | 析取项为 `Not` 的 `Or` | ATOMIC_PREDICATE | 160 |
| `rule_antecedent` | `ForAll` 蕴含的前件含 `Not` | RULE_ANTECEDENT | 114 |
| `rule_consequent` | `ForAll` 蕴含的后件含 `Not` | RULE_CONSEQUENT | 204 |
| `existential_counterexample` | `Exists` | QUANTIFIER | 111 |
| `negated_universal` | `Not(ForAll)` | PROPOSITION | 171 |

因此 `ATOMIC_PREDICATE` 的 600 条等于 440 条原子字面量加 160 条否定析取项。`PROPOSITION` 的 171 条全部是否定全称，不是析取。

**B. 按否定形式合并的展示分类**

该分类只在 AST 宿主与上表一致时使用。它不是 `negation_scope` 的别名。

| 展示类别 | 样本数 | 对应 `negation_form` | 这些样本的原始 `negation_scope` |
| --- | ---: | --- | --- |
| Predicate | 440 | `atomic_literal` | 全部是 ATOMIC_PREDICATE |
| Rule | 318 | `rule_antecedent` 114 + `rule_consequent` 204 | RULE_ANTECEDENT 与 RULE_CONSEQUENT |
| Quantifier | 282 | `negated_universal` 171 + `existential_counterexample` 111 | PROPOSITION 171，加上 QUANTIFIER 111 |
| Proposition | 160 | `negated_disjunct` | 全部是 ATOMIC_PREDICATE，不是 scope 值 PROPOSITION |

440 + 318 + 282 + 160 = 1,200。

需要同时记住的三个差异是：

- 展示类别 Proposition 是 160，原始 scope `PROPOSITION` 是 171。前者是析取里的否定，后者是否定全称。
- 展示类别 Quantifier 是 282，原始 scope `QUANTIFIER` 是 111。282 把否定全称和存在反例合在一起，因为二者在经典逻辑中等价、AST 不同。
- 展示类别 Predicate 是 440，原始 scope `ATOMIC_PREDICATE` 是 600。多出的 160 是 `negated_disjunct`。

展示类别 Rule 的 318 与两个规则辖域之和相同，这一行可以互相对上。其余三行不能对读。

### 3.3 推理深度分布

| `reasoning_depth` | 样本数 | 其中的标签 |
| --- | ---: | --- |
| 0 | 150 | 150 条 FALSE。`fact_lookup` 90 条，`axiom_lookup` 60 条。 |
| 1 | 230 | TRUE 140，FALSE 90。没有 UNKNOWN。 |
| 3 | 210 | TRUE 130，FALSE 80。没有 UNKNOWN。 |
| 5 | 210 | TRUE 130，FALSE 80。没有 UNKNOWN。 |
| null | 400 | 400 条 UNKNOWN。 |

150 + 230 + 210 + 210 + 400 = 1,200。深度 0 是直接读取，不是“比 1 更浅的失败”。`null` 只标记没有典范证明的 UNKNOWN，不能放进 1、3、5 的深度比较。

## 4. 核心交叉分布

空单元格的计数是 0。这些组合在当前构造中没有生成，原因写在表后。它们不是生成失败，也不应在分析时补成 FALSE。

### 4.1 Label × Negation Position

单位：样本数。

| `label` | FACT | RULE | QUERY | 合计 |
| --- | ---: | ---: | ---: | ---: |
| TRUE | 160 | 240 | 0 | 400 |
| FALSE | 90 | 90 | 220 | 400 |
| UNKNOWN | 150 | 70 | 180 | 400 |
| 合计 | 400 | 400 | 400 | 1,200 |

`QUERY` × TRUE 为 0。这 400 条查询位置样本的知识库都不含 Not，唯一的 Not 在查询中。TRUE 要求这份没有否定的知识库蕴涵一条否定查询。本数据集的正事实和正规则不产生这种蕴涵。

### 4.2 Label × Negation Scope

单位：样本数。

| `label` | ATOMIC_PREDICATE | RULE_ANTECEDENT | RULE_CONSEQUENT | QUANTIFIER | PROPOSITION | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TRUE | 160 | 90 | 90 | 0 | 60 | 400 |
| FALSE | 250 | 0 | 90 | 30 | 30 | 400 |
| UNKNOWN | 190 | 24 | 24 | 81 | 81 | 400 |
| 合计 | 600 | 114 | 204 | 111 | 171 | 1,200 |

空缺：

- `RULE_ANTECEDENT` × FALSE 为 0。否定前件要推出一个否定的基结论，需要另一个否定去触发前件。那就成为知识库中的第二个被研究否定，当前构造不生成这种样本。现有 114 条是 TRUE 90 条和 UNKNOWN 24 条。
- `QUANTIFIER` × TRUE 为 0。存在反例这一辖域上的确定标签只有 FALSE 30 条，其余 81 条是 UNKNOWN。
- `RULE` 位置上的 `QUANTIFIER` 和 `PROPOSITION` 没有 FALSE。规则位置的量化否定共 11 + 71 = 82 条，其中 FALSE 为 0：PROPOSITION 是 TRUE 60 与 UNKNOWN 11，QUANTIFIER 是 UNKNOWN 11。量化句上的 FALSE 30 + 30 条都在 `QUERY` 位置，查询否定的是一条已经写明的全称句。

### 4.3 Label × Reasoning Depth

单位：样本数。

| `label` | 0 | 1 | 3 | 5 | null | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TRUE | 0 | 140 | 130 | 130 | 0 | 400 |
| FALSE | 150 | 90 | 80 | 80 | 0 | 400 |
| UNKNOWN | 0 | 0 | 0 | 0 | 400 | 400 |
| 合计 | 150 | 230 | 210 | 210 | 400 | 1,200 |

深度 0 没有 TRUE，也没有 UNKNOWN。肯定的基结论至少要使用一次推理规则，所以 TRUE 的最小深度是 1。UNKNOWN 没有典范证明，深度只能是 null。

### 4.4 Negation Position × Reasoning Depth

单位：样本数。

| `negation_position` | 0 | 1 | 3 | 5 | null | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FACT | 90 | 60 | 50 | 50 | 150 | 400 |
| RULE | 0 | 110 | 110 | 110 | 70 | 400 |
| QUERY | 60 | 60 | 50 | 50 | 180 | 400 |
| 合计 | 150 | 230 | 210 | 210 | 400 | 1,200 |

`RULE` × 深度 0 为 0。深度 0 只来自事实读取和量化句的直接读取，不来自规则链。`FACT` × FALSE 只出现在深度 0，共 90 条。事实位置的 FALSE 是直接写出的否定事实，不是 3 步或 5 步证明。事实位置在深度 1、3、5 上的 160 条都是 TRUE。

### 4.5 Negation Criticality × Gold Label

单位：样本数。范围是全部 1,200 条，不是 90 对实验子集。

| `negation_critical` | TRUE | FALSE | UNKNOWN | 合计 |
| --- | ---: | ---: | ---: | ---: |
| true（critical） | 205 | 355 | 98 | 658 |
| false（distractor） | 195 | 45 | 302 | 542 |
| 合计 | 400 | 400 | 400 | 1,200 |

这张表不能解释成“关键否定导致 FALSE”。658 条 critical 分布在多个家族中，其中 FALSE 355 条、TRUE 205 条、UNKNOWN 98 条。严格的关键性对照只有 `rule_consequent_contrast` 的 180 条，见第 5.1 节。

### 4.6 Negation Criticality × Query Polarity

单位：样本数。范围同样是全部 1,200 条。

| `negation_critical` | POSITIVE | NEGATIVE | 合计 |
| --- | ---: | ---: | ---: |
| true（critical） | 393 | 265 | 658 |
| false（distractor） | 317 | 225 | 542 |
| 合计 | 710 | 490 | 1,200 |

全量交叉里，两种极性下两种关键性都有样本。这仍然不是一个把极性单独操纵出来的实验。

### 4.7 Query Polarity × Gold Label

单位：样本数。

| `query_polarity` | TRUE | FALSE | UNKNOWN | 合计 |
| --- | ---: | ---: | ---: | ---: |
| POSITIVE | 355 | 135 | 220 | 710 |
| NEGATIVE | 45 | 265 | 180 | 490 |
| 合计 | 400 | 400 | 400 | 1,200 |

正向查询更多得到 TRUE，负向查询更多得到 FALSE。这是当前构造的边际分布，不是极性本身的因果效应。数据集没有保持知识库不变、只把查询从 `q` 换成 `NOT(q)` 的 pair。

## 5. 对照数据结构

600 个 `pair_id` 各有 2 条样本，600 个 `base_case_id` 各对应恰好一个 pair。对照单位是 pair，不是样本。

| 类别 | 对数 | 样本数 |
| --- | ---: | ---: |
| 严格受控，`in_controlled_subset = true` | 290 | 580 |
| 探索性，`in_controlled_subset = false` | 310 | 620 |
| 合计 | 600 | 1,200 |

同一对的两条样本，受控标记一致。重新按声明的控制变量、操作变量和派生变量比对后，存储标记与比对结果一致：受控对没有拒绝原因，探索性对都有拒绝原因。

| `family` | 对数 | 样本数 | 类别 |
| --- | ---: | ---: | --- |
| `antecedent_vs_query_atomic` | 90 | 180 | 探索性 |
| `disjunction_vs_query_atomic` | 70 | 140 | 探索性 |
| `fact_ds_vs_negfact` | 90 | 180 | 探索性 |
| `quantifier_distractor_vs_query` | 60 | 120 | 探索性 |
| `rule_consequent_contrast` | 90 | 180 | 严格受控 |
| `unk_fact_block` | 75 | 150 | 严格受控 |
| `unk_query_atomic_target` | 20 | 40 | 严格受控 |
| `unk_query_quantifier_form` | 70 | 140 | 严格受控 |
| `unk_rule_antecedent` | 12 | 24 | 严格受控 |
| `unk_rule_consequent` | 12 | 24 | 严格受控 |
| `unk_rule_quantifier_form` | 11 | 22 | 严格受控 |
| 合计 | 600 | 1,200 |  |

受控对数 90 + 75 + 20 + 70 + 12 + 12 + 11 = 290。探索性对数 90 + 70 + 90 + 60 = 310。

### 5.1 否定关键性对照

`rule_consequent_contrast` 有 90 对、180 条样本，全部属于严格受控子集。查询极性为 POSITIVE 的 45 对，NEGATIVE 的 45 对。

每一对的两条样本在以下字段上相同：`query_ast`、`domain`、`inference_type`、`proof_depth`、`relevant_premise_count`、`negation_count`、`kb_negation_count`、`query_negation_count`、`negation_position`、`negation_scope`、`negation_embedding`、`query_polarity`，以及事实条数和规则条数。两条样本的差异是 `negation_critical` 及其设计所声明的派生内容。90 对中没有控制字段不一致的对。

存储的消融记录覆盖全部 180 条，删除后知识库都可满足：

| 条件 | 删除前 | 删除后 | 样本数 | 是否符合设计 |
| --- | --- | --- | ---: | --- |
| POSITIVE，distractor | TRUE | TRUE | 45 | 标签不变 |
| POSITIVE，critical | FALSE | TRUE | 45 | 标签改变 |
| NEGATIVE，distractor | FALSE | FALSE | 45 | 标签不变 |
| NEGATIVE，critical | TRUE | FALSE | 45 | 标签改变 |

把极性分开以后，标签表是：

| `query_polarity` | distractor 的标签 | critical 的标签 | 对数 |
| --- | --- | --- | ---: |
| POSITIVE | TRUE | FALSE | 45 |
| NEGATIVE | FALSE | TRUE | 45 |

两种极性合在一起时，critical 有 TRUE 45 条和 FALSE 45 条，distractor 同样有 TRUE 45 条和 FALSE 45 条。只分析一种极性时，关键性和标签是一一对应的：正向里 critical 全是 FALSE，负向里 critical 全是 TRUE。这个对应是设计结果，不是可以忽略的抽样误差。

### 5.2 等价形式对照

`pair_type = equivalent_form` 有 81 对、162 条样本。每一对的两种形式都是 `negated_universal` 与 `existential_counterexample`，辖域分别是 `PROPOSITION` 与 `QUANTIFIER`。81 对的标签都是 UNKNOWN。等价类都是 `NEGATED_UNIVERSAL_EXISTENTIAL_COUNTEREXAMPLE`。162 条样本的 `semantic_equivalent` 都是 true，`equivalence_verification` 都是 `pass`。没有其他 pair type 被标成语义等价。

这 81 对分布在两个家族：`unk_query_quantifier_form` 70 对，`unk_rule_quantifier_form` 11 对。它们都在严格受控子集中。

这一对照保持经典语义，改变的是 AST 和句子形式：`¬∀x(A(x) → B(x))` 与 `∃x(A(x) ∧ ¬B(x))`。它用于观察模型是否对这两种写法给出不同预测。它不用于比较 TRUE 与 FALSE，因为这两边的金标签都是 UNKNOWN。

### 5.3 探索性对照

310 对探索性样本的逻辑标签仍然由 Z3 决定，并保留在数据集中。它们没有通过实验控制检查，因为一对内部同时改变了未声明为操作变量的内容。实际差异包括推理类型、证明深度、否定嵌入或否定功能，以及知识库本身。

四个探索性家族是 `antecedent_vs_query_atomic`、`disjunction_vs_query_atomic`、`fact_ds_vs_negfact` 和 `quantifier_distractor_vs_query`。这些对可以用来描述模型在哪些逻辑改写上出错，也可以用来寻找后续要单独控制的现象。它们不宜作为“只改变一个因素”的主要证据。

## 6. 数据划分

划分单位是基础案例。每个基础案例恰好是一个 pair，所以下表的“配对组”同时等于 base case 数和 pair 数。

| Split | 配对组 | 样本数 | 用途 |
| --- | ---: | ---: | --- |
| train | 420 | 840 | 开发阶段的探索、错误分析和提示词初稿。不是必须用于微调的训练集。 |
| dev | 60 | 120 | 开发过程中的检查，包括提示词和解析规则。 |
| test | 120 | 240 | 不参与开发决策的独立测试，用于最终报告。 |
| 合计 | 600 | 1,200 | 全部数据 |

同一 `pair_id`、同一 `base_case_id` 和同一条 `canonical_skeleton` 都只出现在一个 split。按共享 canonical skeleton 做连通后，600 个基础案例形成 27 个不可拆组。不同组可以有不同的骨架字符串；骨架字符串共有 55 个，跨 split 的骨架数是 0。27 是不可拆组的个数，不是每个 split 的配对组个数。

三个 split 在标签、位置和深度上都不完全平衡。下面的数字是分组约束下的实际分布，不是目标配额的完成声明。

### Split × Label

单位：样本数。

| Split | TRUE | FALSE | UNKNOWN | 合计 |
| --- | ---: | ---: | ---: | ---: |
| train | 275 | 275 | 290 | 840 |
| dev | 45 | 45 | 30 | 120 |
| test | 80 | 80 | 80 | 240 |
| 合计 | 400 | 400 | 400 | 1,200 |

### Split × Negation Position

单位：样本数。

| Split | FACT | RULE | QUERY | 合计 |
| --- | ---: | ---: | ---: | ---: |
| train | 310 | 280 | 250 | 840 |
| dev | 0 | 60 | 60 | 120 |
| test | 90 | 60 | 90 | 240 |
| 合计 | 400 | 400 | 400 | 1,200 |

### Split × Reasoning Depth

单位：样本数。

| Split | 0 | 1 | 3 | 5 | null | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 120 | 140 | 150 | 140 | 290 | 840 |
| dev | 0 | 60 | 30 | 0 | 30 | 120 |
| test | 30 | 30 | 30 | 70 | 80 | 240 |
| 合计 | 150 | 230 | 210 | 210 | 400 | 1,200 |

dev 没有 FACT，也没有深度 0 和深度 5。带确定标签的 FACT 组大小是 50 或 60 个基础案例，放进只有 60 个基础案例的 dev 会占满该划分。唯一较小的 FACT 组是 10 条 UNKNOWN，留在 test。test 则包含全部三种标签、全部三个位置，以及 0、1、3、5 和 null 五种深度。

`train`、`dev`、`test` 是数据隔离，不是训练流程。Pilot 可以只做推断，不必微调。若研究者在全部 1,200 条上看模型行为，该结果是探索性分析，必须与只在 240 条 test 上计算的最终指标分开报告。用全量结果选择提示词或样例之后，再在同一批 test 上报告成绩，test 就不再独立。

## 7. 与 Pilot 实验的对应关系

评测输入使用 `pilot.public.jsonl`。该文件含查询、知识库文本、论域和 split，不含金标签、证明、`negation_critical` 和消融标签。金标签和分析变量从 gold 按 `sample_id` 对齐。

| Pilot 实验 | 研究问题 | 使用数据 | 主要指标 |
| --- | --- | --- | --- |
| Experiment 1：三分类能力 | 模型能否区分蕴涵、反向蕴涵和未知？ | 全部 1,200 条；最终数字报告 test 的 240 条 | Accuracy、Macro-F1、三行混淆矩阵 |
| Experiment 2：否定关键性 | 关键否定与干扰否定的错误率是否不同？ | `rule_consequent_contrast` 的 90 对 | 配对错误率差、pair accuracy、McNemar |
| Experiment 3：位置与范围 | 不同位置和辖域是否有不同错误模式？ | 按 `negation_position` 和 `negation_scope` 分组 | 分组 Accuracy、按金标签分层的错误类型 |
| Experiment 4：推理深度 | 更多推理步骤是否带来更多错误？ | TRUE 与 FALSE 中深度为 1、3、5 的样本 | 各深度 Accuracy |
| Experiment 5：等价形式 | 两种等价写法是否得到不同预测？ | 81 对 `equivalent_form` | 成对预测一致率 |
| Experiment 6：否定消融 | 删掉目标 Not 后，模型预测是否随之改变？ | 90 对关键性对照，以及删掉被研究 Not 后的输入 | 预测变化率、变化方向与金标签变化是否一致 |

### Experiment 1

样本是全部 1,200 条，标签各 400 条。开发检查可以用 dev 的 120 条。对外报告的准确率和宏平均 F1 应来自 test 的 240 条，其中三种标签各 80 条。混淆矩阵至少要分开 UNKNOWN 被判成 FALSE、以及 FALSE 被判成 UNKNOWN。前者会把“推不出”误写成“证明为假”。全量 1,200 条上的分数只作为探索，不与 test 分数混成一个最终数。

### Experiment 2

使用 90 对、180 条。每对一条 critical、一条 distractor，查询和深度相同。可以计算每对是否只有一边答错，再用 McNemar 或配对比例差比较两种条件。

限制有两条。第一，正向 45 对里 distractor 的金标签全是 TRUE、critical 全是 FALSE；负向 45 对正好相反。只做一个极性时，条件差异和标签差异无法分开。主分析应同时纳入两种极性，或在极性内部分别报告、并说明标签绑定。第二，不要把第 4.5 节的 1,200 条关键性交叉表当作这个实验的样本。

### Experiment 3

位置各有 400 条，五个辖域的数量见第 3.2 节 A。test 中三个位置都有样本：FACT 90、RULE 60、QUERY 90。dev 没有 FACT，所以位置比较的开发检查不能覆盖事实否定。

`QUERY` 没有 TRUE。位置效应必须在同一金标签内比较，例如只在 FALSE 中比较 FACT、RULE 和 QUERY，或只在 TRUE 中比较 FACT 和 RULE。把三个位置的整体准确率直接排名，会把“查询位置没有 TRUE”算进位置效应。辖域分析同样要避开第 4.2 节中的空单元格，不要把 0 解释成模型在该格上完全失败。

### Experiment 4

可比的多跳样本是标签为 TRUE 或 FALSE、且深度为 1、3 或 5 的样本。全量中这三个深度分别是 230、210、210，其中没有 UNKNOWN。深度 0 的 150 条全是 FALSE，深度 null 的 400 条全是 UNKNOWN。

null 不参加 1/3/5 的比较。深度 0 也不能用来证明“浅层推理更难”或“更易”：它没有 TRUE，推理操作是 `fact_lookup` 或 `axiom_lookup`，和多跳的 `modus_ponens` 不是同一个任务。test 中深度 0、1、3、5、null 都有样本，但深度 5 有 70 条，深度 0、1、3 各有 30 条，比较时要报告每格的分母。dev 不能做深度 0 或深度 5 的检查。

### Experiment 5

使用 81 对、162 条。每对的两条金标签都是 UNKNOWN，一句是否定全称，另一句是存在反例，有限域上的等价标记为通过。指标是模型对两条样本是否给出相同预测，以及是否都给出 UNKNOWN。

一致率高只说明模型对这两种写法的输出相同，不说明它正确理解了等价。两条都答成 TRUE，一致率也是 1。因此要同时报告一致率和 UNKNOWN 准确率。这 81 对全部是受控对照，但它们不估计深度效应，也不估计 TRUE/FALSE 效应。

### Experiment 6

输入是 90 对关键性对照的原文，以及只删除被研究 Not、保留查询中那个控制用 Not 的消融文本。金标签的变化方向已经由第 5.1 节给出：distractor 的 90 条标签不变，critical 的 90 条标签改变，消融后的知识库都可满足。

模型侧可以报告：预测是否改变，以及改变方向是否与金标签的改变方向相同。critical 上，正向对的金标签从 FALSE 变为 TRUE，负向对从 TRUE 变为 FALSE。distractor 上，预测若改变，就不能解释成“模型正确跟踪了这个 Not”。消融输入不是 gold 文件中的另一条样本；构造该输入时只能删除被研究的那个 Not。

### 使用这些实验时的共同限制

- UNKNOWN 的深度都是 null，不进入深度 1、3、5 的比较。
- 深度 0 全是 FALSE，不能单独证明浅层推理更困难。
- `QUERY` 没有 TRUE。位置比较要按标签分层。
- 只看一种查询极性时，90 对里的关键性和金标签一一对应。
- 没有专门的 query-polarity pair。不能把极性的边际分布说成极性的因果作用。
- 310 对探索性对照不是单一变量实验的主要证据。

## 8. 数据质量与适用范围

以下结果来自当前 v1.1 gold 与 `dataset-v1.0/pilot.gold.jsonl` 的逐条字段比对。

| 检查 | 结果 |
| --- | --- |
| 样本总数 | 1,200 |
| `sample_id` 与 v1.0 的集合 | 相同 |
| 重复 `sample_id` | 0 |
| 重复逻辑结构（论域、语句 AST、查询 AST） | 0 |
| 非法标签 | 0 |
| `verification.matches_expected` 为真 | 1,200 / 1,200 |
| `verification_status = pass` | 1,200 / 1,200 |
| 相对 v1.0，`label` 发生变化 | 0 |
| 相对 v1.0，知识库语句 AST 发生变化 | 0 |
| 相对 v1.0，`query_ast` 发生变化 | 0 |
| 相对 v1.0，`proof_trace` 发生变化 | 0 |
| 相对 v1.0，`reasoning_depth` 发生变化 | 0 |
| 严格受控 pair | 290 |
| 探索性 pair | 310 |

存储的 Z3 成功标记是 1.000。最终验收时曾对全部样本重新求解，结论与这些存储标签一致；本说明文档本身不再改写数据。

本数据集适用于研究大语言模型在有限论域经典逻辑中的否定理解、开放世界三分类，以及按典范证明计数的多步推理。论域大小固定为 3，句子来自封闭的符号模板，不是开放英语。结论应限定在这些任务和当前分布之内，不应直接推广为模型处理一切自然语言否定的能力。
