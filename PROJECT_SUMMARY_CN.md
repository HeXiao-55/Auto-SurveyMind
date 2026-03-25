# ARIS 项目总结

## 项目概述

ARIS (Auto-claude-code-research-in-sleep) 是一个基于 Claude Code 的自主机器学习科研工作流系统，实现"让 Claude Code 在你睡觉时做科研"的目标。

**核心机制**：跨模型协作——Claude Code 负责执行（读文件、写代码、跑实验），外部 LLM（GPT-5.4 通过 Codex MCP）负责评审。两个模型互不评自己的输出，形成真正的对抗式反馈循环。

---

## 项目结构

```
/Users/river/Desktop/Auto-claude-code-research-in-sleep/
├── skills/                  # 核心 Skills 目录（45+ 个 skill）
├── skills-codex/           # Codex CLI 原生版本（43个skill）
├── skills-codex-claude-review/   # Codex + Claude 审稿变体
├── skills-codex-gemini-review/    # Codex + Gemini 审稿变体
├── mcp-servers/            # MCP 服务器实现
├── templates/              # 输入模板目录
├── tools/                  # 工具脚本
├── docs/                   # 文档目录
└── assets/                 # 项目资源图片
```

---

## 四大核心工作流

### 工作流 1：Idea 发现与方案精炼

**功能**：文献调研 → 头脑风暴 8-12 个 idea → 查新验证 → GPU pilot 实验 → 排名报告

**命令行**：
```bash
/research-pipeline "你的研究方向"                    # 全流程
/idea-discovery "离散扩散语言模型的 factorized gap" # 工作流 1
/research-lit "topic"                               # 文献调研
/idea-creator "DLLMs post training"                # 头脑风暴
/novelty-check "top idea"                           # 查新验证
/research-review "top idea"                         # 批判性评审
/research-refine "top idea"                         # 精炼方案
/experiment-plan                                    # 实验规划
```

**参数示例**：
```bash
/research-lit "topic" — sources: zotero, web        # 只搜部分源
/research-lit "topic" — arxiv download: true       # 下载最相关 PDF
/idea-discovery "方向" — pilot budget: 4h         # 调整 pilot 预算
```

---

### 工作流 1.5：实验桥接

**功能**：读取实验计划 → 实现代码 → GPT-5.4 代码审查 → Sanity check → 部署到 GPU → 收集结果

**命令行**：
```bash
/experiment-bridge                         # 读取 refine-logs/EXPERIMENT_PLAN.md
/experiment-bridge "my_plan.md"           # 指定实验计划文件
/run-experiment                            # 部署实验到 GPU
/monitor-experiment                        # 监控实验进度、收集结果
```

**参数示例**：
```bash
/experiment-bridge — code review: false   # 跳过 GPT-5.4 代码审查
/experiment-bridge — wandb: true           # 启用 W&B 日志
/experiment-bridge — base repo: https://github.com/org/project  # 使用基础代码库
```

---

### 工作流 2：自动审稿循环

**功能**：审稿 → 定位弱点 → 建议实验 → Claude Code 自动修复 → 再审（最多 4 轮）。睡一觉醒来看结果。

**命令行**：
```bash
/auto-review-loop "你的论文主题"           # 启动自动审稿循环
/research-review "top idea"               # 单轮深度评审
/novelty-check "idea"                      # 验证新颖性
/analyze-results                            # 分析实验结果
```

**参数示例**：
```bash
/auto-review-loop — human checkpoint: true  # 每轮 review 后暂停
/research-pipeline "方向" — human checkpoint: true  # 全流程每步暂停
```

---

### 工作流 3：论文写作

**功能**：研究叙事 → 大纲 → 图表 → LaTeX → PDF → 自动审稿改进

**命令行**：
```bash
/paper-writing "NARRATIVE_REPORT.md"       # 全流程论文写作
/paper-plan                                 # 生成 claims-evidence 矩阵 + 大纲
/paper-figure                               # 生成出版级图表
/paper-write                                # 逐节 LaTeX 生成
/paper-compile                              # 编译 LaTeX 为 PDF
/auto-paper-improvement-loop                # 2轮内容审稿 + 格式检查
```

**论文完成后的产出**：
```bash
/paper-slides "paper/"                     # 生成演讲幻灯片（Beamer PDF + PPTX）
/paper-poster "paper/"                     # 生成会议海报（A0/A1 PDF）
```

**参数示例**：
```bash
/paper-write — target venue: NeurIPS       # 指定目标会议
/paper-write — illustration: gemini        # AI 生成架构图
/paper-writing "报告.md" — compact: true   # 生成精简摘要文件
```

---

### 全流程管道

**命令行**：
```bash
/research-pipeline "你的研究方向"                    # 工作流 1 → 1.5 → 2 → 3
/research-pipeline "改进方法 X" — ref paper: https://arxiv.org/abs/2406.04329
/research-pipeline "改进方法 X" — base repo: https://github.com/org/project
```

---

## MCP 服务器

| 服务器 | 路径 | 功能 |
|--------|------|------|
| claude-review | `mcp-servers/claude-review/` | Claude 审稿接口（供 Codex 工作流调用 Claude） |
| feishu-bridge | `mcp-servers/feishu-bridge/` | 飞书消息推送与交互（端口 5000） |
| gemini-review | `mcp-servers/gemini-review/` | Gemini 审稿接口 |
| llm-chat | `mcp-servers/llm-chat/` | 通用 OpenAI 兼容 API 审稿 |
| minimax-chat | `mcp-servers/minimax-chat/` | MiniMax API 审稿 |

---

## 工具脚本

### watchdog.py — GPU/训练监控守护进程

**功能**：监控所有注册的 GPU 训练和下载任务，支持 screen/tmux 会话监控、GPU 空闲检测、下载速度异常检测。

**命令行**：
```bash
# 注册训练任务
python3 watchdog.py --register '{"name":"exp01","type":"training","session":"exp01","session_type":"screen","gpus":[0,1,2,3]}'

# 查看状态
python3 watchdog.py --status
```

---

## 安装与配置

### 安装 Skills

```bash
# 克隆项目
git clone https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep.git
cd Auto-claude-code-research-in-sleep

# 安装全部 skills（全局可用）
cp -r skills/* ~/.claude/skills/

# 或只安装特定 skill
cp -r skills/auto-review-loop ~/.claude/skills/
```

### 配置 Codex MCP（review 类 skill 需要）

```bash
npm install -g @openai/codex
codex setup                    # 提示选模型时选 gpt-5.4
claude mcp add codex -s user -- codex mcp-server
```

### 安装 LaTeX 环境（仅论文写作需要）

```bash
# macOS
brew install --cask mactex
brew install poppler          # 提供 pdfinfo

# Ubuntu/Debian
sudo apt install texlive-full latexmk poppler-utils

# 验证
latexmk --version && pdfinfo -v
```

### 过夜自动运行配置

在 `.claude/settings.local.json` 中添加：
```json
{
  "permissions": {
    "allow": [
      "mcp__codex__codex",
      "mcp__codex__codex-reply",
      "Write",
      "Edit",
      "Skill(auto-review-loop)"
    ]
  }
}
```

---

## 输入模板

| 模板文件 | 用途 |
|----------|------|
| `RESEARCH_BRIEF_TEMPLATE.md` | 工作流 1 输入 |
| `EXPERIMENT_PLAN_TEMPLATE.md` | 工作流 1.5 输入 |
| `NARRATIVE_REPORT_TEMPLATE.md` | 工作流 3 输入 |
| `PAPER_PLAN_TEMPLATE.md` | 工作流 3 大纲 |
| `IDEA_CANDIDATES_TEMPLATE.md` | compact 模式模板 |
| `EXPERIMENT_LOG_TEMPLATE.md` | 实验日志 |
| `FINDINGS_TEMPLATE.md` | 发现记录 |

---

## 关键特性

| 特性 | 说明 |
|------|------|
| **31+ 可组合 skill** | 自由混搭或串联成完整流水线 |
| **跨模型协作** | Claude Code 执行，GPT-5.4 审稿，对抗式反馈 |
| **Human-in-the-loop** | 关键决策点可配置检查点 |
| **多 IDE 适配** | 支持 Claude Code、Codex CLI、Cursor、Trae、Antigravity |
| **灵活模型选择** | 支持任意 OpenAI 兼容 API |
| **Zotero + Obsidian 集成** | 文献管理无缝衔接 |
| **飞书通知** | 三种模式：关闭/推送/交互 |
| **W&B 集成** | 实验跟踪和可视化 |
| **DBLP/CrossRef 引用** | 反幻觉真实 BibTeX |

---

## 社区已验证成果

| 论文 | 评分 | 会议 | 技术栈 |
|------|:---:|------|--------|
| CS 论文 | **8/10** | CS 会议 | Claude Code + GPT-5.4 |
| AAAI 论文 | **7/10** | AAAI 2026 | 纯 Codex CLI |

---

## 常用参数汇总

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `AUTO_PROCEED` | `true` | 自动带着最优方案继续 |
| `human checkpoint` | `false` | 每轮 review 后暂停 |
| `sources` | `all` | 搜索源：`zotero`、`obsidian`、`local`、`web`、`all` |
| `arxiv download` | `false` | 下载最相关 arXiv PDF |
| `DBLP_BIBTEX` | `true` | 从 DBLP/CrossRef 获取真实 BibTeX |
| `code review` | `true` | GPT-5.4 部署前审查代码 |
| `wandb` | `false` | 自动加 W&B 日志 |
| `venue` | `ICLR` | 目标会议 |
| `compact` | `false` | 生成精简摘要文件 |
| `illustration` | `gemini` | AI 作图：`gemini`/`mermaid`/`false` |
