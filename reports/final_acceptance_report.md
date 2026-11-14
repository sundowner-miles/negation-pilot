# Dataset v1.1 最终验收

结论：**READY FOR PILOT**

本次只读取 `dataset-v1.0/pilot.gold.jsonl`、当前 gold、public，并重新调用 Z3。没有修改样本。

## 1. 数据完整性

结果：**PASS**

- v1.0 / v1.1 样本数：1200 / 1200
- sample_id 集合一致：True
- label、KB AST、query AST、proof trace、reasoning_depth 变化的样本：0
- 重新运行 Z3：1200 / 1200 与存储标签一致
- 无效样本：0
- 重复 sample_id：0
- 重复逻辑结构：0

不一致的 sample_id：无。

## 2. 数据划分

结果：**PASS**

- train / dev / test：840 / 120 / 240
- pair、base_case、canonical skeleton、skeleton_id 均不跨 split
- test 标签：FALSE, TRUE, UNKNOWN
- test 位置：FACT, QUERY, RULE
- test 深度：0, 1, 3, 5, null
- dev FACT / depth 0 / depth 5：0 / 0 / 0。这是已说明的分组限制，本次没有改划分。

## 3. 三个核心实验设计

结果：**PASS**

- 否定关键性：90 对，POSITIVE 45，NEGATIVE 45，问题 0
- negated_disjunct：160 条，推理类型 {'disjunctive_syllogism': 60, 'modus_ponens_then_disjunctive_syllogism': 100}，问题 0
- 等价量词：81 对，Z3 通过 81，问题 0

## 4. 数据泄漏和对照分类

结果：**PASS**

- public 泄漏检查：0 项
- 严格受控 pair：290
- 探索性 pair：310
- 新鲜对照审计与存储标记不一致：0

## 结论

1. 可以启动 Pilot。
2. 没有必须修复的问题。
3. 可以接受的研究限制：dev 没有 FACT、depth 0 和 depth 5；只看一种 query polarity 时，关键性仍和标签绑在一起；310 对探索性样本不是严格受控对照。
