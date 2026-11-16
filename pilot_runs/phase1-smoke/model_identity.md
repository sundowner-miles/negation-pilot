# 阶段一：模型与环境

本文件记录 2026-11-14 实际调用的模型和环境。Smoke Test 只检查调用、解析和保存，不是实验 1 的成绩。每个模型 n=6，全部来自 dev。

## 请求名称与实际检查点

官方 Qwen3.5 没有名为 `Qwen3.5-4B-Instruct` 或 `Qwen3.5-8B-Instruct` 的仓库。2026-03-02 发布的稠密 post-trained 规格是 0.8B、2B、4B、9B。带 `-Instruct` 后缀的 4B/8B 在 Hugging Face 与 ModelScope 上都不存在（ModelScope 返回 404）。post-trained 权重本身就是指令模型；对应的 base 仓库另有 `-Base` 后缀。

| 请求名称 | 实际调用 | 来源 | 磁盘体积 | 架构 |
| --- | --- | ---: | --- | --- |
| Qwen3.5-4B-Instruct | `Qwen/Qwen3.5-4B` | ModelScope `master` | 9.34 GB，2 个 safetensors | `Qwen3_5ForConditionalGeneration`，32 层，hidden 2560，词表 248320 |
| Qwen3.5-8B-Instruct | `Qwen/Qwen3.5-9B` | ModelScope `master` | 19.33 GB，4 个 safetensors | 同上，hidden 4096 |

9B 是当前官方稠密系列里比 4B 更大的最近规格，不是 8B 的别名。后续表格使用实际 ID。

ModelScope 当前 tip 都是 2026-07-18 的 README 更新，权重文件的内容用本地哈希固定：

| 模型 | ModelScope tip | 父提交 | 同日查询到的 Hugging Face `sha` | `config.json` sha256 前缀 | index sha256 前缀 |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5-4B | `ed182e32` | `6658c7b1943092bb07b2a425b09e205d7bc9b212` | `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | `ddc63e1c717afa86` | `cf3f798ee02ba45f` |
| Qwen3.5-9B | `460979c3` | `e138e55eb2e1f1c59ebbf0f815bb972649fc22c6` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | `d0883072e01861ed` | `26d3539b516be613` |

Hugging Face `sha` 与 ModelScope tip 没有被证明是同一次提交。复现时以本地 `config.json` 和 `model.safetensors.index.json` 的哈希为准。许可证均为 Apache-2.0。原生上下文长度 262,144。本次提示词约 282–290 token，没有按 262,144 分配缓存。

文本权重位于 `model.language_model.*`，所以加载的是 `Qwen3_5ForConditionalGeneration`，不是 `Qwen3_5ForCausalLM`。视觉权重随检查点进入显存，输入里没有图像。

## 硬件与软件

| 项目 | 值 |
| --- | --- |
| GPU | NVIDIA vGPU-32GB，32760 MiB，compute capability 8.9 |
| 驱动 | 550.120 |
| 系统 | Linux 5.15.0-78-generic，Python 3.12.3 |
| 推理框架 | Hugging Face Transformers 5.23.0 |
| PyTorch | 2.6.0+cu124，CUDA 12.4，bfloat16 |
| 视觉依赖 | torchvision 0.21.0+cu124（VLM 类导入需要；0.18 与 torch 2.6 不兼容） |
| 模板 | jinja2 3.1.6 |
| 仓库 HEAD | `2a8dfb6b76d90dd2694602d88c62f4d5c52189cb` |
| public sha256 | `b94a75c454991e4fa6804b90df382ae6a966cf0973a4f4cbfd2fce96d2260746` |
| gold sha256 | `3135a6df0c99aefc08ce02d3423ac322fe69bc78d4d8316b7096b9a8f4e75206` |

原先的 torch 2.3.0+cu121 不能加载 Transformers 5.23 的 Qwen3.5。驱动 550 对应 CUDA 12.4，因此安装的是 cu124 的 torch 2.6.0，不是更新的 cu128 轮子。

`causal_conv1d` 和 `flash-linear-attention` 未安装。DeltaNet 使用 Transformers 自带的 PyTorch 参考实现。日志写明该实现结果正确、速度更慢。Smoke 的单条生成在预热后约 270–290 ms，参考实现没有挡住这 12 条。正式 240 条之前如果改用优化核，需要先核对贪心输出是否与本次参考实现一致。本次 Smoke 没有安装这两个包。

没有使用 vLLM 或 SGLang。Qwen3.5 的服务端配方要求这些框架的主分支或 nightly；本阶段用已发布的 Transformers 5.23.0，便于固定版本。

## 解码与提示词

两个模型相同。

- 提示词版本 `plan-6.4-v1`。系统提示词是实验说明第 6.4 节原文，用户轮是 public 记录里的 `prompt` 字段原文。
- `enable_thinking=false`。官方模板在关闭思考时，把空的 `<think>\n\n</think>\n\n` 放进提示词，生成从这段之后开始。已用本地 tokenizer 渲染核对。
- 贪心解码：`do_sample=false`。这是实验说明要求的 temperature 0。`generate()` 不另传 temperature，因为部分 Transformers 版本会拒绝与 `do_sample=false` 同时给出的 temperature。`top_p` 和 `top_k` 未使用。
- 这与厂商推荐的非思考采样（temperature 0.7，top_p 0.8，top_k 20）不同。正式比较沿用本次贪心设置，除非阶段二确认前改写并记新版本。
- `max_new_tokens=32`。重试次数 0。
- 解析：去掉首尾空白后，整段必须是 TRUE、FALSE 或 UNKNOWN。完整的 `<think>...</think>` 后面如果只剩一个标签，记为 `after_think`。其余为 `invalid_output`，不猜测。本次 12 条原始输出都是 `TRUE\n` 或 `FALSE\n`，去空白后为 `exact`。特殊符号 `<|im_end|>` 不进入解析文本。

模型进程只打开 `pilot.public.jsonl`。gold 只用于挑选 6 个 dev 编号和事后评分。挑选规则：dev 内按 `sample_id` 排序，TRUE、FALSE、UNKNOWN 各取前 2 条。编号是 `ex-0120a`、`ex-0121a`、`ex-0120b`、`ex-0121b`、`ex-0515a`、`ex-0515b`。

## 数据检查

`python -m negpilot.cli validate` 通过：1,200 条，Z3 成功率 1.000。`pytest` 26 项通过，其中 8 项覆盖解析、拒收 gold 字段和评分。没有运行 `statistics`，因为它会重写 `reports/` 下已发布的分布报告。没有运行 `generate`。Dataset v1.1 的样本、标签、AST、证明、深度、划分和对照标记没有修改。

## 尚未做

实验 1–6 都没有开始。dev 上这 6 条的对错不能外推到 test 的 240 条。优化核、提示词改写和全量运行都留在确认之后。
