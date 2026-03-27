---
name: survey-brainstorm
description: "Brainstorming and topic refinement for survey writing. Use when user says 'I want to write a survey on X', 'help me narrow my survey topic', 'what should my survey focus on', or wants to refine a fuzzy research idea into a concrete survey scope before invoking /survey-pipeline."
argument-hint: [fuzzy-research-idea]
allowed-tools: Bash(*), Read, Write, Grep, Glob, WebSearch, WebFetch, Agent
---

# Survey Topic Brainstorming & Refinement

Refine a fuzzy research idea into a concrete, focused survey scope. This is **Stage 0** of the survey pipeline — it runs BEFORE `/survey-pipeline` to ensure the survey has a well-defined scope.

## Overview

When a user says "I want to write a survey about LLM quantization" or "我想写一篇关于大模型压缩的综述", the topic is too broad. This skill helps the user and SurveyMind jointly narrow it down through structured exploration and clarification.

## Constants

- **MAX_INITIAL_RESULTS = 15** — Maximum papers to fetch during initial direction exploration
- **ARXIV_SCRIPT** — `tools/arxiv_fetch.py` relative to project root, or inline fallback
- **SURVEY_SCOPE_FILE = `SURVEY_SCOPE.md`** — Output file in project root

## Workflow

### Step 1: Parse User's Fuzzy Idea

Parse `$ARGUMENTS` to extract the raw research interest. If `$ARGUMENTS` is empty or vague (e.g., just "survey" or "写综述"), ask the user to elaborate.

Common patterns:
- `"survey on LLM quantization"` → "LLM quantization"
- `"我想写关于大模型量化的文章"` → "大模型量化"
- `"量化压缩"` → "量化压缩"

### Step 2: Initial Field Exploration (10-15 min)

Quickly scan the landscape to understand what sub-directions exist within the user's broad interest.

**Search arXiv** using `tools/arxiv_fetch.py` with multiple keyword variations:
```bash
python3 tools/arxiv_fetch.py search "LLM quantization" --max 5
python3 tools/arxiv_fetch.py search "binary neural networks LLM" --max 5
python3 tools/arxiv_fetch.py search "post-training quantization large language models" --max 5
python3 tools/arxiv_fetch.py search "ternary quantization transformer" --max 5
```

**Web search** for recent surveys and trends:
```bash
# Check if recent surveys already exist on this topic
WebSearch: "LLM quantization survey 2024 2025 site:arxiv.org OR site:paperswithcode.com"
WebSearch: "ultra-low bit quantization LLM survey"
```

**Build a quick landscape map** (3-5 min):
- What sub-areas exist within this broad topic?
- What bit-width regimes are active? (4-bit, 2-bit, 1-bit, 1.58-bit)
- What model types? (decoder-only, encoder-only, multimodal, MoE)
- What methods? (PTQ, QAT, mixed-precision, hardware co-design)
- Are there already recent surveys on this? How does this differ?

### Step 3: Clarifying Questions (Interactive Dialogue)

Present the landscape map, then ask the user to narrow down through structured questions:

**Present to user:**
```
I found several active sub-directions in this area:
1. Ultra-low bit PTQ (<2-bit): methods like GPTQ, AWQ, SpQR, QuIP
2. Ternary/Binary QAT: BitNet, TernaryLLM, Tequila, Sherry
3. Outlier handling: SmoothQuant, QuaRot, PrefixQuant
4. Hardware co-design: BitNet.cpp, T-MAC, CIM accelerators
5. KV cache quantization: Long-context efficiency
6. Multimodal quantization: VLM, vision transformers

To help define your survey scope, please clarify:
```

**Then ask 5-7 key questions:**

1. **Bit-width focus** (choose one or specify range):
   - "Ultra-low bit only" (< 2-bit, e.g., 1-bit, 1.58-bit, 2-bit)
   - "Low bit" (2-4 bit)
   - "Full range" (including 8-bit, 16-bit as baselines)

2. **Method type**:
   - "PTQ only" (post-training quantization, no retraining)
   - "QAT only" (quantization-aware training, retraining)
   - "Both PTQ and QAT" (most comprehensive)

3. **Model types**:
   - "Decoder-only LLMs only" (LLaMA, Mistral, GPT)
   - "Include vision transformers" (ViT, VLM, multimodal)
   - "Include MoE models" (Mixtral, DBRX)
   - "Any transformer-based model"

4. **Primary focus**:
   - "Algorithm innovation" (new quantization methods)
   - "Hardware-algorithm co-design" (implementation, accelerators)
   - "Benchmark and evaluation" (standardized comparison)
   - "Theory and information theory" (why quantization works)

5. **Deployment scenario**:
   - "Edge devices" (mobile, IoT, CPU)
   - "Datacenter/GPU" (serving efficiency)
   - "Any platform" (general methods)

6. **Target venue** (affects depth/breadth trade-off):
   - "TPAMI / IEEE Transactions" (comprehensive, 20-30 pages)
   - "NeurIPS/ICML/ICLR" (focused, 8-10 pages)
   - "arXiv only" (rapid, can be narrower or broader)
   - "Journal (Nature/Science)" (very comprehensive)

7. **Any hard exclusions**? (topics to deliberately NOT cover)

### Step 4: Refine Scope Based on Answers

After user responds, synthesize their answers into a concrete scope. If answers are vague, ask follow-up questions.

**Example refinement:**
- User said: "I want to survey LLM quantization"
- User answered: "Ultra-low bit (<2-bit), both PTQ and QAT, decoder-only LLMs, algorithm innovation focus, edge deployment, TPAMI"
- Refined: "Ultra-low bit post-training and quantization-aware training methods for edge deployment of decoder-only large language models: algorithms and hardware co-design"

### Step 5: Generate SURVEY_SCOPE.md

Write the refined scope to `SURVEY_SCOPE.md`:

```markdown
# Survey Scope: [Refined Topic Title]

**Original idea**: [User's original fuzzy input]
**Refined by**: SurveyMind + User
**Date**: [timestamp]

## Refined Topic
[Brief, precise description of the survey scope — 2-3 sentences]

## Target Keywords (for arXiv search)
- **Primary**: [main keywords, e.g., "quantization, LLM, large language model, ultra-low bit"]
- **Secondary**: [related keywords, e.g., "binary, ternary, 1-bit, 1.58-bit, post-training"]
- **Excluded terms**: [deliberately excluded keywords, e.g., "pruning, distillation"]

## Survey Parameters
| Parameter | Value |
|-----------|-------|
| **Bit-width focus** | Ultra-low (<2-bit) |
| **Method scope** | PTQ + QAT |
| **Model types** | Decoder-only LLMs |
| **Primary focus** | Algorithm innovation |
| **Deployment** | Edge devices |
| **Target venue** | TPAMI |
| **Scope** | Comprehensive (all sub-areas below) |

## Anticipated Sections
1. Introduction & Background
2. Taxonomies & Problem Formulation
3. Post-Training Quantization (PTQ) Methods
4. Quantization-Aware Training (QAT) Methods
5. Outlier Handling Strategies
6. Hardware Implementation & Co-design
7. Benchmark Comparison
8. Research Gaps & Future Directions
9. Conclusion

## Exclusion List
| Excluded Area | Reason |
|--------------|--------|
| General model compression (pruning, KD) | Deserve their own surveys |
| Vision transformers | Different architecture family |
| 8-bit+ quantization | Not "ultra-low" |

## Suggested arXiv Search Query
```
quantization AND (LLM OR "large language model") AND (binary OR ternary OR "1-bit" OR "1.58-bit" OR "ultra-low" OR "sub-2-bit") AND NOT pruning AND NOT distillation
```

## Next Steps
The refined scope above is ready for `/survey-pipeline`. To proceed:
```
/survey-pipeline "[refined topic]"
```
