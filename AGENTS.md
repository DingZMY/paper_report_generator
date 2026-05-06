# AGENTS.md — Bio Digest Project Context

## Project Identity

**Bio Digest** — 系统/合成生物学文献周报 (Weekly Systems/Synthetic Biology Literature Digest).

Fully automated pipeline: PubMed collection → DeepSeek semantic filtering → translation + findings extraction → bilingual HTML/Markdown reports → GitHub Pages deployment. Runs every Monday 00:00 UTC.

> 📖 See [README.md](README.md) for setup instructions, journal coverage, and detailed filtering criteria.

## Tech Stack

- **Language**: Python 3.12+
- **Dependencies**: `openai>=1.0.0`, `requests>=2.28.0`, `jinja2>=3.1.0`, `python-dateutil>=2.8.0`
- **LLM**: DeepSeek API (`deepseek-v4-pro`) via OpenAI SDK with custom `base_url`
- **CI/CD**: GitHub Actions → GitHub Pages from `docs/`

## Build & Run

```bash
pip install -r requirements.txt
export DEEPSEEK_API_KEY="..."     # required
export PUBMED_API_KEY="..."       # optional (3→10 req/s)

# Pipeline (run in order)
python scripts/collect_papers.py
python scripts/filter_papers.py
python scripts/translate_papers.py
python scripts/generate_report.py

# Preview
cd docs && python -m http.server 8080
```

## Architecture

```
[Action #1] 1-collect-papers.yml (Monday 00:00 UTC)
  ├── collect_papers.py    → PubMed esearch + efetch → data/papers/YYYY-WW.json
  ├── filter_papers.py     → DeepSeek semantic filter (temp=0.2) → adds llm_filter field
  └── translate_papers.py  → DeepSeek translation (temp=1.0) → adds abstract_zh + key_findings

[Action #2] 2-generate-report.yml (triggered by Action #1)
  └── generate_report.py   → Jinja2 → docs/reports/YYYY-WW.html + reports/YYYY-WW.md + docs/index.html
```

## File Map

| Path | Role |
|------|------|
| `scripts/collect_papers.py` | PubMed API client, `JOURNALS` list, MeSH/keyword matching, `_is_on_topic()` |
| `scripts/filter_papers.py` | LLM semantic filtering, 6 classification buckets |
| `scripts/deepseek_utils.py` | `make_client()`, `extract_json()` (robust JSON from LLM output) |
| `scripts/translate_papers.py` | LLM translation + 3 `key_findings` extraction |
| `scripts/generate_report.py` | `enrich_papers()`, Jinja2 rendering, `JOURNAL_COLOR_MAP`, journal `family` classification |
| `templates/report.html.j2` | Card-style bilingual HTML (variables: `nature_papers`, `cell_papers`, `science_papers`, `other_papers`) |
| `templates/report.md.j2` | Markdown table template |
| `templates/index.html.j2` | GitHub Pages home (lists all weeks) |
| `data/papers/YYYY-WW.json` | Weekly paper archive (incremental cache — never delete) |
| `docs/` | GitHub Pages output root |
| `.github/workflows/1-collect-papers.yml` | CI: collect → filter → translate → push data |
| `.github/workflows/2-generate-report.yml` | CI: generate → deploy to Pages |

## Code Conventions

- **Language**: Chinese comments and docstrings throughout
- **Naming**: `snake_case` functions, `UPPER_CASE` constants at module top
- **Error handling**: `sys.exit(1)` on critical failures; `[错误]` prefix in stderr
- **Logging**: Progress prefix pattern: `[  1/ 50] ✅ 保留：method | ...`
- **Env vars**: `DEEPSEEK_API_KEY` (required), `PUBMED_API_KEY` (optional), `DAYS_BACK` (default 7)
- **Idempotent**: All scripts skip already-processed papers (incremental)

## LLM Configuration

| Stage | Temperature | Purpose |
|-------|-------------|---------|
| Filtering (`filter_papers.py`) | 0.2 | Deterministic keep/discard decisions |
| Translation (`translate_papers.py`) | 1.0 | Natural phrasing variation |

**Filter buckets** (in `filter_papers.py`): `method`, `framework`, `mechanism_case` → usually **keep**; `application_case`, `descriptive_study`, `incremental_tooling` → usually **discard**.

**JSON extraction** (`deepseek_utils.extract_json()`): Strips `<think>` blocks → tries direct parse → strips markdown code blocks → regex fallback for `{...}`.

## Data Schema (`data/papers/YYYY-WW.json`)

```jsonc
{
  "week": "2026-W19",
  "total": 35,
  "papers": [{
    "pmid": "42069654",
    "title": "...", "journal": "Nat Commun", "authors": [...],
    "abstract": "...", "abstract_zh": "...",
    "doi": "...", "url": "...", "pub_date": "2026-May-02",
    "key_findings": ["发现1", "发现2", "发现3"],
    "llm_filter": { "decision": "keep", "bucket": "mechanism_case", "reason": "..." }
  }],
  "filtered_out_papers": [{ "pmid": "...", "bucket": "...", "reason": "..." }]
}
```

## Template Variables

`generate_report.py` enriches papers with `journal_color` (hex from `JOURNAL_COLOR_MAP`) and `family` (`nature`/`cell`/`science`/`other`). Templates receive: `week`, `date_range`, `total`, `papers`, `nature_papers`, `cell_papers`, `science_papers`, `other_papers`, `unique_journals`.

## Safety Rules

- **Never commit**: `.env` files, API keys, secrets
- **Never hardcode**: API keys (always `os.getenv()`)
- **Rate limits**: PubMed 3 req/s (10 with key); DeepSeek `REQUEST_DELAY=1.2s`; efetch batch size 50 PMIDs
- **Retry**: `MAX_RETRIES=3`, `RETRY_DELAY=5.0s` with exponential backoff
- **Don't delete** `data/papers/` — contains incremental translation cache

## Common Agent Tasks

### Adding a journal
1. Edit `JOURNALS` list in `scripts/collect_papers.py` — use PubMed `ta` abbreviation
2. Add color in `JOURNAL_COLOR_MAP` and family in `enrich_papers()` in `scripts/generate_report.py`
3. Run `python scripts/collect_papers.py` to validate

### Modifying filtering logic
- **Keyword filters**: Edit positive/negative dicts in `scripts/collect_papers.py` (see [README.md](README.md#主题筛选) for full lists)
- **Semantic criteria**: Edit the LLM prompt in `scripts/filter_papers.py`
- **Test**: Run `python scripts/filter_papers.py` against existing `data/papers/*.json`

### Template changes
1. Edit `templates/report.html.j2` or `templates/report.md.j2`
2. Run `python scripts/generate_report.py` locally
3. Preview: `cd docs && python -m http.server 8080`

### Debugging pipeline failures
1. Check GitHub Actions logs
2. Run scripts locally in order (see Build & Run above)
3. Common issues: missing `DEEPSEEK_API_KEY`, expired API key, PubMed rate limit
