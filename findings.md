# Research Findings

> **格式规范**：每个条目以 `## [YYYY-MM-DD] {Topic}` 开头，后跟 3–5 个固定字段。
> 所有字段可选，但出现的字段必须使用此格式，否则 grep/解析工具无法识别。

---

## Research Findings

### [YYYY-MM-DD] Topic

- **Finding**:  一句话描述（必须用 "Finding" 字段）
- **Evidence**: 来源，支持的指标或引用（paper_id、URL、wandb run 等）
- **Confidence**: high / medium / low
- **Context**: 什么情况下成立，什么情况下不成立（可选）
- **Tags**: comma-separated 标签，便于 grep（可选）

---

### [YYYY-MM-DD] Example: AWQ outperforms naive quantization on LLaMA-7B

- **Finding**: Activation-aware weight quantization (AWQ) preserves perplexity within 0.3 of FP16 at W4 precision, while naive per-tensor quantization degrades by 2.1
- **Evidence**: AWQ paper (arxiv:2306.00978), Table 3; downstream task accuracy on PIQA: 71.2 (AWQ) vs 69.1 (naive)
- **Confidence**: high
- **Context**: Validated on LLaMA-7B and Vicuna-7B; LLaMA-2-13B shows similar trend but with smaller gap (0.1 perplexity difference)
- **Tags**: quantization, AWQ, LLM, benchmark

### [YYYY-MM-DD] Example: Ternary (1.58-bit) training is unstable beyond 13B parameters

- **Finding**: TernaryLLM training collapses after ~3k steps on models >13B parameters, requiring careful gradient clipping and warmup
- **Evidence**: TernaryLLM paper (arxiv:2312.00135); wandb run `ternary-13b/run42`
- **Confidence**: medium
- **Context**: Stable on 7B and 2.7B models with standard hyperparams; 13B+ requires lower learning rate (1e-5 vs 2e-5) and 500-step linear warmup
- **Tags**: ternary, 1.58-bit, training, stability

---

## Engineering Findings

### [YYYY-MM-DD] Topic

- **Problem**: 问题描述
- **Root Cause**: 根本原因
- **Fix Applied**: 应用的修复方案

---

### [YYYY-MM-DD] Example: DDP + wandb.log() causes hanging on multi-GPU

- **Problem**: Training hangs indefinitely on 4-GPU setup after epoch 1
- **Root Cause**: `wandb.log()` called inside DDP forward/backward pass synchronizes across all ranks, causing deadlock
- **Fix Applied**: Wrapped all logging in `if dist.get_rank() == 0:` guard; moved metric aggregation to post-step hook
- **Tags**: DDP, wandb, multi-GPU, debugging

### [YYYY-MM-DD] Example: OOM with gradient accumulation on 24GB GPUs

- **Problem**: OOM on batch_size=32 with 4x accumulation steps even though each micro-batch should fit in 24GB
- **Root Cause**: Gradient checkpointing was disabled in our fork; each full backward pass held full activations
- **Fix Applied**: Enabled `model.gradient_checkpointing_enable()`; batch_size=32 now fits with 4x accumulation and 24GB budget
- **Tags**: memory, OOM, gradient-checkpointing, multi-GPU
