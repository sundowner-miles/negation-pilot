# 否定推理试点验证报告

[English](pilot_report.md)

## 结果

- 生成样本：1200
- 基础案例：600
- 对照对：600
- TRUE / FALSE / UNKNOWN：400 / 400 / 400
- 无效样本：0
- 重复样本编号：0
- 重复逻辑结构：0
- Z3 验证成功率：1.000
- 校验通过：是

标签的算法是：先把每个量词展开到名单里列出的有限论域，再交给 Z3。TRUE 表示知识库加上查询的否定不可满足。FALSE 表示知识库加上查询本身不可满足。UNKNOWN 表示两边都可满足。知识库自身不可满足的样本会被拒绝。仅仅推不出来的命题不会被标成 FALSE。推理深度等于典范证明中推理规则的使用次数。直接写出的事实深度为 0。没有典范证明的样本深度为 null。互补标签本身不足以构成受控对照。

## 类别、位置、范围与深度

### 标签

| 标签 | 数量 |
| --- | --- |
| FALSE | 400 |
| TRUE | 400 |
| UNKNOWN | 400 |

### 否定位置

| 位置 | 数量 |
| --- | --- |
| FACT（事实） | 400 |
| QUERY（查询） | 400 |
| RULE（规则） | 400 |

### 否定范围

| 范围 | 数量 |
| --- | --- |
| ATOMIC_PREDICATE（原子谓词） | 600 |
| PROPOSITION（整句） | 171 |
| QUANTIFIER（量词） | 111 |
| RULE_ANTECEDENT（规则前件） | 114 |
| RULE_CONSEQUENT（规则后件） | 204 |

`¬∀x(A(x) → B(x))` 记为 PROPOSITION。`∃x(A(x) ∧ ¬B(x))` 记为 QUANTIFIER。两者在经典逻辑中等价，但抽象语法树不同。

### 推理深度

| 深度 | 数量 |
| --- | --- |
| 0 | 150 |
| 1 | 230 |
| 3 | 210 |
| 5 | 210 |
| null | 400 |

### 标签 × 位置

| 位置 | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| FACT | 90 | 160 | 150 |
| QUERY | 220 | 0 | 180 |
| RULE | 90 | 240 | 70 |

### 标签 × 范围

| 范围 | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| ATOMIC_PREDICATE | 250 | 160 | 190 |
| PROPOSITION | 30 | 60 | 81 |
| QUANTIFIER | 30 | 0 | 81 |
| RULE_ANTECEDENT | 0 | 90 | 24 |
| RULE_CONSEQUENT | 90 | 90 | 24 |

### 标签 × 深度

| 深度 | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| 0 | 150 | 0 | 0 |
| 1 | 90 | 140 | 0 |
| 3 | 80 | 130 | 0 |
| 5 | 80 | 130 | 0 |
| null | 0 | 0 | 400 |

深度 null 的 400 条都是 UNKNOWN。深度 0 的 150 条都是 FALSE，来自直接写出的否定事实，或查询本身就在否定一条已经写明的全称句。深度 0 没有 TRUE，因为肯定结论至少要用一次推理规则。

### 位置 × 范围

| 位置 | ATOMIC_PREDICATE | RULE_ANTECEDENT | RULE_CONSEQUENT | QUANTIFIER | PROPOSITION |
| --- | --- | --- | --- | --- | --- |
| FACT | 400 | 0 | 0 | 0 | 0 |
| QUERY | 200 | 0 | 0 | 100 | 100 |
| RULE | 0 | 114 | 204 | 11 | 71 |

### 位置 × 深度

| 位置 | 0 | 1 | 3 | 5 | null |
| --- | --- | --- | --- | --- | --- |
| FACT | 90 | 60 | 50 | 50 | 150 |
| QUERY | 60 | 60 | 50 | 50 | 180 |
| RULE | 0 | 110 | 110 | 110 | 70 |

### 范围 × 深度

| 范围 | 0 | 1 | 3 | 5 | null |
| --- | --- | --- | --- | --- | --- |
| ATOMIC_PREDICATE | 90 | 120 | 100 | 100 | 190 |
| PROPOSITION | 30 | 20 | 20 | 20 | 81 |
| QUANTIFIER | 30 | 0 | 0 | 0 | 81 |
| RULE_ANTECEDENT | 0 | 30 | 30 | 30 | 24 |
| RULE_CONSEQUENT | 0 | 60 | 60 | 60 | 24 |

### 对照类型

数量按样本计，每对含 2 条样本。

| 对照类型 | 样本数 | 含义 |
| --- | --- | --- |
| counterfactual_fact | 378 | 事实的反事实改写 |
| counterfactual_rule | 180 | 规则的反事实改写 |
| equivalent_form | 162 | 等价量词形式 |
| negation_relocation | 440 | 否定位置迁移 |
| query_target_contrast | 40 | 查询对象对照 |

查询极性对照（同一知识库上分别问 `q` 和 `NOT(q)`）：0。

### 受控对照子集

标签有效、单条样本有效、逻辑对照有效、实验控制有效分开记录。两条样本不可比，或者推理操作和目标否定属性一起改变、又没有声明这是推理类型对照时，该对留在探索性样本里。探索性样本仍留在数据集中。原因见 `reports/pair_comparison.jsonl`。

- 已审计的对照对：600
- 严格受控对照对：290
- 探索性对照对：310

| 家族 | 受控 | 探索性 | 含义 |
| --- | --- | --- | --- |
| antecedent_vs_query_atomic | 0 | 90 | 否定前件与原子查询 |
| disjunction_vs_query_atomic | 0 | 70 | 析取三段论与原子查询 |
| fact_ds_vs_negfact | 0 | 90 | 析取事实与否定事实 |
| quantifier_distractor_vs_query | 0 | 60 | 量词旁路与量化查询 |
| rule_consequent_contrast | 90 | 0 | 规则后件的关键否定与干扰否定 |
| unk_fact_block | 75 | 0 | 事实阻断的 UNKNOWN |
| unk_query_atomic_target | 20 | 0 | 原子查询的对象对照 |
| unk_query_quantifier_form | 70 | 0 | 查询上的等价量词 |
| unk_rule_antecedent | 12 | 0 | 规则前件未触发 |
| unk_rule_consequent | 12 | 0 | 规则后件闲置 |
| unk_rule_quantifier_form | 11 | 0 | 规则上的等价量词 |

| 原因 | 对数 |
| --- | --- |
| undeclared_change:knowledge_base（知识库差异未声明） | 310 |
| undeclared_change:negation_function（否定功能差异未声明） | 310 |
| undeclared_change:statement_template（句式差异未声明） | 310 |
| undeclared_change:negation_embedding（否定嵌入差异未声明） | 280 |
| hard_control_differs:inference_type（推理类型属于硬控制，却发生了变化） | 220 |
| hard_control_differs:query（查询属于硬控制，却发生了变化） | 220 |
| inference_and_negation_property_both_change（推理类型与否定属性同时改变） | 220 |
| undeclared_change:inference_type（推理类型差异未声明） | 220 |
| undeclared_change:kb_negation_count（知识库否定数量差异未声明） | 220 |
| undeclared_change:negation_position（否定位置差异未声明） | 220 |
| undeclared_change:query（查询差异未声明） | 220 |
| undeclared_change:query_negation_count（查询否定数量差异未声明） | 220 |
| undeclared_change:query_polarity（查询极性差异未声明） | 220 |
| hard_control_differs:proof_depth（证明深度属于硬控制，却发生了变化） | 150 |
| undeclared_change:negation_critical（否定关键性差异未声明） | 150 |
| undeclared_change:proof_depth（证明深度差异未声明） | 150 |
| undeclared_change:relevant_premise_count（相关前提数量差异未声明） | 150 |
| undeclared_change:fact_count（事实数量差异未声明） | 130 |
| undeclared_change:rule_count（规则数量差异未声明） | 130 |
| negation_position_and_scope_both_change（否定位置与范围同时改变） | 120 |
| undeclared_change:negation_scope（否定范围差异未声明） | 120 |

同一对可以有多条原因，所以各行相加大于 310。

### 否定形式

| 形式 | 样本数 | 含义 |
| --- | --- | --- |
| atomic_literal | 440 | 原子字面量 |
| negated_disjunct | 160 | 否定析取项。推理操作仍记在 inference_type，为 disjunctive_syllogism 或 modus_ponens_then_disjunctive_syllogism |
| existential_counterexample | 111 | 存在反例 |
| negated_universal | 171 | 否定全称 |
| rule_antecedent | 114 | 规则前件 |
| rule_consequent | 204 | 规则后件 |

### 删掉被研究的否定后，标签是否改变

`起作用` 表示标签会变。`旁路` 表示删掉后标签不变。消融只删除被研究的那个否定。本次 1200 条在删除后知识库仍然可满足。

| 标签 | 旁路 | 起作用 |
| --- | --- | --- |
| FALSE | 45 | 355 |
| TRUE | 195 | 205 |
| UNKNOWN | 302 | 98 |

FALSE 里的 45 条旁路来自负向查询上的干扰否定：查询是 `¬B(a)`，关键否定在另一条样本里，这一条的否定不参与推导。把正向查询和负向查询合在一起，关键否定与干扰否定各自都有 TRUE 和 FALSE。

## 划分

基础案例整份划入一个划分，所以一对中的两条样本始终在一起。目标是基础案例的 70% 训练、10% 开发、20% 测试。每个划分的论域大小都是 3，句式都是 symbol。字母换名后相同的逻辑骨架留在同一个划分里，替换谓词字母不算留出的测试项。600 个基础案例收成 27 个不可拆组。dev 没有 FACT，也没有 depth 0 和 depth 5；test 覆盖了已有的全部标签、位置和深度。分组原因见 `reports/dataset_v1.1_summary.md`。

| 划分 | 样本数 |
| --- | --- |
| dev | 120 |
| test | 240 |
| train | 840 |

### 划分 × 标签

| 划分 | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| dev | 45 | 45 | 30 |
| test | 80 | 80 | 80 |
| train | 275 | 275 | 290 |

### 划分 × 位置

| 划分 | FACT | RULE | QUERY |
| --- | --- | --- | --- |
| dev | 0 | 60 | 60 |
| test | 90 | 60 | 90 |
| train | 310 | 280 | 250 |

### 划分 × 深度

| 划分 | 0 | 1 | 3 | 5 | null |
| --- | --- | --- | --- | --- | --- |
| dev | 0 | 60 | 30 | 0 | 30 |
| test | 30 | 30 | 30 | 70 | 80 |
| train | 120 | 140 | 150 | 140 | 290 |

### 划分 × 句式包

| 划分 | symbol |
| --- | --- |
| dev | 120 |
| test | 240 |
| train | 840 |

## 不适用的格子

下列位置与范围的组合没有生成。数据中的计数为 0。

| 位置 | 范围 | 原因 |
| --- | --- | --- |
| FACT | RULE_ANTECEDENT | 试点中的事实不带量词，没有可供否定占据的规则前件。 |
| FACT | RULE_CONSEQUENT | 试点中的事实不带量词，没有可供否定占据的规则后件。 |
| FACT | QUANTIFIER | 存在反例里的否定是量化句，存成规则或查询，不存成基事实。 |
| FACT | PROPOSITION | 整句否定的全称句是量化句，存成规则或查询，不存成基事实。 |
| RULE | ATOMIC_PREDICATE | 本试点中原子谓词上的否定是基字面量或基析取。量化句才是规则，所以这一格不用。 |
| QUERY | RULE_ANTECEDENT | 否定的规则前件是知识库中的规则，不是试点查询。查询是基字面量或封闭的量化句。 |
| QUERY | RULE_CONSEQUENT | 否定的规则后件是知识库中的规则，不是试点查询。 |

下面这些格子句法上合法，但由于否定数量约束，或由于最短证明达不到所要求的深度，所以是空的。

- **查询位置的 TRUE。** 被研究的否定若在查询里，知识库就是全正的。TRUE 就要求这份知识库蕴涵那个否定查询。本试点的正规则和正事实推不出否定句，所以这一格是空的。
- **规则前件的 FALSE。** 从否定前件推出否定的基结论，需要第二个否定字面量来触发前件。那就是知识库里的第二个否定，所以这一格是空的。
- **规则位置上、范围为 QUANTIFIER 或 PROPOSITION 的 FALSE。** 知识库中的否定全称并不指明哪个论域元素是反例，因此它本身推不出一个否定的基原子。量化句上的 FALSE 是那些否定一条已写明全称句的查询。
- **深度 3 或 5 上、事实位置的 FALSE。** 否定的基事实是直接陈述的，推理深度为 0，不是一步推理。多跳 FALSE 使用否定的规则后件或否定的查询。
- **深度大于 0 时，查询位置且范围为 QUANTIFIER 或 PROPOSITION 的 FALSE。** 知识库已经直接陈述了那条全称句，查询是它的否定，所以证明是深度为 0 的公理查找。没有用到的跳数不计入深度。
- **对照类型 query_polarity。** 这种对照保持同一个知识库，同时问 `q` 和 `NOT(q)`。否定关键性家族改为让两条样本共用同一个查询，查询可以是正向的，也可以是负向的。负向查询会多出一个否定，这个否定在同一对里相同，属于控制变量。

## 句式如何保持区分

“Every C is not D” 和 “No C is D” 是否定的规则后件 `ForAll(x, Implies(C(x), Not(D(x))))`。
“Not every C is D” 和 “Not (every C is D)” 是否定全称 `Not(ForAll(x, Implies(C(x), D(x))))`。
“Some C is not D” 是存在反例 `Exists(x, And(C(x), Not(D(x))))`。
在经典逻辑中，否定全称和存在反例等价。否定后件与这两者都不等价。
实际写入数据的是符号句式：`Every A is not B.`、`Every non-A is B.`、`Not every A is B.`、`Some A is not B.`。四种句子各自解析回不同的抽象语法树。alpha 和 beta 句框仍留在渲染器里，对应同一批公式。

- `ForAll(x, Implies(C(x), Not(D(x))))`
  - 也称为：Every C is not D，No C is D。每个 C 都不是 D。
  - 符号句式：Every A is not B.
  - Alpha 句框：For every individual, if the individual is C, then the individual is not D.
  - Beta 句框：Whenever an individual has property C, that individual does not have property D.
- `ForAll(x, Implies(Not(C(x)), D(x)))`
  - 也称为：Every non-C is D，Anyone who is not C is D。每个非 C 都是 D。
  - 符号句式：Every non-A is B.
  - Alpha 句框：For every individual, if the individual is not C, then the individual is D.
  - Beta 句框：Whenever an individual does not have property C, that individual has property D.
- `Not(ForAll(x, Implies(C(x), D(x))))`
  - 也称为：Not every C is D，Not (every C is D)。并非每个 C 都是 D。
  - 符号句式：Not every A is B.
  - Alpha 句框：It is not true that for every individual, if the individual is C, then the individual is D.
  - Beta 句框：It is not the case that whenever an individual has property C, that individual has property D.
- `Exists(x, And(C(x), Not(D(x))))`
  - 也称为：Some C is not D，There is a C that is not D。有的 C 不是 D。
  - 符号句式：Some A is not B.
  - Alpha 句框：There is at least one individual that is C and is not D.
  - Beta 句框：At least one individual has property C and does not have property D.

## 骨架与泄漏

- 抽象模板键：45
- 出现在不止一个划分中的抽象模板键：7

带具体谓词字母、个体和论域的完整逻辑结构必须唯一。完全相同的结构会导致校验失败。谓词和个体做字母换名之后，相同骨架留在同一个划分里。跨划分的骨架数量见 `reports/split_leakage_report.json`，当前为 0。较粗的模板键仍可能出现在多个划分里，因为那些实例是不同的骨架。

## 验证过程

生成时先构造抽象语法树，拒绝畸形公式，展开量词，再调用 Z3。若判定与模板的预期标签不一致，该样本被拒绝。它不会被改标签，也不会被复制来填配额。判定通过后，抽象语法树被渲染成句子，再解析回去。审计随后重算每条标签，并检查对照对、深度、否定提示词和配额。

## 局限

- 单个经典否定要成为肯定原子结论的关键前提，删掉它之后蕴涵关系必须改变。在本试点中，这种情况出现于析取三段论，以及删掉后会使 FALSE 或 UNKNOWN 翻转的否定事实、否定后件和否定查询。有些 TRUE 样本把那个否定放在未使用的旁路规则上，这些否定标记为 `negation_critical: false`。
- 同一知识库上分别问 `q` 和 `NOT(q)` 不是一种对照类型。否定关键性家族让两条样本共用同一个查询，查询可以是正向的，也可以是负向的。负向查询会多出一个否定，这个否定属于控制变量。
- 由否定基事实得到的 FALSE 是事实查找，推理深度为 0。事实位置的 FALSE 不出现在深度 3 或 5。
- 否定全称并不说明哪个个体是例外。除非查询就是该量化句本身，否则这些样本对基原子保持 UNKNOWN。
- 语法是上面这组封闭模板，不是开放英语的解析器。
- 谓词和个体都是单个字母。字母表用到 A–Z，因为深度 5 的链再加一条旁路规则，A–F 不够用。量词变量保持为 x、y、z。
