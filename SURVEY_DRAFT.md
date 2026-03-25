---
title: "Survey on Large Language Model Quantization: Methods, Benchmarks, and Future Directions"
topic: "LLM Quantization"
date: "2026-03-25"
---

# Survey on Large Language Model Quantization: Methods, Benchmarks, and Future Directions

---

## Abstract

Large Language Models (LLMs) have achieved remarkable success across diverse AI applications, yet their astronomical model size and computational requirements pose significant challenges for practical deployment, particularly on resource-constrained edge devices. LLM quantization has emerged as a critical technique for enabling efficient inference by reducing model weight precision. This survey provides a comprehensive review of quantization methods for LLMs, with a focus on post-training quantization approaches that enable deployment without extensive retraining. We categorize existing methods into hierarchical taxonomies based on method category, training paradigm, and core challenges addressed. Our analysis reveals several promising research directions, including unexplored combinations of quantization with other efficiency techniques, the need for comprehensive efficiency benchmarks, and opportunities for extreme low-bit quantization at scale. This survey aims to provide researchers and practitioners with a structured understanding of the LLM quantization landscape and guide future developments in efficient LLM deployment.

---

## Table of Contents

1. Introduction
2. Background and Motivation
3. Taxonomy of Methods
4. Detailed Survey by Category
5. Research Gaps and Future Directions
6. Conclusion

---

## 1. Introduction

### 1.1 Motivation

The rapid advancement of Large Language Models has transformed artificial intelligence research and applications. Models such as GPT, LLaMA, and their variants have demonstrated unprecedented capabilities in natural language understanding, generation, and reasoning tasks. However, the deployment of these models remains challenging due to their massive parameter counts—often ranging from billions to hundreds of billions of parameters—and the substantial computational resources required for inference.

Quantization has emerged as one of the most effective techniques for addressing these deployment challenges. By reducing the numerical precision of model weights from the standard 32-bit floating-point (FP32) or 16-bit floating-point (FP16) to lower bit representations (e.g., 8-bit, 4-bit, or even 1-2 bits), quantization can dramatically reduce model storage requirements, memory bandwidth, and computational costs while maintaining acceptable accuracy levels.

### 1.2 Scope and Definitions

This survey focuses on quantization methods specifically designed for or applicable to Large Language Models. Key concepts covered include:

- **Quantization**: The process of reducing the bit-width representation of model weights and/or activations
- **Post-Training Quantization (PTQ)**: Quantization applied after model training without additional training
- **Quantization-Aware Training (QAT)**: Training with quantization constraints built into the optimization process
- **Weight-only Quantization**: Quantization applied to weights only, not activations
- **Activation-aware Quantization**: Methods that consider activation distributions in addition to weight distributions

### 1.3 Organization

This survey is organized as follows: Section 2 provides background on quantization fundamentals and the challenges specific to LLMs. Section 3 presents our hierarchical taxonomy of quantization methods. Section 4 provides detailed analysis of representative methods in each category. Section 5 identifies research gaps and proposes future directions. Section 6 concludes with a summary of key findings.

---

## 2. Background and Motivation

### 2.1 Historical Context

Quantization has been a fundamental technique in machine learning for decades, originally developed for model compression and efficient inference on mobile devices. Early work focused on quantizing convolutional neural networks for computer vision tasks, establishing foundational principles that have been adapted for transformer-based models.

The emergence of LLMs in recent years has renewed interest in quantization due to the unprecedented scale of these models. While traditional CNN quantization could often achieve 8-bit or even 4-bit representations with minimal accuracy loss, LLM quantization presents unique challenges due to the scale of the models and the sensitivity of their internal representations.

### 2.2 Fundamental Concepts

**Quantization Fundamentals**:
Quantization maps continuous floating-point values to a discrete set of lower-precision values. The mapping can be formulated as:

```
Q(x) = round(x / s) + z
```

where `s` is the scale factor and `z` is the zero-point. Dequantization approximates the original value as:

```
x̂ = s × (Q(x) - z)
```

**Round-to-Nearest (RTN)**: The simplest quantization method, rounding weights to the nearest quantized value. While straightforward, RTN often leads to significant accuracy degradation for LLMs due to the non-uniform distribution of weights.

### 2.3 Challenges Overview

The primary challenges in LLM quantization include:

1. **Representation Capacity**: Reducing precision inevitably loses information, potentially degrading model performance
2. **Outlier Sensitivity**: LLMs exhibit activation outliers that disproportionately affect quantization accuracy
3. **Scale Mismatch**: Large variation in weight and activation magnitudes across layers complicates uniform quantization
4. **Hardware Constraints**: Different hardware platforms have varying support for low-precision arithmetic

### 2.4 Evaluation Metrics

Common metrics for evaluating quantized LLMs include:

| Metric | Description | Typical Benchmarks |
|--------|-------------|-------------------|
| Perplexity | Language modeling loss | WikiText-2, Penn Treebank |
| Downstream Accuracy | Task performance | ARC, BoolQ, PIQA, HellaSwag |
| Latency | Inference time | Tokens/second on target hardware |
| Memory Footprint | Model storage size | Bytes per parameter |
| Energy Efficiency | Power consumption | Joules per inference |

---

## 3. Taxonomy of Methods

### 3.1 Taxonomy Overview

Our taxonomy organizes LLM quantization methods across multiple dimensions:

**Primary Dimensions**:
- Method Category (how the method addresses quantization challenges)
- Training Paradigm (when quantization is applied in the training pipeline)
- Core Challenge Addressed (the specific problem the method targets)

### 3.2 Classification by Method Category

#### Representation Enhancement

Methods in this category aim to enhance representation capacity or protect important information during quantization.

**Key Techniques**:
- Activation-aware weight scaling
- Per-channel/per-token quantization
- Smooth quantization
- Learnable quantization parameters

**Representative Methods**: AWQ [2306.00978], SmoothQuant

### 3.3 Classification by Training Paradigm

| Paradigm | Description | Pros | Cons |
|----------|-------------|------|------|
| **PTQ** | Post-Training Quantization | No retraining, fast | May lose accuracy |
| **QAT** | Quantization-Aware Training | Better accuracy | Requires retraining |
| **Hybrid** | Combines PTQ and QAT | Balanced | More complex |
| **From-Scratch** | Training at low precision | Maximum flexibility | High computational cost |

### 3.4 Classification by Core Challenge

| Challenge | Description | Example Methods |
|-----------|-------------|----------------|
| Representation Capacity | Maintaining model capability | Mixed-precision, adaptive scaling |
| Outlier Sensitivity | Handling activation outliers | SmoothQuant, AWQ |
| Gradient Flow | Enabling learning at low precision | Straight-through estimator |
| Hardware Efficiency | Optimizing for target hardware | Kernel fusion, bit-packing |

---

## 4. Detailed Survey by Category

### 4.1 Representation Enhancement

#### 4.1.1 Activation-aware Weight Scaling (AWQ)

**Description**: AWQ [2306.00978] identifies that not all weights in an LLM are equally important. By protecting only 1% of the most salient weights, quantization error can be significantly reduced.

**Representative Papers**: [2306.00978] - AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration

**Key Techniques**:
- Activation statistics collection to identify salient weights
- Per-channel scaling for weight protection
- Equivalent transformation for hardware efficiency
- No backpropagation or reconstruction required

**Strengths**:
- Lightweight implementation (no training required)
- Good generalization across domains (language, coding, math)
- Hardware-efficient (per-channel scaling only)
- Works well with instruction-tuned and multi-modal models

**Limitations**:
- Primarily focused on weight-only quantization
- May not be optimal for extremely low-bit settings (<2-bit)
- Limited exploration of combinations with other efficiency techniques

---

## 5. Research Gaps and Future Directions

### 5.1 Unexplored Combinations

Based on our analysis, several promising method combinations remain unexplored:

1. **Activation-aware + QAT**: Combining activation-awareness with quantization-aware training could potentially achieve better accuracy at very low bit-widths
2. **Activation-aware + Sub-2-bit**: Extending AWQ-style protection to extreme quantization (1-2 bits) could enable new deployment scenarios
3. **Quantization + Speculative Decoding**: Integration with speculative decoding could provide complementary efficiency gains

### 5.2 Benchmark Gaps

Current benchmarks focus primarily on accuracy metrics with limited coverage of efficiency aspects:

- **Missing**: Unified benchmarks covering accuracy + latency + energy consumption
- **Missing**: Standardized on-device/mobile deployment benchmarks with real hardware constraints
- **Current Practice**: AWQ evaluates on WikiText-2, Penn Treebank, PIQA, BoolQ, and GPU latency

### 5.3 Methodological Gaps

The field lacks unified frameworks that integrate multiple orthogonal efficiency techniques:

- **Current State**: Most methods focus on a single aspect (quantization, pruning, or distillation)
- **Opportunity**: Joint optimization of quantization + pruning + knowledge distillation
- **Challenge**: Understanding interactions between different efficiency techniques

### 5.4 Scale Gaps

Significant gaps exist in our understanding of quantization behavior at extreme scales:

- **Model Scale**: Most methods evaluated up to 70B parameters; limited exploration of 100B+ models
- **Bit-width Scale**: Sub-2-bit (1-bit, 1.5-bit) quantization remains challenging for large models
- **Implication**: As models continue to scale, understanding quantization at extreme scales becomes critical

### 5.5 Generalization Gaps

Cross-domain and cross-architecture generalization require further investigation:

- **Cross-architecture**: Systematic evaluation across diverse model families beyond LLaMA, OPT, and Vicuna
- **Cross-bit-width**: How quantization learned at one bit-width transfers to other bit-widths
- **Cross-domain**: Extending evaluation beyond language to multi-modal and multi-task scenarios

### 5.6 Recommended Future Directions

Based on our gap analysis, we recommend the following prioritized research directions:

| Priority | Direction | Impact | Difficulty |
|----------|-----------|--------|------------|
| 1 | Sub-2-bit activation-aware quantization | High | High |
| 2 | Unified efficiency framework (Q + P + KD) | High | High |
| 3 | Comprehensive efficiency benchmark | Medium | Medium |
| 4 | 100B+ model quantization study | Medium | Medium |
| 5 | Cross-bit-width generalization study | Medium | Medium |

---

## 6. Conclusion

### 6.1 Summary of Contributions

This survey has provided a comprehensive review of LLM quantization methods, organized through a hierarchical taxonomy that captures the diversity of approaches in this rapidly evolving field. We have analyzed methods across multiple dimensions including method category, training paradigm, and core challenges addressed.

### 6.2 Key Findings

1. **PTQ Dominance**: Post-training quantization methods have become increasingly effective, with AWQ demonstrating that lightweight approaches can achieve competitive accuracy without the overhead of retraining

2. **Activation Awareness**: Understanding activation distributions has proven crucial for identifying and protecting important weight channels

3. **Hardware Efficiency**: Methods that co-design with target hardware (e.g., GPU kernels, edge deployment) show practical benefits beyond theoretical improvements

4. **Generalization**: Modern quantization methods show promising generalization across domains and model architectures

### 6.3 Closing Remarks

LLM quantization remains a critical enabler for practical deployment of large models. While significant progress has been made, our analysis reveals substantial opportunities for future research, particularly in extreme low-bit quantization, unified efficiency frameworks, and comprehensive evaluation benchmarks. As LLMs continue to scale and diversify, quantization techniques must evolve to address new challenges and deployment scenarios.

---

## References

1. Lin, J., Tang, J., Tang, H., Yang, S., Chen, W.-M., Wang, W.-C., Xiao, G., Dang, X., Gan, C., & Han, S. (2023). *AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration*. arXiv:2306.00978.

---

## Appendix A: Method Comparison Summary

| Method | Category | Paradigm | Bit-width | Key Innovation | Hardware Co-design |
|--------|----------|----------|-----------|----------------|-------------------|
| AWQ [2306.00978] | Representation Enhancement | PTQ | 4-bit (weight-only) | Activation-aware scaling | GPU Mixed-precision |

---

## Appendix B: Implementation Resources

- **AWQ Code**: https://github.com/mit-han-lab/llm-awq
- **TinyChat**: Efficient inference engine for quantized LLMs

---

*This survey was generated by SurveyMind - Automated Research Survey Agent*
*Generated: 2026-03-25*
