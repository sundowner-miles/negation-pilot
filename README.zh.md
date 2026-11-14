# 否定推理试点数据集

[English](README.md)

这是一套用于多跳演绎中逻辑否定的受控合成基准。金标签由 Z3 在明确列出的有限论域上计算，不由语言模型指定。推不出来的命题不会被标成 FALSE。

## 语义

每条样本的论域是有限且封闭的，并写在提示词里。谓词信息是不完备的：没有陈述、也推不出来的原子命题保持开放。

对可满足的知识库 `KB` 和查询 `q`：

- `TRUE` 当且仅当 `KB` 蕴涵 `q`，当且仅当 `UNSAT(KB ∧ ¬q)`
- `FALSE` 当且仅当 `KB` 蕴涵 `¬q`，当且仅当 `UNSAT(KB ∧ q)`
- `UNKNOWN` 当且仅当 `SAT(KB ∧ q)` 且 `SAT(KB ∧ ¬q)`

若 `KB` 本身不可满足，该样本被丢弃。量词先在声明的论域上展开，再交给求解器。逻辑式是抽象语法树节点（`Atom`、`Not`、`And`、`Or`、`Implies`、`ForAll`、`Exists`），不是英语句子。

## 这几句英语分别是什么意思

下面四种日常说法不能互换。

| 日常说法 | 公式 | 试点里实际使用的句子 |
| --- | --- | --- |
| Every C is not D. / No C is D.（每个 C 都不是 D / 没有 C 是 D） | `∀x (C(x) → ¬D(x))` | For every individual, if the individual is C, then the individual is not D. |
| Every non-C is D.（每个非 C 都是 D） | `∀x (¬C(x) → D(x))` | For every individual, if the individual is not C, then the individual is D. |
| Not every C is D. / Not (every C is D).（并非每个 C 都是 D） | `¬∀x (C(x) → D(x))` | It is not true that for every individual, if the individual is C, then the individual is D. |
| Some C is not D.（有的 C 不是 D） | `∃x (C(x) ∧ ¬D(x))` | There is at least one individual that is C and is not D. |

后两行在经典逻辑里等价。第一行和它们都不等价。生成给模型看的句子使用符号句式，四种结构可以各自还原成抽象语法树：`Every A is not B.`、`Every non-A is B.`、`Not every A is B.`、`Some A is not B.`。谓词是单个大写字母，个体是除 `x`、`y`、`z` 以外的单个小写字母。alpha 和 beta 句式仍留在渲染器里，对应同一批公式。

## 试点规模

1200 条样本，600 个对照对，随机种子 `20261111`。

- 400 个确定对照对：一条 `TRUE`，一条 `FALSE`
- 200 个不确定对照对：两条都是 `UNKNOWN`
- 类别计数：400 / 400 / 400
- 知识库里有一个被研究的否定。否定关键性对照里的负向查询会再增加一个否定，这个查询否定在同一对的两条样本上相同
- 推理深度等于典范证明中推理规则的使用次数。直接写出的事实深度为 0。多跳证明的深度为 1、3、5。没有典范证明的样本深度为 `null`
- 否定位置 `FACT`、`RULE`、`QUERY` 在样本层面各 400 条

否定关键性对照在两条样本上使用同一个查询，查询可以是 `B(a)`，也可以是 `¬B(a)`。正向查询时，干扰否定对应 TRUE，关键否定对应 FALSE。负向查询把这两个标签对调。把两种查询方向合在一起看，实验条件不和某一个金标签绑死。同一知识库上分别问 `q` 和 `NOT(q)` 的对照没有生成。每一对都由 Z3 单独验证。不会为了凑数量而事后改标签。互补标签本身不足以构成受控对照。`logical_pair_validity` 和 `experimental_control_validity` 分开记录。未通过对照检查的样本对仍保留为探索性样本，并写明原因。600 对里有 290 对进入严格受控子集，310 对是探索性样本。

一部分 `TRUE` 样本把这唯一的否定放在证明用不到的旁路规则上。`negation_critical` 记录删掉这个否定后标签会不会变。真正起作用的肯定式是否定析取三段论：`¬P ∨ Q` 加上 `P` 可以推出 `Q`。

## 划分

Dataset v1.1 按 AST 的 canonical skeleton 划分。同一对、同一个基础案例，以及字母换名后相同的骨架，都留在同一个划分。600 个基础案例收成 27 个不可拆组，所以 840 / 120 / 240 的样本配额是精确的，部分边际分布不是。dev 没有 FACT：唯一能放进 dev 的 FACT 组只有 10 条 UNKNOWN，放进去会让标签、位置和深度的联合平衡变差。test 覆盖了已有的全部标签、位置和深度。说明见 `reports/dataset_v1.1_summary.md`。

| 划分 | 基例 | 样本 | 论域大小 | 句式 |
| --- | --- | --- | --- | --- |
| train | 70%（420） | 840 | 3 | symbol |
| dev | 10%（60） | 120 | 3 | symbol |
| test | 20%（120） | 240 | 3 | symbol |

只替换谓词字母不算一条新的逻辑样本。测试集不再使用论域大小 5 和 beta 句式，因为那样的副本会和训练集共享骨架。`reports/split_leakage_report.json` 记录这项检查。

给被评测模型的说明是：

- 论域恰好包含列出的这些个体
- 只使用给出的事实和规则
- 未陈述的句子不要当成假
- `TRUE` / `FALSE` / `UNKNOWN` 按上面的蕴涵定义理解
- 输出必须恰好是 `TRUE`、`FALSE`、`UNKNOWN` 之一

## 目录

```
configs/pilot.yaml          配额、深度、句式、种子
src/negpilot/               抽象语法树、Z3 语义、模板、渲染、生成器
data/generated/             pilot.public.jsonl 与 pilot.gold.jsonl
reports/                    distribution.json 与 pilot_report.md
tests/                      语义、生成、对照对、数据审计
```

`pilot.public.jsonl` 是评测输入，不含金标签、二值标签、抽象语法树、证明轨迹和对照审计字段。这些字段在 `pilot.gold.jsonl` 里。用 `sample_id` 对齐。`binary_label` 中，TRUE 为 `1`，FALSE 为 `0`，UNKNOWN 为 `null`。

## 安装与运行

在本目录执行：

```bash
pip install -e ".[dev]"
python -m negpilot.cli validate --input data/generated/pilot.gold.jsonl --config configs/pilot.yaml
python -m negpilot.cli statistics --input data/generated/pilot.gold.jsonl --config configs/pilot.yaml
python -m pytest
```

`data/generated/` 里的文件是已发布的 Dataset v1.1。`python -m negpilot.cli generate` 会按模板重写这些文件，并用配额划分，不会保留这次的分层划分。任一命令失败时返回非零退出码。在当前配置和种子 `20261111` 下，生成结果是确定的。配额只在 `configs/pilot.yaml` 里修改。如果合法样本凑不满配额，生成会停止并写明是哪条约束造成的，不会复制已有行来填数量。

## 方法来源

逻辑形状是受 PrOntoQA 受控风格启发的原创模板，没有抄录 PrOntoQA 的题目。
