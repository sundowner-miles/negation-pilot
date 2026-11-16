# Phase 1 smoke test

This file is a pipeline check. The dev-slice counts below are not Experiment 1 scores.

## Decoding

```json
{
  "do_sample": false,
  "temperature": 0,
  "top_p": null,
  "top_k": null,
  "max_new_tokens": 32,
  "enable_thinking": false,
  "retry_limit": 0,
  "note": "Greedy decoding (do_sample=false) is the temperature-0 condition. generate() does not receive a temperature keyword. top_p and top_k are unused. This is not the vendor sampling recipe for non-thinking mode."
}
```

## Smoke sample ids

Rule: within dev, sort by sample_id, take the first 2 TRUE, 2 FALSE, and 2 UNKNOWN.

ex-0120a, ex-0121a, ex-0120b, ex-0121b, ex-0515a, ex-0515b

## Models

### Qwen/Qwen3.5-4B

- revision: `modelscope-master-ed182e32`
- n: 6
- correct: 4
- accuracy: 0.6666666666666666
- macro_f1: 0.5555555555555555
- invalid_output: 0

### Qwen/Qwen3.5-9B

- revision: `modelscope-master-460979c3`
- n: 6
- correct: 2
- accuracy: 0.3333333333333333
- macro_f1: 0.2222222222222222
- invalid_output: 0

## Parser self-check

- input `TRUE` -> TRUE (exact)
- input ` FALSE ` -> FALSE (exact)
- input `UNKNOWN
` -> UNKNOWN (exact)
- input `The answer is TRUE` -> invalid_output (invalid)
- input `TRUE.` -> invalid_output (invalid)
- input `<think>the query is entailed</think>
TRUE` -> TRUE (after_think)
- input `<think>TRUE</think>` -> invalid_output (invalid)
- input `` -> invalid_output (invalid)
- input `true` -> invalid_output (invalid)
