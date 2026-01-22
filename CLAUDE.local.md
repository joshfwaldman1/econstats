# EconStats Project Memory

## Critical Rules (User-Specified)
- **DO NOT HALLUCINATE DATES** - Never make up or guess date ranges
- **PAYROLLS = CHANGES NOT LEVELS** - When using payroll data, focus on month-over-month or year-over-year changes, not absolute employment levels

## LLM Integration Patterns
- **LLMs hallucinate series IDs** - Never have LLMs generate FRED series IDs directly
- **Use topic discovery instead** - Have LLMs suggest dimensions/topics, then use FRED API to find valid series
- **Validate all series** - Use `validate_series_relevance()` to filter irrelevant/overly broad series
- **Claude API auth issues** - May get 401 errors; Gemini works as fallback in ensemble

## Architecture
- **RAG Catalog**: 94 curated FRED series in `agents/series_rag.py` with semantic search
- **Pre-computed Plans**: ~300 query-to-series mappings in `query_plans.json`
- **Hybrid Approach**: Combine RAG + FRED API search for best coverage
- **Ensemble LLMs**: Claude + Gemini + GPT for improved query understanding

## Query Processing Flow
1. **Demographic extraction** - Extract demographic group (Black, Hispanic, women, etc.) BEFORE fuzzy matching
2. Check for holistic queries ("how is X doing?") needing multi-dimensional answers
3. Check pre-computed plans first (demographic-aware: only match within same demographic)
4. **Geographic detection** - Warn if query asks about a state but only national data available
5. For holistic queries, augment with hybrid search (RAG + FRED)
6. Apply recency filter (reject series with no data after 2020)
7. Apply relevance filter (title must relate to query)
8. **STRICT LLM validation** - Reject wrong demographic, wrong industry, overly broad series
9. **Presentation validation** - AI determines stock/flow/rate for proper display
10. **Graceful no-data** - If validation rejects all series, show helpful guidance instead of wrong data

## Demographic Routing (CRITICAL)
The `extract_demographic_group()` function prevents cross-demographic confusion:
- "Black workers" → ONLY matches Black-specific plans (not women's data!)
- Demographic keywords: black, hispanic, latino, women, men, immigrant, youth, older

## Geographic Handling
The `detect_geographic_scope()` function detects state/regional queries:
- **Searches FRED** for state-specific series (e.g., TXUR, TXNA for Texas)
- Falls back to national data with warning if no state series found
- State series examples: {STATE}UR (unemployment), {STATE}NA (nonfarm payrolls), {STATE}RGSP (GDP)

## Presentation Validation (Stock vs Flow vs Rate)
The `validate_presentation()` function uses AI to determine how each series should be displayed:

| Category | Example | Display |
|----------|---------|---------|
| **STOCK** | Total Payrolls (159M) | Show as monthly CHANGE (+256K) |
| **FLOW** | Initial Claims (200K/week) | Show as LEVEL (already per-period) |
| **RATE** | Unemployment (4.4%) | Show as LEVEL (already a ratio) |

Key insight: Stocks are cumulative totals where the level is less meaningful than the change. Flows are already measured per-period, so the level IS meaningful.

## Key Files
- `app.py` - Main Streamlit app with query routing and hybrid search
- `agents/agent_ensemble.py` - LLM ensemble for dimension discovery and validation
- `agents/series_rag.py` - RAG system with curated series catalog
- `query_plans.json` - Pre-computed query-to-series mappings
