---
phase: 01-infrastructure
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - src/data/base.py
  - src/data/tushare_fetcher.py
  - src/data/akshare_fetcher.py
  - src/data/efinance_fetcher.py
  - src/data/manager.py
  - src/data/__init__.py
  - src/config/settings.py
  - src/config/__init__.py
autonomous: true
requirements:
  - INFRA-03

must_haves:
  truths:
    - "TushareFetcher can fetch stock list and daily market data with rate limiting"
    - "AkshareFetcher and EfinanceFetcher work as fallbacks without token"
    - "DataFetcherManager routes requests with failover: Tushare -> Akshare -> Efinance"
    - "Rate limiting enforced: 80 calls/min for Tushare free tier"
  artifacts:
    - path: "src/config/settings.py"
      provides: "Pydantic settings for DATABASE_URL, TUSHARE_TOKEN, API timeouts"
      exports: ["Settings", "settings"]
    - path: "src/data/base.py"
      provides: "Abstract BaseFetcher with common interface"
      exports: ["BaseFetcher", "FetchResult"]
    - path: "src/data/tushare_fetcher.py"
      provides: "Tushare Pro API integration with rate limiting"
      exports: ["TushareFetcher"]
    - path: "src/data/manager.py"
      provides: "DataFetcherManager with failover logic"
      exports: ["DataFetcherManager"]
  key_links:
    - from: "src/data/tushare_fetcher.py"
      to: "Tushare Pro API"
      via: "HTTP requests with token auth"
      pattern: "tushare\\.pro|api\\.tushare\\.pro"
    - from: "src/data/manager.py"
      to: "src/data/tushare_fetcher.py"
      via: "Importer instantiation"
      pattern: "from .*tushare_fetcher import TushareFetcher"
---

<objective>
Implement data source layer with Tushare as primary (D-02), Akshare and Efinance as fallbacks, with rate limiting and failover.

Purpose: Enable automated data fetching from external sources without manual intervention per INFRA-03.
Output: Three fetcher implementations, abstract base class, and manager with failover logic.
</objective>

<execution_context>
@/Users/heyecheng/.claude/get-shit-done/workflows/execute-plan.md
@/Users/heyecheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-infrastructure/01-CONTEXT.md
@.planning/phases/01-infrastructure/01-RESEARCH.md
@.planning/REQUIREMENTS.md
</context>

<interfaces>
<!-- Key types from Plan 01 -->

From src/database/models.py (after Plan 01 completes):
```python
class MarketDataModel(Base):
    # Columns: id, ts_code, trade_date, open, high, low, close, volume, amount, source, created_at
```

From src/config/settings.py:
```python
class Settings(BaseSettings):
    database_url: str
    tushare_token: str
    tushare_rate_limit: int = 80
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create configuration module with Pydantic settings</name>
  <files>src/config/settings.py, src/config/__init__.py, .env.example</files>
  <action>
    Create src/config/__init__.py (empty init).
    
    Create src/config/settings.py with:
    1. Settings class inheriting from BaseSettings
    2. Fields:
       - database_url: str (required)
       - tushare_token: str (required for TushareFetcher)
       - tushare_rate_limit: int = 80 (default from research)
       - tushare_daily_limit: int = 500
       - request_timeout: int = 30
       - log_level: str = "INFO"
    3. Config: env_file=".env", case_sensitive=False
    4. Export settings = Settings() singleton
    
    Create .env.example with:
       DATABASE_URL=mysql+aiomysql://user:pass@localhost:3306/stock_logic
       TUSHARE_TOKEN=your_token_here
       LOG_LEVEL=INFO
  </action>
  <verify>
    <automated>python -c "from src.config.settings import settings; print(f'DB: {settings.database_url[:20]}...')"</automated>
  </verify>
  <done>
    Settings class loads from environment; .env.example documents required variables; tushare_token validated at runtime.
  </done>
</task>

<task type="auto">
  <name>Task 2: Define abstract BaseFetcher with common interface</name>
  <files>src/data/base.py</files>
  <action>
    Create src/data/base.py with:
    
    1. FetchResult dataclass:
       - success: bool
       - data: Optional[pd.DataFrame]
       - error: Optional[str]
       - source: str
    
    2. BaseFetcher abstract class:
       - Abstract methods:
         - get_stock_list() -> FetchResult
         - get_daily_data(ts_code: str, days: int = 1) -> FetchResult
         - get_limit_list(trade_date: str) -> FetchResult (optional)
       - Concrete methods:
         - _log_request(method, params)
         - _handle_error(error, method)
       - Properties:
         - name: str (e.g., "tushare", "akshare")
         - is_available: bool (health check)
    
    3. All methods return FetchResult (never raise exceptions directly).
  </action>
  <verify>
    <automated>python -c "from src.data.base import BaseFetcher, FetchResult; print('OK')"</automated>
  </verify>
  <done>
    FetchResult dataclass and BaseFetcher abstract class import successfully; abstract methods defined.
  </done>
</task>

<task type="auto">
  <name>Task 3: Implement TushareFetcher with rate limiting (Priority 1 per D-02)</name>
  <files>src/data/tushare_fetcher.py</files>
  <action>
    Create src/data/tushare_fetcher.py with:
    
    1. TushareFetcher(BaseFetcher):
       - __init__: Validate tushare_token from settings; log warning if missing
       - name = "tushare"
       - is_available = token is not None
    
    2. Rate limiting (per RESEARCH.md):
       - _call_count: int
       - _minute_start: Optional[float]
       - _check_rate_limit(): Sleep if 80 calls/min exceeded
    
    3. Implement methods:
       - get_stock_list() -> FetchResult with columns: ts_code, name, industry, listed_date
       - get_daily_data(ts_code, days=1) -> FetchResult with OHLCV data
       - get_limit_list(trade_date) -> FetchResult with limit_up/down stocks
    
    4. Use direct HTTP requests (not tushare SDK) per existing pattern.
       API endpoint: http://api.tushare.pro
       Request format: POST with {"api_name": "xxx", "token": "...", "params": {...}}
    
    5. Handle Tushare-specific errors:
       - 403: Token invalid or insufficient points
       - 429: Rate limited (shouldn't happen with our limiting)
       - Empty response: Return FetchResult(success=False, data=empty_df)
  </action>
  <verify>
    <automated>python -c "from src.data.tushare_fetcher import TushareFetcher; f = TushareFetcher(); print(f'Available: {f.is_available}')"</automated>
  </verify>
  <done>
    TushareFetcher instantiates; rate limiting counter works; methods return FetchResult with DataFrame or error.
  </done>
</task>

<task type="auto">
  <name>Task 4: Implement AkshareFetcher and EfinanceFetcher (fallback sources)</name>
  <files>src/data/akshare_fetcher.py, src/data/efinance_fetcher.py</files>
  <action>
    Create src/data/akshare_fetcher.py:
    - AkshareFetcher(BaseFetcher)
    - name = "akshare"
    - is_available = True (no token required)
    - get_stock_list(): Use ak.stock_info_a_code_name()
    - get_daily_data(): Use ak.stock_zh_a_hist()
    - Wrap in try/except; return FetchResult on error
    
    Create src/data/efinance_fetcher.py:
    - EfinanceFetcher(BaseFetcher)
    - name = "efinance"
    - is_available = True
    - get_stock_list(): Use efinance.stock.get_all_stock_code()
    - get_daily_data(): Use efinance.stock.get_quote_history()
    - No token required, completely free
    
    Per D-02: These are fallbacks; Tushare is primary.
  </action>
  <verify>
    <automated>python -c "from src.data.akshare_fetcher import AkshareFetcher; from src.data.efinance_fetcher import EfinanceFetcher; print('OK')"</automated>
  </verify>
  <done>
    Both fetchers instantiate; methods return FetchResult; no token required.
  </done>
</task>

<task type="auto">
  <name>Task 5: Implement DataFetcherManager with failover logic</name>
  <files>src/data/manager.py, src/data/__init__.py</files>
  <action>
    Create src/data/manager.py:
    
    DataFetcherManager class:
    - __init__: Instantiate TushareFetcher, AkshareFetcher, EfinanceFetcher
    - fetchers: List[Tuple[BaseFetcher, priority]] (lower = higher priority)
      [(tushare, 1), (akshare, 2), (efinance, 3)]
    
    - get_stock_list() -> pd.DataFrame:
      For each fetcher by priority:
        result = fetcher.get_stock_list()
        If result.success and not result.data.empty: return result.data
      Return empty DataFrame after all fail
    
    - get_daily_data(ts_code, days) -> Tuple[pd.DataFrame, str]:
      Same failover pattern; return (df, source_name)
    
    - get_limit_list(trade_date) -> pd.DataFrame:
      Same failover pattern
    
    - _log_failure(fetcher_name, method, error): Log which fetcher failed
    
    Create src/data/__init__.py with exports:
      from .manager import DataFetcherManager
      from .base import BaseFetcher, FetchResult
  </action>
  <verify>
    <automated>python -c "from src.data.manager import DataFetcherManager; m = DataFetcherManager(); print(f'Fetchers: {len(m.fetchers)}')"</automated>
  </verify>
  <done>
    DataFetcherManager instantiates with 3 fetchers; failover logic implemented for all methods.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Application → Tushare API | API token must be protected; transmitted over HTTPS |
| Application → Third-party APIs | Akshare/Efinance are public; no auth required |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-05 | Information Disclosure | TUSHARE_TOKEN env var | mitigate | Load from .env (not committed); document in .env.example; never log token value |
| T-01-06 | Denial of Service | Tushare rate limiting | mitigate | _check_rate_limit() enforces 80 calls/min; counter resets per minute |
| T-01-07 | Integrity | Data source response validation | mitigate | FetchResult validates success flag; empty DataFrame on error; no silent failures |
| T-01-08 | Repudiation | API call failures | accept | Log failures with fetcher name, method, error; no audit trail required for Phase 1 |
</threat_model>

<verification>
- Config test: python -c "from src.config.settings import settings; print(settings.tushare_rate_limit)"
- TushareFetcher test: python -c "from src.data.tushare_fetcher import TushareFetcher; f = TushareFetcher(); print(f.is_available)"
- Manager test: python -c "from src.data.manager import DataFetcherManager; m = DataFetcherManager(); print(len(m.fetchers))"
- Rate limit test: Inspect TushareFetcher._check_rate_limit() logic
</verification>

<success_criteria>
1. Settings class loads DATABASE_URL, TUSHARE_TOKEN from environment
2. BaseFetcher defines common interface (get_stock_list, get_daily_data, get_limit_list)
3. TushareFetcher implements rate limiting (80 calls/min) per research
4. AkshareFetcher and EfinanceFetcher work without token as fallbacks
5. DataFetcherManager routes with failover: Tushare -> Akshare -> Efinance
6. .env.example documents all required environment variables
</success_criteria>

<output>
After completion, create .planning/phases/01-infrastructure/02-02-SUMMARY.md
</output>
