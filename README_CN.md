# SurveyMind：自动化科研综述智能体

> 面向科研主题的端到端综述构建：从模糊选题到结构化综述草稿。

[English](README.md) | [简体中文](README_CN.md)

## 项目做什么

SurveyMind 提供两种互补的工作方式：

- **Skill 流水线（智能体式）**：通过 `/survey-brainstorm`、`/research-lit`、`/paper-analysis`、`/taxonomy-build`、`/gap-identify`、`/survey-write` 等技能逐阶段推进
- **CLI 流水线（可脚本化）**：通过 `tools/surveymind_run.py` 运行可复现阶段，便于自动化、CI 和批处理

每个综述任务都会被隔离输出到：

`surveys/survey_<topic_slug>/`

并按 gate 分层：

- `gate0_scope`
- `gate1_research_lit`
- `gate2_paper_analysis`
- `gate3_taxonomy`
- `gate4_gap_analysis`
- `gate5_survey_write`

## 快速开始

### 1）安装

```bash
cp .env.example .env
make install
./install.sh
```

### 2）Skill 工作流（首次使用推荐）

```bash
claude
> /survey-brainstorm "你的模糊选题"
> /survey-pipeline "你的精炼主题"
```

### 3）CLI 工作流

```bash
python3 tools/surveymind_run.py --stage brainstorm \
  --scope-topic "你的主题描述" \
  --survey-name "your_survey_name" \
  --topic-keywords "keyword1,keyword2,keyword3"

python3 tools/surveymind_run.py --stage all \
  --survey-name "your_survey_name" \
  --topic-keywords "keyword1,keyword2,keyword3"
```

## CLI 阶段（`tools/surveymind_run.py`）

当前支持阶段：

- `brainstorm`
- `arxiv-discover`
- `corpus-extract`
- `paper-download`
- `paper-analysis`
- `batch-triage`
- `taxonomy-build`
- `gap-identify`
- `survey-write`
- `trace-init`
- `trace-sync`
- `taxonomy-alloc`
- `validate`
- `validate-and-improve`
- `all`

`--stage all` 默认执行顺序：

1. `brainstorm`
2. `arxiv-discover`（可通过 `--no-discover-arxiv` 关闭）
3. `corpus-extract`
4. `batch-triage`
5. `paper-download`
6. `paper-analysis`
7. `taxonomy-build`
8. `gap-identify`
9. `survey-write`
10. `trace-init`
11. `taxonomy-alloc`
12. `trace-sync`
13. `validate-and-improve`

## 常用命令

```bash
# 测试与质量检查
make test
make lint
make format

# arXiv 连通性冒烟测试
make check-arxiv

# 仅执行验证
python3 validation/run_validation.py --scope all --strict --retry 2
```

Tier 范围控制示例：

```bash
# 下载 Tier1+Tier2 PDF（默认行为）
python3 tools/surveymind_run.py --stage paper-download \
  --survey-name "your_survey_name" \
  --download-tier-scope tier1_tier2

# 按需分析 Tier3+Tier4
python3 tools/surveymind_run.py --stage paper-analysis \
  --survey-name "your_survey_name" \
  --analysis-tier-scope tier3_tier4 \
  --analysis-mode deep+coverage
```

## 核心目录

```text
SurveyMind/
├── skills/                 # Skill 定义与流水线
├── tools/                  # CLI 工具与编排器
├── templates/              # 模板与 domain profiles
├── validation/             # 验证规则与运行器
├── tests/                  # pytest 测试
├── surveys/                # 按 survey 隔离输出
├── .mcp.example.json       # MCP 配置模板
├── .env.example            # 环境变量模板
├── Makefile
├── README.md
└── README_CN.md
```

## MCP 与集成

SurveyMind 支持基于 MCP 的外部集成，建议从以下位置开始：

- `.mcp.example.json`
- `mcp-servers/`
- `tools/mcp_base.py`（新增 MCP server 适配器的基类）

## 故障排查

- **找不到 Skill**：重新执行 `./install.sh`
- **未检索到论文**：扩大关键词后重跑 `arxiv-discover`
- **下载超时**：先缩小范围（`--literature-scope focused`）
- **trace-init 缺少 LaTeX 文件**：传入 `--survey-tex` 或使用 `--trace-init-missing-policy skip`

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。
