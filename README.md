# Negation pilot

[中文说明](README.zh.md)

Controlled synthetic benchmark for logical negation in multi-hop deduction.
Gold labels come from Z3 over an explicitly listed finite domain. They are not
assigned by a language model, and a sentence that merely cannot be derived is
not labeled FALSE.

## Semantics

The domain of each example is closed and finite, and it is listed in the prompt.
Predicate information is incomplete: unstated atoms stay open.

For a satisfiable knowledge base `KB` and a query `q`:

- `TRUE` iff `KB` entails `q` iff `UNSAT(KB ∧ ¬q)`
- `FALSE` iff `KB` entails `¬q` iff `UNSAT(KB ∧ q)`
- `UNKNOWN` iff `SAT(KB ∧ q)` and `SAT(KB ∧ ¬q)`

If `KB` itself is unsatisfiable, the sample is rejected. Quantifiers are
grounded over the declared domain before solving. Formulas are AST nodes
(`Atom`, `Not`, `And`, `Or`, `Implies`, `ForAll`, `Exists`), not English strings.

## What the English sentences mean

These four plain-language patterns are not interchangeable.

| Plain language | Formula | Pilot frame |
| --- | --- | --- |
| Every C is not D. No C is D. | `∀x (C(x) → ¬D(x))` | For every individual, if the individual is C, then the individual is not D. |
| Every non-C is D. | `∀x (¬C(x) → D(x))` | For every individual, if the individual is not C, then the individual is D. |
| Not every C is D. Not (every C is D). | `¬∀x (C(x) → D(x))` | It is not true that for every individual, if the individual is C, then the individual is D. |
| Some C is not D. | `∃x (C(x) ∧ ¬D(x))` | There is at least one individual that is C and is not D. |

The last two are classically equivalent. The first is not equivalent to either of them.
The generated prompts use a symbol pack that keeps those four shapes distinct and
parses back to the AST: `Every A is not B.`, `Every non-A is B.`, `Not every A is B.`,
and `Some A is not B.` Predicates are single capitals and individuals are single
lowercase letters other than `x`, `y`, and `z`. Alpha and beta frames remain in the
renderer for the same formulas.

## Pilot composition

1,200 examples, 600 contrast pairs, seed `20261111`.

- 400 determinate pairs: one `TRUE` and one `FALSE`
- 200 unknown pairs: two `UNKNOWN` examples
- Class counts: 400 / 400 / 400
- One studied negation in the knowledge base. A negative query in the criticality
  contrast adds a second negation, and that query negation is shared by both members
- Reasoning depth is the number of inference-rule applications in the canonical proof.
  A directly stated fact is depth 0. Multi-hop proofs are depth 1, 3, or 5.
  An example with no canonical proof stores depth `null`
- Positions `FACT`, `RULE`, and `QUERY` are balanced at the example level

The negation-criticality contrast keeps one query, either `B(a)` or `¬B(a)`, on both
members. Positive queries make the distractor TRUE and the critical member FALSE.
Negative queries reverse those labels. Collapsed across polarity, neither condition
is tied to one gold label. A pair that asks `q` and `NOT(q)` on one knowledge base
is not generated. Every pair is checked independently with Z3. Labels are never
flipped after the fact to balance the file. Complementary labels are not enough
for a controlled contrast. `logical_pair_validity` and `experimental_control_validity`
are stored separately. Pairs that fail the contrast checks stay in the JSONL as
exploratory samples, with a reason. Of the 600 pairs, 290 are in the controlled
subset and 310 are exploratory.

Some `TRUE` examples keep the single negation on a side rule that the proof does
not use. `negation_critical` records whether deleting that negation changes the
label. Disjunctive syllogism is the critical positive case: `¬P ∨ Q` together
with `P` entails `Q`.

## Splits

Dataset v1.1 assigns splits from canonical AST skeletons. Both members of a pair,
one base case, and every alpha-renaming of the same skeleton stay in one split.
The 600 base cases form 27 unsplittable groups, so the 840 / 120 / 240 example
quotas are exact and some margins are not. Dev has no FACT examples: the only
FACT group that fits in dev is 10 UNKNOWN examples, and moving it there makes
the joint balance worse. Test covers every label, position, and depth that
exists. See `reports/dataset_v1.1_summary.md`.

| Split | Base cases | Examples | Domain size | Wording |
| --- | --- | --- | --- | --- |
| train | 70% (420) | 840 | 3 | symbol |
| dev | 10% (60) | 120 | 3 | symbol |
| test | 20% (120) | 240 | 3 | symbol |

Letter substitution is not treated as a new logical item. Domain size 5 and the
beta wording pack are not used as a test shift, because those copies would share
a skeleton with train. `reports/split_leakage_report.json` records the check.

The evaluated model is told:

- the domain contains exactly the listed individuals
- use only the supplied facts and rules
- do not treat an unstated sentence as false
- `TRUE` / `FALSE` / `UNKNOWN` have the entailment meanings above
- the output must be exactly one of `TRUE`, `FALSE`, `UNKNOWN`

## Layout

```
configs/pilot.yaml          quotas, depths, packs, seed
src/negpilot/               AST, Z3 semantics, templates, renderer, generator
src/negpilot/evalkit/       Pilot inference, parsing, scoring, experiments 1–6
data/generated/             pilot.public.jsonl and pilot.gold.jsonl
pilot_runs/                 smoke, test, and ablation predictions and reports
reports/                    dataset audits and the experiments 1–6 report
Negation_Pilot_Experiment_Plan_Dataset_v1.1.md  experiment plan
tests/                      semantics, generator, pairs, dataset audit, evalkit
```

`pilot.public.jsonl` is the evaluation input. It has no gold label, binary
label, AST, proof trace, or pair-audit fields. `pilot.gold.jsonl` has those fields. Join on
`sample_id`. `binary_label` is `1` for TRUE, `0` for FALSE, and `null` for
UNKNOWN.

## Install and run

From this directory:

```bash
pip install -e ".[dev]"
python -m negpilot.cli validate --input data/generated/pilot.gold.jsonl --config configs/pilot.yaml
python -m negpilot.cli statistics --input data/generated/pilot.gold.jsonl --config configs/pilot.yaml
python -m pytest
```

The files in `data/generated/` are the released Dataset v1.1. `python -m negpilot.cli generate` rebuilds them from the templates and uses the quota splitter, so it does not keep this stratified split. Each command exits with a non-zero status on failure. Generation is deterministic for this config and seed `20261111`. Change quotas only in `configs/pilot.yaml`. If a quota cannot be met with valid examples, generation stops and names the constraint. It does not copy rows to fill the file.

## License of the method

The logical shapes are original templates inspired by the controlled style of
PrOntoQA. No PrOntoQA items are copied.
