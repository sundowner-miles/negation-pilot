# 阶段二：test 集上的实验 1–3

这是独立 test 的 240 条。dev 和 train 没有参与这次评分。全量 1,200 条没有运行。
提示词版本是 plan-6.4-v1，两个模型都使用贪心解码，思考模式关闭。
实验 3 的分组准确率是描述性结果。探索性对照同时改变了多个因素，不能单独当成位置或辖域的因果效应。

## 实验 1：三分类

### Qwen/Qwen3.5-4B

n=240，正确 160，Accuracy 66.7%（95% Wilson [60.5%, 72.3%]），Macro-F1 0.607，invalid 0。 TRUE F1 0.904，FALSE F1 0.638，UNKNOWN F1 0.280。

| 标签 | n | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| TRUE | 80 | 0.825 | 1.000 | 0.904 |
| FALSE | 80 | 0.515 | 0.838 | 0.638 |
| UNKNOWN | 80 | 1.000 | 0.163 | 0.280 |

| 金标签 \ 预测 | TRUE | FALSE | UNKNOWN | invalid_output |
| --- | ---: | ---: | ---: | ---: |
| TRUE | 80 | 0 | 0 | 0 |
| FALSE | 13 | 67 | 0 | 0 |
| UNKNOWN | 4 | 63 | 13 | 0 |

UNKNOWN 被判成 FALSE：63 / 80。 FALSE 被判成 UNKNOWN：0 / 80。

### Qwen/Qwen3.5-9B

n=240，正确 126，Accuracy 52.5%（95% Wilson [46.2%, 58.7%]），Macro-F1 0.456，invalid 0。 TRUE F1 0.590，FALSE F1 0.661，UNKNOWN F1 0.118。

| 标签 | n | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| TRUE | 80 | 0.419 | 1.000 | 0.590 |
| FALSE | 80 | 0.932 | 0.512 | 0.661 |
| UNKNOWN | 80 | 1.000 | 0.062 | 0.118 |

| 金标签 \ 预测 | TRUE | FALSE | UNKNOWN | invalid_output |
| --- | ---: | ---: | ---: | ---: |
| TRUE | 80 | 0 | 0 | 0 |
| FALSE | 39 | 41 | 0 | 0 |
| UNKNOWN | 72 | 3 | 5 | 0 |

UNKNOWN 被判成 FALSE：3 / 80。 FALSE 被判成 UNKNOWN：0 / 80。

## 实验 2：否定关键性

只使用 test 中的 `rule_consequent_contrast`。全部 90 对里还有 60 对在 train 或 dev，这次没有运行。
正向查询里 distractor 的金标签是 TRUE、critical 是 FALSE；负向查询相反。只看一种极性时，条件和标签绑在一起。

### Qwen/Qwen3.5-4B

对数 30。pair accuracy（两条都对）90.0%。 critical Accuracy 93.3%，distractor Accuracy 96.7%。
critical 减 distractor 的准确率差是 -3.3%，自助法 95% 区间 [-13.3%, 6.7%]（10000 次，种子 20261111）。 McNemar 精确检验：discordant 3 （critical 错而 distractor 对 2，相反 1），双侧 p=1.0000。

| 极性 | 对数 | critical Accuracy | distractor Accuracy | pair accuracy | 准确率差 | 95% 区间 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| POSITIVE | 15 | 86.7% | 100.0% | 86.7% | -13.3% | [-33.3%, 0.0%] |
| NEGATIVE | 15 | 100.0% | 93.3% | 93.3% | 6.7% | [0.0%, 20.0%] |

被拒绝的不完整 pair：0。

### Qwen/Qwen3.5-9B

对数 30。pair accuracy（两条都对）33.3%。 critical Accuracy 80.0%，distractor Accuracy 53.3%。
critical 减 distractor 的准确率差是 26.7%，自助法 95% 区间 [0.0%, 53.3%]（10000 次，种子 20261111）。 McNemar 精确检验：discordant 20 （critical 错而 distractor 对 6，相反 14），双侧 p=0.1153。

| 极性 | 对数 | critical Accuracy | distractor Accuracy | pair accuracy | 准确率差 | 95% 区间 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| POSITIVE | 15 | 60.0% | 100.0% | 60.0% | -40.0% | [-66.7%, -13.3%] |
| NEGATIVE | 15 | 100.0% | 6.7% | 6.7% | 93.3% | [80.0%, 100.0%] |

被拒绝的不完整 pair：0。

## 实验 3：位置与辖域

下面每个格子都带样本数。某个位置没有出现的金标签不写成准确率 0。

### Qwen/Qwen3.5-4B：位置

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| FACT | 90 | 82 | 91.1% | [83.4%, 95.4%] | 0.744 |
| QUERY | 90 | 21 | 23.3% | [15.8%, 33.1%] | 未计算 |
| RULE | 60 | 57 | 95.0% | [86.3%, 98.3%] | 未计算 |

| 组 | 金标签 | n | 正确 | Accuracy |
| --- | --- | ---: | ---: | ---: |
| FACT | TRUE | 50 | 50 | 100.0% |
| FACT | FALSE | 30 | 30 | 100.0% |
| FACT | UNKNOWN | 10 | 2 | 20.0% |
| QUERY | FALSE | 20 | 10 | 50.0% |
| QUERY | UNKNOWN | 70 | 11 | 15.7% |
| RULE | TRUE | 30 | 30 | 100.0% |
| RULE | FALSE | 30 | 27 | 90.0% |

### Qwen/Qwen3.5-4B：辖域

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| ATOMIC_PREDICATE | 110 | 92 | 83.6% | [75.6%, 89.4%] | 0.687 |
| PROPOSITION | 35 | 1 | 2.9% | [0.5%, 14.5%] | 未计算 |
| QUANTIFIER | 35 | 10 | 28.6% | [16.3%, 45.1%] | 未计算 |
| RULE_CONSEQUENT | 60 | 57 | 95.0% | [86.3%, 98.3%] | 未计算 |

| 组 | 金标签 | n | 正确 | Accuracy |
| --- | --- | ---: | ---: | ---: |
| ATOMIC_PREDICATE | TRUE | 50 | 50 | 100.0% |
| ATOMIC_PREDICATE | FALSE | 50 | 40 | 80.0% |
| ATOMIC_PREDICATE | UNKNOWN | 10 | 2 | 20.0% |
| PROPOSITION | UNKNOWN | 35 | 1 | 2.9% |
| QUANTIFIER | UNKNOWN | 35 | 10 | 28.6% |
| RULE_CONSEQUENT | TRUE | 30 | 30 | 100.0% |
| RULE_CONSEQUENT | FALSE | 30 | 27 | 90.0% |

受控对照与探索性对照分开：

受控

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| FACT | 10 | 2 | 20.0% | [5.7%, 51.0%] | 未计算 |
| QUERY | 70 | 11 | 15.7% | [9.0%, 26.0%] | 未计算 |
| RULE | 60 | 57 | 95.0% | [86.3%, 98.3%] | 未计算 |

探索性

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| FACT | 80 | 80 | 100.0% | [95.4%, 100.0%] | 未计算 |
| QUERY | 20 | 10 | 50.0% | [29.9%, 70.1%] | 未计算 |

### Qwen/Qwen3.5-9B：位置

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| FACT | 90 | 85 | 94.4% | [87.6%, 97.6%] | 0.866 |
| QUERY | 90 | 1 | 1.1% | [0.2%, 6.0%] | 未计算 |
| RULE | 60 | 40 | 66.7% | [54.1%, 77.3%] | 未计算 |

| 组 | 金标签 | n | 正确 | Accuracy |
| --- | --- | ---: | ---: | ---: |
| FACT | TRUE | 50 | 50 | 100.0% |
| FACT | FALSE | 30 | 30 | 100.0% |
| FACT | UNKNOWN | 10 | 5 | 50.0% |
| QUERY | FALSE | 20 | 1 | 5.0% |
| QUERY | UNKNOWN | 70 | 0 | 0.0% |
| RULE | TRUE | 30 | 30 | 100.0% |
| RULE | FALSE | 30 | 10 | 33.3% |

### Qwen/Qwen3.5-9B：辖域

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| ATOMIC_PREDICATE | 110 | 86 | 78.2% | [69.6%, 84.9%] | 0.744 |
| PROPOSITION | 35 | 0 | 0.0% | [0.0%, 9.9%] | 未计算 |
| QUANTIFIER | 35 | 0 | 0.0% | [0.0%, 9.9%] | 未计算 |
| RULE_CONSEQUENT | 60 | 40 | 66.7% | [54.1%, 77.3%] | 未计算 |

| 组 | 金标签 | n | 正确 | Accuracy |
| --- | --- | ---: | ---: | ---: |
| ATOMIC_PREDICATE | TRUE | 50 | 50 | 100.0% |
| ATOMIC_PREDICATE | FALSE | 50 | 31 | 62.0% |
| ATOMIC_PREDICATE | UNKNOWN | 10 | 5 | 50.0% |
| PROPOSITION | UNKNOWN | 35 | 0 | 0.0% |
| QUANTIFIER | UNKNOWN | 35 | 0 | 0.0% |
| RULE_CONSEQUENT | TRUE | 30 | 30 | 100.0% |
| RULE_CONSEQUENT | FALSE | 30 | 10 | 33.3% |

受控对照与探索性对照分开：

受控

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| FACT | 10 | 5 | 50.0% | [23.7%, 76.3%] | 未计算 |
| QUERY | 70 | 0 | 0.0% | [0.0%, 5.2%] | 未计算 |
| RULE | 60 | 40 | 66.7% | [54.1%, 77.3%] | 未计算 |

探索性

| 组 | n | 正确 | Accuracy | 95% Wilson | Macro-F1 |
| --- | ---: | ---: | ---: | --- | ---: |
| FACT | 80 | 80 | 100.0% | [95.4%, 100.0%] | 未计算 |
| QUERY | 20 | 1 | 5.0% | [0.9%, 23.6%] | 未计算 |

本 split 中没有样本的位置：无。没有样本的辖域：RULE_ANTECEDENT。
位置×金标签样本数为 0 的格子：RULE×UNKNOWN, QUERY×TRUE。

这些空格子是当前 test 划分里没有生成的组合，不是模型在该格上得分为 0。

