# 🧬 Bio Digest — 系统/合成生物学文献周报

全自动文献整理系统，每周从 Nature / Cell / Science 系列期刊收集系统生物学与合成生物学论文，先用 DeepSeek v4-pro 做语义精筛，再完成摘要翻译与核心发现提炼，最终自动生成中英双语 HTML + Markdown 报告并部署至 GitHub Pages。

当前版本已加入一套**反馈驱动筛选演化的基础设施**：筛选 prompt 版本化、前端收藏/归档反馈上报、反馈事件聚合快照。自动 prompt 晋升与回滚还在后续实现中。

## 功能特性

- **自动采集**：PubMed E-utilities API，覆盖 23 个顶刊及子刊
- **精准筛选**：仅保留 Research Article，排除 Review / Editorial / Letter 等；负向过滤多组学文章
- **LLM 精筛**：DeepSeek v4-pro 二次判断论文是否偏方法论，剔除纯应用型案例和无方法创新的描述性研究
- **策略版本化**：筛选 prompt 已从代码中抽离为配置文件，可记录 `policy_version` 与 `prompt_version`
- **AI 翻译**：DeepSeek v4-pro，翻译摘要 + 提炼 3 条核心发现
- **双语输出**：中英对照卡片式 HTML 报告 + Markdown 存档
- **反馈采集基础**：周报页的收藏 / 归档行为可异步上报到轻量反馈服务，并聚合为稳定 JSON 快照
- **全自动运行**：GitHub Actions 每周一 00:00 UTC 自动触发（北京时间 08:00），零人工干预
- **增量处理**：已翻译论文不会重复调用 API

## 快速开始

### 1. Fork 本仓库

点击右上角 **Fork**，创建你自己的副本。

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**：

| Secret 名 | 说明 | 获取地址 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（必须） | [platform.deepseek.com](https://platform.deepseek.com) |
| `PUBMED_API_KEY` | NCBI API Key（可选，速率 3→10 req/s） | [NCBI 账号中心](https://www.ncbi.nlm.nih.gov/account/) |

### 3. 开启 GitHub Pages

进入 **Settings → Pages**，Build and deployment 的 Source 选择 **GitHub Actions**。

### 4. 确认 Actions 写权限

进入 **Settings → Actions → General → Workflow permissions**，选择 **Read and write permissions**。

### 5. 触发首次运行

进入 **Actions → "1. Collect, Filter & Translate Papers" → Run workflow** 手动触发。

报告将在约 5-10 分钟后出现在 `https://<你的用户名>.github.io/<仓库名>/`。

---

## 文件结构

```
bio-digest/
├── .github/workflows/
│   ├── 1-collect-papers.yml   # Action #1：采集 + 筛选 + 翻译，每周一自动运行
│   └── 2-generate-report.yml  # Action #2：生成报告 + 部署 Pages
├── configs/
│   ├── filter_policy.json     # 当前激活的筛选策略与 prompt 版本
│   └── filter_prompts/
│       └── v1.txt            # 当前筛选 prompt 文本
├── scripts/
│   ├── collect_papers.py      # PubMed E-utilities 采集客户端
│   ├── filter_papers.py       # DeepSeek 语义筛选客户端（支持策略配置）
│   ├── deepseek_utils.py      # DeepSeek 共享配置与 JSON 解析
│   ├── translate_papers.py    # DeepSeek API 翻译客户端
│   ├── generate_report.py     # Jinja2 报告渲染器
│   ├── feedback_server.py     # 轻量反馈接收服务（JSONL）
│   └── aggregate_feedback.py  # 反馈事件聚合为稳定快照
├── templates/
│   ├── report.html.j2         # 卡片式双语 HTML 模板
│   ├── report.md.j2           # Markdown 模板
│   └── index.html.j2          # GitHub Pages 首页模板
├── data/papers/               # 每周 JSON 数据存档（含翻译结果）
├── data/feedback/
│   ├── events/                # 原始反馈事件（JSONL）
│   └── aggregated/            # 聚合反馈快照
├── docs/                      # GitHub Pages 输出根目录
│   ├── assets/feedback.js     # 前端反馈上报客户端
│   ├── favorites.html         # 收藏页
│   ├── index.html             # 自动维护的报告列表首页
│   └── reports/               # 每周 HTML 报告
├── reports/                   # Markdown 版本存档
└── requirements.txt
```

## 期刊覆盖范围

| 期刊族 | 期刊 |
|---|---|
| **Nature 系列** | Nature, Nat Biotechnol, Nat Chem Biol, Nat Methods, Nat Chem, Nat Commun, Nat Phys |
| **Cell 系列** | Cell, Cell Syst, Cell Chem Biol |
| **Science 系列** | Science, Sci Adv |
| **系统/计算生物学** | Mol Syst Biol, PLoS Comput Biol, PLoS Biol, Elife |
| **物理/生物物理** | Phys Rev Lett, Biophys J |
| **核酸/合成生物学** | Nucleic Acids Res, ACS Synth Biol |

## 主题筛选

### 正向匹配（满足任意一条即入选）

**MeSH 主题词**：`Synthetic Biology`、`Systems Biology`、`Biophysics`、`Biophysical Phenomena`

**系统 / 合成生物学**：`synthetic biology`、`systems biology`、`gene circuit`、`genetic circuit`、`gene regulatory network`、`biological network`、`metabolic flux`、`metabolic engineering`、`cell-free`、`optogenetics`、`CRISPR`、`genome editing`、`protein design`、`de novo protein`

**理论 / 计算 / 物理**：`mathematical model`、`computational model`、`theoretical model`、`biophysical model`、`stochastic`、`noise in gene expression`、`quantitative biology`、`theoretical biophysics`、`statistical mechanics`、`nonequilibrium`、`information theory`、`mutual information`、`entropy production`、`free energy`、`dynamical systems`、`bifurcation`、`reaction-diffusion`、`Turing pattern`、`active matter`、`living matter`、`collective behavior`、`self-organization`、`single-molecule`、`molecular motor`、`force generation`、`mechanobiology`

**方法开发**：`method development`、`new method`、`computational framework`、`algorithm`、`deep learning`、`machine learning`（包含 omics 背景下的新颖方法论文）

### 负向排除

**纯结构解析**：`cryo-EM structure`、`crystal structure`、`X-ray crystallography`、`structure determination`、`cryo-electron tomography`

**描述性 omics 普查**（不含方法开发）：`transcriptomic landscape`、`genomic landscape`、`epigenomic landscape`、`proteomic landscape`、`single-cell atlas`、`cell atlas`、`whole genome sequencing`、`whole exome`、`metagenomics survey`

**非目标临床研究**：`clinical trial`、`randomized controlled`、`case report`、`cohort study`

> **注意**：omics 方向的新颖**方法开发**文章（如新算法、新计算框架）不受以上排除影响，仍可通过正向关键词入选。

## LLM 二次筛选

在 PubMed 关键词过滤之后，系统会再调用一次 DeepSeek v4-pro，对每篇论文做语义判断：

- **优先保留**：新方法、新框架、新工具、新建模范式、新实验平台、可迁移的机制洞察
- **酌情保留**：有明显概念新意、机制新意或演化启发性的 case study
- **倾向剔除**：
        - 纯应用导向的代谢工程、产物优化、特定酶或特定通路案例
        - 仅套用现成 omics / CRISPR / 机器学习工具、但方法本身无创新的研究
        - 主要价值局限于具体疾病、菌株、细胞系或材料体系，缺乏方法论迁移性
        - 主要是局部性能改良、没有带来新方法学能力的增量工具优化

筛除结果会写回每周 JSON 数据文件，包含保留/剔除决定和简短理由，便于回查。

### 策略版本化（实验基础已实现）

- 当前筛选策略由 `configs/filter_policy.json` 指向激活 prompt 文件，而不是硬编码在 `filter_papers.py` 中
- `filter_papers.py` 会把 `prompt_version`、`policy_version`、`evaluation_snapshot_id` 写入 `llm_filter` 元数据
- 可使用 `python scripts/filter_papers.py --print-policy` 检查当前生效策略，而不调用 LLM API

这部分已经落地，后续会在此基础上继续实现自动候选 prompt 生成、离线评估和自动晋升。

### 文章类型限制

仅收录 **Research Article**（`Journal Article`），自动排除 Review、Comment、Editorial、News、Letter。

## 运行时序

```
每周一 00:00 UTC（北京时间 08:00）
        │
        ▼
[Action #1] collect_papers.py → filter_papers.py → translate_papers.py → git push data/
        │
        ▼ (workflow_run 触发)
[Action #2] generate_report.py → git push docs/ reports/
        │
        ▼
GitHub Pages 自动更新
```

## 反馈闭环基础（实验中）

当前已经实现反馈闭环的基础设施，但还**没有**接入正式的自动 prompt 晋升流程。

``` 
用户浏览周报 / 收藏页
        │
        ├─ 收藏 / 取消收藏 → docs/assets/feedback.js
        └─ 归档 / 取消归档 → docs/assets/feedback.js
                              │
                              ▼
                    scripts/feedback_server.py
                              │
                              ▼
                 data/feedback/events/*.jsonl
                              │
                              ▼
                 scripts/aggregate_feedback.py
                              │
                              ▼
             data/feedback/aggregated/latest.json
```

这一步的目标是先把用户行为沉淀为可审计、可回放的标签快照，为后续筛选 prompt 的自动评估与演化打基础。

## 本地调试

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export DEEPSEEK_API_KEY="your_key_here"
export PUBMED_API_KEY="your_key_here"  # 可选

# 按顺序运行
python scripts/collect_papers.py
python scripts/filter_papers.py
python scripts/translate_papers.py
python scripts/generate_report.py

# 查看当前筛选策略（不调用 API）
python scripts/filter_papers.py --print-policy

# 预览 HTML（需要 Python 3）
cd docs && python -m http.server 8080
```

### 本地反馈服务（实验）

```bash
# 启动反馈服务
python scripts/feedback_server.py --host 127.0.0.1 --port 8787

# 聚合反馈事件为稳定快照
python scripts/aggregate_feedback.py
```

默认情况下，本地打开周报页时，`docs/assets/feedback.js` 会优先把反馈发送到 `http://127.0.0.1:8787/api/feedback/events`。

## License

MIT
