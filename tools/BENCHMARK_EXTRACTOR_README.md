# Benchmark Extractor Tool

从研究论文中提取benchmark数据并生成对比表格的Python工具。

## 安装依赖

```bash
pip install pymupdf
```

## 使用方法

### 1. 自动提取（快速预览）

```bash
# 提取单篇论文
python3 benchmark_comparison.py auto papers/2306.00978.pdf -o output/

# 提取多篇论文
python3 benchmark_comparison.py auto papers/*.pdf -o output/

# 指定页码范围
python3 benchmark_comparison.py auto papers/paper.pdf --pages 7 8 9 -o output/
```

**注意**: 自动提取的准确性有限，因为PDF内部格式可能导致表格行列关系丢失。建议用于快速预览，最终数据请使用手动模式验证。

### 2. 手动模式（推荐）

创建手动配置文件：

```bash
# 创建模板
python3 benchmark_comparison.py manual 2306.00978 -o awq_data.json
```

编辑生成的JSON文件，填入正确的数值：

```json
{
  "paper_id": "2306.00978",
  "title": "AWQ: Activation-aware Weight Quantization",
  "models": {
    "LLaMA-2-7B": {
      "WikiText-2": "5.47",
      "WikiText-2_AWQ_4bit": "5.60"
    }
  }
}
```

### 3. 生成对比

```bash
# 从JSON文件生成对比
python3 benchmark_comparison.py compare awq_data.json ptqtp_data.json -o comparison.md

# 或使用通配符
python3 benchmark_comparison.py compare output/*.json -o comparison.md
```

### 4. 生成LaTeX表格

```bash
# 从对比markdown生成LaTeX
python3 benchmark_comparison.py latex comparison.md -o tables.tex

# 或直接从JSON生成
python3 benchmark_comparison.py latex data.json -o tables.tex
```

### 5. 完整流程

```bash
# 一键执行：提取 -> 对比 -> LaTeX
python3 benchmark_comparison.py full papers/*.pdf -o benchmark_output/
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `*.json` | 提取的原始数据 |
| `comparison.md` | Markdown格式的对比表格 |
| `tables.tex` | LaTeX格式的对比表格 |

## 工具限制

1. **PDF表格复杂性**: PDF内部文本表示与视觉布局不同，表格行列关系难以完美恢复
2. **数字提取**: 可能提取到无关的数字（如页码、引用年份等）
3. **建议**: 始终验证自动提取的结果，使用手动模式进行修正

## 示例：AWQ vs PTQTP 对比

```bash
# 1. 提取数据
python3 benchmark_comparison.py auto papers/2306.00978.pdf papers/2509.16989.pdf -o /tmp/bench

# 2. 基于模板创建手动数据文件
python3 benchmark_comparison.py manual 2306.00978 -o /tmp/bench/awq_manual.json
python3 benchmark_comparison.py manual 2509.16989 -o /tmp/bench/ptqtp_manual.json

# 3. 编辑手动文件后，生成对比
python3 benchmark_comparison.py compare /tmp/bench/*_manual.json -o comparison.md
```

## 生成表格示例

### Markdown

```markdown
## WikiText-2 Perplexity (↓)

| Model | AWQ | PTQTP |
|-------|-----|-------|
| LLaMA-2-7B | 5.60 | 6.30 |
| LLaMA-3-8B | - | 8.53 |
```

### LaTeX

```latex
\begin{table}[t]
\centering
\caption{WikiText-2 Perplexity (↓) Comparison}
\label{tab:wikitext}
\begin{tabular}{lcc}
\toprule
\textbf{Model} & \textit{AWQ} & \textit{PTQTP} \\
\midrule
\texttt{LLaMA-2-7B} & 5.60 & 6.30 \\
\texttt{LLaMA-3-8B} & - & 8.53 \\
\bottomrule
\end{tabular}
\end{table}
```
