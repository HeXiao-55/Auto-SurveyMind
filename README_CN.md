# SurveyMind: 自动化科研综述工具

> 一个自主运行的AI智能体框架，用于在任意科研子领域进行全面的文献综述。从课题定义到结构化综述报告——全程自动化。

## 概述

SurveyMind 自动化了撰写科研综述论文的整个流程：

- **输入**：一个科研子领域（占位符：`{TOPIC}`）
- **输出**：包含分类体系、基准对比分析和研究空白识别的结构化综述报告
- **流程**：课题提炼 → 多源文献检索 → 论文分类 → 分类体系构建 → 空白分析 → 综述撰写

CLI 编排器默认在 scope 确认后先执行广覆盖检索阶段：

- `arxiv-discover`：根据 `SURVEY_SCOPE.md` + `--topic-keywords` 广泛检索 arXiv，输出 `gate1_research_lit/arxiv_results.json`
- `corpus-extract`：在上述 `arxiv_results.json` 基础上做相关性分层和报告生成

`stage all` 默认顺序：

- `brainstorm` -> `arxiv-discover` -> `corpus-extract` -> `batch-triage`
- `paper-download` -> `paper-analysis` -> `trace-init` -> `taxonomy-alloc` -> `trace-sync` -> `validate`

默认输出目录采用按 survey 隔离、按 gate 分层：

- `surveys/survey_<topic_slug>/gate0_scope`
- `surveys/survey_<topic_slug>/gate1_research_lit`
- `surveys/survey_<topic_slug>/gate2_paper_analysis`
- `surveys/survey_<topic_slug>/gate3_taxonomy`
- `surveys/survey_<topic_slug>/gate4_gap_analysis`
- `surveys/survey_<topic_slug>/gate5_survey_write`

系统自主运行——课题提炼、文献检索、结构化分类的论文分析、证据提取、分类体系构建、空白识别和学术写作全部自动化。

## 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SurveyMind 工作流                              │
│                                                                       │
│  /survey-pipeline "{TOPIC}"                                      │
│        │                                                              │
│        ▼                                                              │
│  ┌────────────────┐                                                   │
│  │ Stage 0        │                                                   │
│  │ /survey-brainstorm │ ──▶ SURVEY_SCOPE.md                         │
│  └───────┬────────┘                                                   │
│          │                                                            │
│          ▼                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  流水线（默认自动继续）                                           │ │
│  │                                                                │ │
│  │  Stage 1 ──▶ Stage 2 ──▶ Stage 3 ──▶ Stage 4 ──▶ Stage 5    │ │
│  │  文献检索   论文分析   分类体系   空白识别     综述撰写         │ │
│  │  优先级驱动   构建       Gap分析     生成           │          │ │
│  │    │          │           │           │            │          │ │
│  │    ▼          ▼           ▼           ▼            ▼          │ │
│  │  paper_   paper_     taxonomy   gap_        SURVEY_          │ │
│  │  list    analysis/   .md     analysis.md  DRAFT.md          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          │                   │                    │                  │
│          ▼                   ▼                    ▼                  │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    结构化综述报告                              │     │
│  │  • 按方法论和应用构建的层次化分类体系                         │     │
│  │  • 基准测试对比表（精度、效率）                              │     │
│  │  • 研究空白与未来方向                                        │     │
│  │  • 证据绑定（每个结论均引用原文）                            │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

## 核心功能

| 功能 | 描述 |
|------|------|
| **自动继续模式** | 首次确认后，流水线自主运行全程——无需反复确认 |
| **课题提炼** | `/survey-brainstorm` 将模糊主题联合精炼为聚焦的综述范围 |
| **多源检索** | ArXiv、DBLP、Semantic Scholar、Web——自动查找相关论文 |
| **结构化论文分析** | 多维度分类从收集的论文语料库中动态提取——分类维度不预先固定，而是从文献本身涌现 |
| **证据绑定** | 每个分类结论均引用原文——完全可审计 |
| **自动分类体系** | 从分类后的论文构建层次化分类体系（方法→子方法→具体技术） |
| **空白分析** | 识别未探索的组合、未充分研究的方向、基准测试缺口 |
| **基准综合** | 从各论文中提取并标准化数据，形成统一对比表 |
| **综述生成** | 生成符合学术规范的综述文档 |

## 分类体系的涌现机制

分类体系**不是预定义的**——而是从收集的论文语料库中归纳得出的。第二阶段（论文分析）从每篇论文中动态提取分类维度，包括：

- **方法维度**：该论文属于哪种技术路线（如：旋转、重构、剪枝、蒸馏）？
- **问题维度**：它解决了什么问题（如：离群值处理、梯度流、表示崩溃）？
- **评测维度**：它汇报了哪些指标和基准？
- **范围维度**：涵盖了哪些模型类型、位宽和训练范式？

第三阶段（`/taxonomy-build`）随后将所有论文聚类为**层次化结构**——分组完全从所发现的论文中导出，而非来自任何固定模式。因此，生成的分类体系对每个综述主题和语料库都是独特的。

## 工作流

### 全流程综述

```bash
/survey-pipeline "{TOPIC}"
```

单命令：头脑风暴 → 检索 → 分析 → 分类 → 构建分类体系 → 识别空白 → 撰写综述。

**自动继续**：默认情况下流水线自动通过所有关卡（`AUTO_PROCEED=true`）。设为 `false` 可在每个关卡暂停等待手动确认。

**状态持久化**：每个关卡完成后自动保存状态到 `WORKLOG.md` 和 `findings.md`；新 session 启动时 agent 自动读取这些文件恢复上下文，无需手动操作。

### 分步骤使用

| 步骤 | 命令 | 功能 |
|------|------|------|
| 0 | `/survey-brainstorm "宽泛主题"` | 将模糊主题精炼为聚焦范围（仅当主题模糊时） |
| 1 | `/research-lit "子领域"` | 多源文献检索 |
| 1.5 | `python3 tools/surveymind_run.py --stage paper-download` | 按优先级批量下载 PDF（默认 Tier1+Tier2），为深度分析做准备 |
| 2 | `/paper-analysis "子领域"` | 基于优先级（默认Tier1+Tier2）执行深度分析并输出覆盖报告 |
| 3 | `/taxonomy-build "子领域"` | 从分类结果构建层次化分类体系 |
| 4 | `/gap-identify "子领域"` | 识别研究空白和未来方向 |
| 5 | `/survey-write "子领域"` | 生成结构化综述文档 |

按需扩展 Tier3/Tier4（预留接口）：

```bash
# 按需下载 Tier3/Tier4 的 PDF
python3 tools/surveymind_run.py --stage paper-download \
  --survey-name "{SURVEY_NAME}" \
  --download-tier-scope tier3_tier4

# 按需对 Tier3/Tier4 做深度分析
python3 tools/surveymind_run.py --stage paper-analysis \
  --survey-name "{SURVEY_NAME}" \
  --analysis-tier-scope tier3_tier4 \
  --analysis-mode deep+coverage
```

### CLI 阶段说明（surveymind_run.py）

`tools/surveymind_run.py` 当前提供 10 个可执行阶段：

| 阶段 | 调用工具 | 说明 |
|------|----------|------|
| `brainstorm` | 进程内 | 根据 `--scope-topic` + `--topic-keywords` 生成 `SURVEY_SCOPE.md` |
| `arxiv-discover` | `arxiv_discover.py` | 基于 scope 的广覆盖 arXiv 检索，输出 gate1 `arxiv_results.json` |
| `corpus-extract` | `arxiv_json_extractor.py` | 解析 `arxiv_results.json` 并生成分层语料报告 |
| `batch-triage` | `batch_paper_triage.py` | 对 `arxiv_results.json` 全量进行多字段分诊 |
| `paper-download` | 进程内 + `arxiv_fetch.py` | 按优先级确保本地 PDF 可用（默认 Tier1+Tier2） |
| `paper-analysis` | 进程内 + `paper_triage.py` 回退 | 按优先级执行深度分析并生成覆盖率报告 |
| `trace-init` | `survey_trace_init.py` | 解析 LaTeX 并创建 `survey_trace/` 目录树 |
| `taxonomy-alloc` | `taxonomy_alloc.py` | 基于 `taxonomy.md` 回填分析字段与分配映射 |
| `trace-sync` | `survey_trace_sync.py` | 同步分析结果到 `survey_trace/` 子章节记录 |
| `validate` | `validation/run_validation.py` | 引用、基准与 guardrails 校验 |

CLI 常用示例：

```bash
# 全流程
python3 tools/surveymind_run.py --stage all \
  --survey-name "{SURVEY_NAME}" \
  --topic-keywords "{KEYWORDS}"

# 仅下载优先级论文 PDF
python3 tools/surveymind_run.py --stage paper-download \
  --survey-name "{SURVEY_NAME}" \
  --download-tier-scope tier1_tier2

# 仅执行 taxonomy 驱动分配
python3 tools/surveymind_run.py --stage taxonomy-alloc \
  --survey-name "{SURVEY_NAME}" \
  --verbose
```

### 验证关卡（建议在撰写最终稿前运行）

```bash
python3 validation/run_validation.py --scope all --strict --retry 2
```

这将检查引用完整性、基准数据合理性，以及路径级别的保护guardrails。

## 输出示例

工作流产出结构化综述报告：

```markdown
# 综述：{TOPIC}

## 1. 引言
## 2. 背景

## 3. 分类体系

### 3.1 量化方法
#### 3.1.1 训练后量化（PTQ）
- **1-bit**：QAT-LLM、BiLLM、...
- **1.58-bit**：TinyChat、...
#### 3.1.2 量化感知训练（QAT）
- ...

### 3.2 剪枝方法
### 3.3 知识蒸馏

## 4. 基准对比

| 方法 | 类型 | WikiText-2 PPL | ARC | 延迟 | 内存 |
|------|------|----------------|-----|------|------|
| QAT-LLM 1-bit | QAT | 12.3 | 45.2 | 1.0x | 0.9GB |
| TinyChat 1.58b | PTQ | 13.1 | 43.8 | 0.9x | 0.8GB |

## 5. 研究空白

1. **未探索组合**：亚2比特量化 + 投机解码
2. **基准缺口**：缺乏涵盖精度 + 效率 + 能耗的统一基准
3. **方法论缺口**：极端量化下离群值的分析有限
```

## 快速开始

```bash
# 1. 克隆并安装（或本地复制）
git clone <REPO_URL>  # 或：cp -r /path/to/SurveyMind .
cd SurveyMind
./install.sh

# 2. 配置 API keys（可选）
export ARXIV_API_KEY=your_key    # 增强检索
export GEMINI_API_KEY=your_key   # 论文插图

# 3. 运行综述
claude
> /survey-pipeline "大语言模型高效推理"

# 占位符写法
> /survey-pipeline "{TOPIC}"

# 断点续行：新 session 启动时 agent 自动读取 WORKLOG.md + findings.md
# 恢复流水线状态——无需手动操作
```

## 配置参数

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--topic` | 必填 | 要综述的科研子领域 |
| `--depth` | `standard` | `quick`（20篇）/ `standard`（50篇）/ `comprehensive`（100+篇） |
| `--sources` | `all` | `arxiv`、`semantic`、`dblp`、`web`、`zotero`、`local` 或 `all` |
| `--output` | `survey.md` | 输出文件路径 |

**流水线常量**（位于 `skills/survey-pipeline/SKILL.md`）：

| 常量 | 默认值 | 描述 |
|------|--------|------|
| `AUTO_PROCEED` | `true` | 自动通过所有关卡，无需用户确认 |
| `MAX_PAPERS` | `20` | 最多分析的论文数 |
| `MIN_PAPERS_FOR_TAXONOMY` | `5` | 构建分类体系所需的最少论文数 |

## 项目结构

```
SurveyMind/
├── skills/                          # 模块化 skill 组件
│   ├── survey-pipeline/            # 端到端编排器
│   ├── survey-brainstorm/          # 课题提炼与范围定义
│   ├── research-lit/              # 文献检索
│   ├── paper-analysis/            # 论文深度分析与覆盖校验（优先级驱动）
│   ├── taxonomy-build/            # 分类体系构建
│   ├── gap-identify/              # 研究空白分析
│   ├── survey-write/              # 综述生成
│   └── [其他ML科研技能]           # 可复用组件
├── templates/                       # 输出模板
├── tools/                          # 工具脚本
├── validation/                     # 验证规则（guardrails）
├── surveys/                        # 按课题隔离的输出目录
│   └── survey_<topic_slug>/
│       ├── gate0_scope/
│       ├── gate1_research_lit/
│       ├── gate2_paper_analysis/
│       ├── gate3_taxonomy/
│       ├── gate4_gap_analysis/
│       ├── gate5_survey_write/
│       ├── survey_trace/
│       └── validation/
├── CLAUDE.md                       # Session恢复与流水线状态
└── README.md
```



---

## 故障排除

### SSL 证书错误 (macOS)

如果从 arXiv 下载时遇到 SSL 证书错误：

```bash
# 方法 1: 通过 Homebrew 安装证书
brew install curl-ca-bundle

# 方法 2: 运行 Python 证书安装程序
/Applications/Python\ 3.x/Install\ Certificates.command

# 方法 3: 安装 certifi 包
pip install certifi
/Applications/Python\ 3.x/Install\ Certificates.command
```

### arXiv 下载超时

如果下载速度慢或超时：

1. 检查网络连接
2. 尝试使用代理或 VPN
3. 使用 `--depth quick` 模式减少论文数量
4. 使用本地论文：`--sources local`

### 未找到论文

如果搜索返回空结果：

1. 尝试扩大搜索主题（例如：用"机器学习"代替"具体技术"）
2. 检查拼写和关键词变体
3. 确保已设置 API keys
4. 尝试不同来源：`--sources all`

### 找不到 Skill

如果 `/survey-pipeline` 命令无法识别：

```bash
# 重新运行安装
cd SurveyMind
./install.sh

# 验证 skills 已安装
ls ~/.claude/skills/
```

### 分析结果为空

如果论文分析产生空结果：

1. 验证 PDF 下载成功
2. 检查 `surveys/survey_<topic_slug>/gate1_research_lit/paper_list.json` 是否存在
3. 确保论文格式可读（未加密）

### 内存问题

处理大型综述（100+ 论文）时：

1. 使用 `--depth standard` 而非 `--depth comprehensive`
2. 分批处理论文
3. 运行之间清除中间文件

## 引用

如果这个工具对你的研究有帮助，请引用：

```bibtex
@software{surveymind,
  title = {SurveyMind: 自动化科研综述工具},
  author = {[作者]},
  year = {2026},
  url = {[仓库地址]}
}
```

## 许可证

MIT 许可证——详见 [LICENSE](LICENSE)。
