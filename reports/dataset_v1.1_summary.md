# Dataset v1.1

这次整理保留了 v1.0 的 1,200 条样本。金标签、查询、知识库 AST、证明和 Z3 记录没有改写。
改动限于划分、否定形式元数据、等价形式标记和对照说明。

## 审计问题

1. 全部 1,200 条样本都还在。样本编号集合与 v1.0 相同。
2. 所有 gold label 保持不变。逐条哈希包含 label。
3. 所有逻辑 AST 保持不变。逐条哈希包含 statement AST 和 query AST。
4. 存储的 Z3 验证结果保持不变，且每条 `matches_expected` 仍为真。 新鲜复核见关键性审计：无效 pair 0。
5. 新划分：train 840，dev 120，test 240。 基础案例 420 / 60 / 120。
6. 同一个 pair、同一个 base_case、同一条 canonical skeleton 都只出现在一个 split。 train/test 骨架重叠为 0。
7. test 的 depth 1 从 0 变为 30。 test 的 depth 3 从 0 变为 30。 test 的 depth 5 从 130 变为 70。 dev 的 FACT 从 0 变为 0。唯一小于 dev 配额、且含 FACT 的组是 5 个基础案例、10 条 UNKNOWN。把它放进 dev 的最优补全，全局分层分数是 8046，差于当前划分的 7358。这 10 条因此留在 test，用来补齐 test 的 FACT 和 UNKNOWN。
8. `negation_form = disjunctive_syllogism` 的 160 条样本，被研究的 Not 都在析取的左支上。形式改为 `negated_disjunct`，embedding 改为 `disjunction`，function 改为 `disjunctive_premise`。inference_type 仍是 `disjunctive_syllogism` 或 `modus_ponens_then_disjunctive_syllogism`。
9. rule_consequent_contrast 共 90 对：POSITIVE 45，NEGATIVE 45。 不符合设计的 pair：0。
10. 正向查询里，干扰否定是 TRUE、关键否定是 FALSE。负向查询相反。把两种查询合在一起后，两种条件都有 TRUE 和 FALSE。只看一种查询方向时，条件和标签仍然一一对应。
11. 等价量词 pair 通过独立 Z3 验证的数量：81。 失败：0。
12. 严格受控 pair 与探索性 pair 的数量没有为了凑数而改写。 受控 290，探索性 310。 形式字段的改写没有改变对照判定。
13. 仍在的限制：canonical skeleton 把 600 个基础案例收成 27 个不可拆组。带 TRUE 或 FALSE 的 FACT 组大小是 50 或 60，放进 dev 会占满该划分。dev 因此没有 FACT，也没有 depth 0 和 depth 5。三个 split 都有 TRUE、FALSE、UNKNOWN。test 覆盖了已有的全部深度和全部否定位置。只分析一种 query polarity 时，关键性与标签仍然绑在一起。探索性 pair 仍同时改变推理类型或深度。

## 修改前后

| 项目 | v1.0 | v1.1 |
| --- | ---: | ---: |
| 样本 | 1200 | 1200 |
| dev FACT | 0 | 0 |
| test depth 1 | 0 | 30 |
| test depth 3 | 0 | 30 |
| test depth 5 | 130 | 70 |
| test FACT | 160 | 90 |
| test QUERY | 20 | 90 |
| test UNKNOWN | 80 | 80 |
| 哈希不一致 | 0 | 0 |

v1.0 文件在 `dataset-v1.0/`，没有被覆盖。
