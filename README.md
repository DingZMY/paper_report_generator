# 🧬 Bio Digest — 系统/合成生物学文献周报

全自动文献整理系统，每周从 Nature / Cell / Science 系列期刊收集系统生物学与合成生物学论文，通过 Moonshot Kimi AI 翻译摘要并提炼核心发现，自动生成中英双语 HTML + Markdown 报告并部署至 GitHub Pages。

## 功能特性

- **自动采集**：PubMed E-utilities API，覆盖 12 个顶刊及子刊
- **AI 翻译**：Moonshot Kimi 2.5，翻译摘要 + 提炼 3 条核心发现
- **双语输出**：中英对照卡片式 HTML 报告 + Markdown 存档
- **全自动运行**：GitHub Actions 每周一 06:00 UTC 自动触发，零人工干预
- **增量处理**：已翻译论文不会重复调用 API

## 快速开始

### 1. Fork 本仓库

点击右上角 **Fork**，创建你自己的副本。

### 2. 配置 Secrets

进入仓库 **Settings → Secrets and variables → Actions → New repository secret**：

| Secret 名 | 说明 | 获取地址 |
|---|---|---|
| `KIMI_API_KEY` | Moonshot Kimi API Key（必须） | [platform.moonshot.cn](https://platform.moonshot.cn) |
| `PUBMED_API_KEY` | NCBI API Key（可选，速率 3→10 req/s） | [NCBI 账号中心](https://www.ncbi.nlm.nih.gov/account/) |

### 3. 开启 GitHub Pages

进入 **Settings → Pages**，Source 选择 **Deploy from a branch**，Branch 选 `main`，目录选 `/docs`，点击 Save。

### 4. 触发首次运行

进入 **Actions → "1. Collect & Translate Papers" → Run workflow** 手动触发。

报告将在约 5-10 分钟后出现在 `https://<你的用户名>.github.io/<仓库名>/`。

---

## 文件结构

```
bio-digest/
├── .github/workflows/
│   ├── 1-collect-papers.yml   # Action #1：采集 + 翻译，每周一自动运行
│   └── 2-generate-report.yml  # Action #2：生成报告 + 部署 Pages
├── scripts/
│   ├── collect_papers.py      # PubMed E-utilities 采集客户端
│   ├── translate_papers.py    # Moonshot Kimi API 翻译客户端
│   └── generate_report.py     # Jinja2 报告渲染器
├── templates/
│   ├── report.html.j2         # 卡片式双语 HTML 模板
│   ├── report.md.j2           # Markdown 模板
│   └── index.html.j2          # GitHub Pages 首页模板
├── data/papers/               # 每周 JSON 数据存档（含翻译结果）
├── docs/                      # GitHub Pages 输出根目录
│   ├── index.html             # 自动维护的报告列表首页
│   └── reports/               # 每周 HTML 报告
├── reports/                   # Markdown 版本存档
└── requirements.txt
```

## 期刊覆盖范围

| 期刊族 | 期刊 |
|---|---|
| **Nature 系列** | Nature, Nat Biotechnol, Nat Chem Biol, Nat Methods, Nat Chem, Nat Struct Mol Biol, Nat Commun |
| **Cell 系列** | Cell, Cell Syst, Cell Chem Biol |
| **Science 系列** | Science, Sci Adv |

## 主题筛选

同时匹配以下任一条件的论文才会被收录：

- MeSH 词汇：`Synthetic Biology` 或 `Systems Biology`
- 标题/摘要关键词：`synthetic biology` 或 `systems biology`

## 运行时序

```
每周一 06:00 UTC
        │
        ▼
[Action #1] collect_papers.py → translate_papers.py → git push data/
        │
        ▼ (workflow_run 触发)
[Action #2] generate_report.py → git push docs/ reports/
        │
        ▼
GitHub Pages 自动更新
```

## 本地调试

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export KIMI_API_KEY="your_key_here"
export PUBMED_API_KEY="your_key_here"  # 可选

# 按顺序运行
python scripts/collect_papers.py
python scripts/translate_papers.py
python scripts/generate_report.py

# 预览 HTML（需要 Python 3）
cd docs && python -m http.server 8080
```

## License

MIT
