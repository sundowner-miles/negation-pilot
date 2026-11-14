# Negation pilot verification report

## Outcome

- Generated examples: 1200
- Unique base cases: 600
- Unique pairs: 600
- TRUE / FALSE / UNKNOWN: 400 / 400 / 400
- Invalid sample count: 0
- Duplicate sample count: 0
- Duplicate logical-structure count: 0
- Z3 verification success rate: 1.000
- Validation passed: True

Labels were computed by grounding every quantifier over the listed finite domain and asking Z3. TRUE means the knowledge base plus the negated query is unsatisfiable. FALSE means the knowledge base plus the query is unsatisfiable. UNKNOWN means both are satisfiable. An unsatisfiable knowledge base is rejected. A proposition that is merely underivable is not labeled FALSE. Reasoning depth counts inference-rule applications in the canonical proof. A directly stated fact has depth 0. An example with no canonical proof stores depth null. Complementary labels alone do not make a controlled contrast.

## Class, position, scope, and depth

### Labels

| label | count |
| --- | --- |
| FALSE | 400 |
| TRUE | 400 |
| UNKNOWN | 400 |

### Negation position

| position | count |
| --- | --- |
| FACT | 400 |
| QUERY | 400 |
| RULE | 400 |

### Negation scope

| scope | count |
| --- | --- |
| ATOMIC_PREDICATE | 600 |
| PROPOSITION | 171 |
| QUANTIFIER | 111 |
| RULE_ANTECEDENT | 114 |
| RULE_CONSEQUENT | 204 |

### Reasoning depth

| depth | count |
| --- | --- |
| 0 | 150 |
| 1 | 230 |
| 3 | 210 |
| 5 | 210 |
| null | 400 |

### Label by position

| position | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| FACT | 90 | 160 | 150 |
| QUERY | 220 | 0 | 180 |
| RULE | 90 | 240 | 70 |

### Label by scope

| scope | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| ATOMIC_PREDICATE | 250 | 160 | 190 |
| PROPOSITION | 30 | 60 | 81 |
| QUANTIFIER | 30 | 0 | 81 |
| RULE_ANTECEDENT | 0 | 90 | 24 |
| RULE_CONSEQUENT | 90 | 90 | 24 |

### Label by depth

| depth | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| 0 | 150 | 0 | 0 |
| 1 | 90 | 140 | 0 |
| 3 | 80 | 130 | 0 |
| 5 | 80 | 130 | 0 |
| null | 0 | 0 | 400 |

### Position by scope

| position | ATOMIC_PREDICATE | RULE_ANTECEDENT | RULE_CONSEQUENT | QUANTIFIER | PROPOSITION |
| --- | --- | --- | --- | --- | --- |
| FACT | 400 | 0 | 0 | 0 | 0 |
| QUERY | 200 | 0 | 0 | 100 | 100 |
| RULE | 0 | 114 | 204 | 11 | 71 |

### Position by depth

| position | 0 | 1 | 3 | 5 | null |
| --- | --- | --- | --- | --- | --- |
| FACT | 90 | 60 | 50 | 50 | 150 |
| QUERY | 60 | 60 | 50 | 50 | 180 |
| RULE | 0 | 110 | 110 | 110 | 70 |

### Scope by depth

| scope | 0 | 1 | 3 | 5 | null |
| --- | --- | --- | --- | --- | --- |
| ATOMIC_PREDICATE | 90 | 120 | 100 | 100 | 190 |
| PROPOSITION | 30 | 20 | 20 | 20 | 81 |
| QUANTIFIER | 30 | 0 | 0 | 0 | 81 |
| RULE_ANTECEDENT | 0 | 30 | 30 | 30 | 24 |
| RULE_CONSEQUENT | 0 | 60 | 60 | 60 | 24 |

### Pair types

| pair_type | examples |
| --- | --- |
| counterfactual_fact | 378 |
| counterfactual_rule | 180 |
| equivalent_form | 162 |
| negation_relocation | 440 |
| query_target_contrast | 40 |

Query-polarity pairs (`q` versus `NOT(q)` under one knowledge base): 0.

### Controlled contrastive subset

Label validity, individual sample validity, pair validity, and experimental-control validity are recorded separately. A pair leaves the controlled subset when the members are not comparable, or when the inference operation and a target negation property change together without an explicit inference-type comparison. Rejected pairs stay in the dataset. Reasons are in `reports/pair_comparison.jsonl`.

- Pairs audited: 600
- Controlled pairs: 290
- Exploratory pairs: 310

| family | controlled | exploratory |
| --- | --- | --- |
| antecedent_vs_query_atomic | 0 | 90 |
| disjunction_vs_query_atomic | 0 | 70 |
| fact_ds_vs_negfact | 0 | 90 |
| quantifier_distractor_vs_query | 0 | 60 |
| rule_consequent_contrast | 90 | 0 |
| unk_fact_block | 75 | 0 |
| unk_query_atomic_target | 20 | 0 |
| unk_query_quantifier_form | 70 | 0 |
| unk_rule_antecedent | 12 | 0 |
| unk_rule_consequent | 12 | 0 |
| unk_rule_quantifier_form | 11 | 0 |

| rejection reason | pairs |
| --- | --- |
| undeclared_change:knowledge_base | 310 |
| undeclared_change:negation_function | 310 |
| undeclared_change:statement_template | 310 |
| undeclared_change:negation_embedding | 280 |
| hard_control_differs:inference_type | 220 |
| hard_control_differs:query | 220 |
| inference_and_negation_property_both_change | 220 |
| undeclared_change:inference_type | 220 |
| undeclared_change:kb_negation_count | 220 |
| undeclared_change:negation_position | 220 |
| undeclared_change:query | 220 |
| undeclared_change:query_negation_count | 220 |
| undeclared_change:query_polarity | 220 |
| hard_control_differs:proof_depth | 150 |
| undeclared_change:negation_critical | 150 |
| undeclared_change:proof_depth | 150 |
| undeclared_change:relevant_premise_count | 150 |
| undeclared_change:fact_count | 130 |
| undeclared_change:rule_count | 130 |
| negation_position_and_scope_both_change | 120 |
| undeclared_change:negation_scope | 120 |

### Negation form

| form | examples |
| --- | --- |
| atomic_literal | 440 |
| existential_counterexample | 111 |
| negated_disjunct | 160 |
| negated_universal | 171 |
| rule_antecedent | 114 |
| rule_consequent | 204 |

### Whether deleting the single negation changes the label

| label | critical false | critical true |
| --- | --- | --- |
| FALSE | 45 | 355 |
| TRUE | 195 | 205 |
| UNKNOWN | 302 | 98 |

## Splits

Base cases are assigned wholly to one split, so both members of a pair stay together. The target is 70% train, 10% dev, and 20% test of base cases. Every split uses domain size 3 and the symbol template pack. Alpha-renamed logical skeletons are kept inside one split, so a letter substitution is not a held-out test item. The 600 base cases form 27 unsplittable groups. Dev has no FACT examples and no depth 0 or depth 5. Test covers every label, position, and depth that exists. See `reports/dataset_v1.1_summary.md`.

| split | examples |
| --- | --- |
| dev | 120 |
| test | 240 |
| train | 840 |

### Split by label

| split | FALSE | TRUE | UNKNOWN |
| --- | --- | --- | --- |
| dev | 45 | 45 | 30 |
| test | 80 | 80 | 80 |
| train | 275 | 275 | 290 |

### Split by position

| split | FACT | RULE | QUERY |
| --- | --- | --- | --- |
| dev | 0 | 60 | 60 |
| test | 90 | 60 | 90 |
| train | 310 | 280 | 250 |

### Split by depth

| split | 0 | 1 | 3 | 5 | null |
| --- | --- | --- | --- | --- | --- |
| dev | 0 | 60 | 30 | 0 | 30 |
| test | 30 | 30 | 30 | 70 | 80 |
| train | 120 | 140 | 150 | 140 | 290 |

### Split by template pack

| split | symbol |
| --- | --- |
| dev | 120 |
| test | 240 |
| train | 840 |

## Not applicable cells

These position/scope combinations are not generated. The count in the data is zero.

| position | scope | reason |
| --- | --- | --- |
| FACT | RULE_ANTECEDENT | A pilot fact is quantifier-free. It has no rule antecedent for a negation to occupy. |
| FACT | RULE_CONSEQUENT | A pilot fact is quantifier-free. It has no rule consequent for a negation to occupy. |
| FACT | QUANTIFIER | A negation inside an existential witness is a quantified sentence. It is stored as a rule or a query, not as a ground fact. |
| FACT | PROPOSITION | Negation of a whole universal sentence is a quantified sentence. It is stored as a rule or a query, not as a ground fact. |
| RULE | ATOMIC_PREDICATE | Atomic-predicate negation in this pilot is a ground literal or a ground disjunction. Quantified sentences are rules, so this cell is not used. |
| QUERY | RULE_ANTECEDENT | A negated rule antecedent is a knowledge-base rule, not a pilot query. Queries are ground literals or closed quantified sentences. |
| QUERY | RULE_CONSEQUENT | A negated rule consequent is a knowledge-base rule, not a pilot query. |

These further cells are syntactically legal but empty because of the one-negation constraint or because the shortest proof cannot have the requested depth.

- **QUERY label TRUE.** With exactly one negation and no double negation, the negation would have to sit in the query. A TRUE label would then require the negation-free knowledge base to entail that negative query. The positive rules and facts in this pilot never entail a negative sentence, so the cell is empty.
- **RULE_ANTECEDENT label FALSE.** Proving a negative ground conclusion from a negated antecedent requires a second negative literal to discharge the antecedent. That would be a second negation, so the cell is empty.
- **RULE + QUANTIFIER or PROPOSITION label FALSE.** A negated universal in the knowledge base does not identify which domain element is the counterexample, so it does not by itself entail a negative ground atom. FALSE quantified items are queries that negate a stated universal.
- **FACT label FALSE at depth 3 or 5.** A negative ground fact is stated directly, so its reasoning depth is 0. It is not a one-step inference. Multi-hop FALSE examples use a negated rule consequent or a negated query.
- **QUERY + QUANTIFIER or PROPOSITION label FALSE above depth 0.** The knowledge base states the universal outright. The query is that statement's negation, so the proof is an axiom lookup of depth 0. Unused hops are not counted.
- **pair type query_polarity.** A query-polarity pair keeps one knowledge base and asks both q and NOT(q). Exactly one negation in every example forbids that pair: the positive query has zero negations when the base has none, and NOT(q) has two negations when the base already contains the target negation. Double negation is also excluded.

## How the English forms are kept apart

Every C is not D, and No C is D, are the negated rule consequent `ForAll(x, Implies(C(x), Not(D(x))))`.
Not every C is D, and Not (every C is D), are the negated universal `Not(ForAll(x, Implies(C(x), D(x))))`.
Some C is not D is the existential counterexample `Exists(x, And(C(x), Not(D(x))))`.
In classical logic the negated universal and the existential counterexample are equivalent. The negated consequent is not equivalent to either of them.
The generated text uses the symbol pack: 'Every A is not B.', 'Every non-A is B.', 'Not every A is B.', and 'Some A is not B.' each parse back to a different AST. Alpha and beta frames remain in the renderer for the same four shapes.

- `ForAll(x, Implies(C(x), Not(D(x))))`
  - Also called: Every C is not D, No C is D.
  - Alpha frame: For every individual, if the individual is C, then the individual is not D.
  - Beta frame: Whenever an individual has property C, that individual does not have property D.
- `ForAll(x, Implies(Not(C(x)), D(x)))`
  - Also called: Every non-C is D, Anyone who is not C is D.
  - Alpha frame: For every individual, if the individual is not C, then the individual is D.
  - Beta frame: Whenever an individual does not have property C, that individual has property D.
- `Not(ForAll(x, Implies(C(x), D(x))))`
  - Also called: Not every C is D, Not (every C is D).
  - Alpha frame: It is not true that for every individual, if the individual is C, then the individual is D.
  - Beta frame: It is not the case that whenever an individual has property C, that individual has property D.
- `Exists(x, And(C(x), Not(D(x))))`
  - Also called: Some C is not D, There is a C that is not D.
  - Alpha frame: There is at least one individual that is C and is not D.
  - Beta frame: At least one individual has property C and does not have property D.

## Skeletons and leakage

- Abstract template keys: 45
- Abstract template keys that occur in more than one split: 7

Exact logical structures, including the predicate letters, individuals, and the domain, are required to be unique. A duplicate exact structure fails validation.
After predicates and individuals are alpha-renamed, identical skeletons stay in one split. The count of those skeletons that cross a split is in reports/split_leakage_report.json. A coarser template key can still appear in more than one split when the instances are different skeletons.

## Verification procedure

Generation builds an AST, rejects a malformed formula, grounds quantifiers, and calls Z3. If the decision disagrees with the template's expected label, the sample is rejected. It is not relabeled and it is not copied to fill a quota. After a passing decision, the AST is rendered and parsed back. The audit then recomputes every label and checks pairs, depths, cues, and quotas.

## Limitations

- A single classical negation cannot be the critical premise of a positive atomic conclusion unless it occurs where deleting it changes the entailment. In this pilot that happens for disjunctive syllogism and for negative facts, negative consequents, and negative queries whose deletion flips FALSE or UNKNOWN. Some TRUE items keep the required single negation on an unused side rule. Those negations are marked `negation_critical: false`.
- Classic query polarity on one knowledge base, query `q` against query `NOT(q)`, is not a pair type. The negation-criticality family instead keeps one query, positive or negative, identical on both members. A negative query adds a second negation that is controlled, not manipulated.
- FALSE from a negative ground fact is fact lookup, so its reasoning depth is 0. Fact-level FALSE does not occur at depth 3 or 5.
- A negated universal does not say which individual is the exception. Those items stay UNKNOWN for a ground atom unless the query is the quantified sentence itself.
- The grammar is the closed template set above. It is not a parser for unrestricted English.
- Predicate and individual names are single letters. The alphabet is A-Z because a depth-5 chain plus a side rule needs more than A-F. Quantifier variables stay x, y, and z.
