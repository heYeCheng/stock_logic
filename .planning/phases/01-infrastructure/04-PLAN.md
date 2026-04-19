---
phase: 01-infrastructure
plan: 04
type: execute
wave: 2
depends_on:
  - 01-infrastructure-01
  - 01-infrastructure-02
files_modified:
  - src/logging/__init__.py
  - src/logging/litellm_callback.py
  - src/logging/app_logger.py
  - logs/.gitkeep
autonomous: true
requirements:
  - INFRA-04

must_haves:
  truths:
    - "LLM calls are logged to JSON format in logs/lite_llm/calls.jsonl"
    - "Application logs to logs/app.log with structured format"
    - "Data source health (success/failure) is logged for monitoring"
    - "JSON logs contain timestamp, model, messages, response, usage"
  artifacts:
    - path: "src/logging/__init__.py"
      provides: "Logging module exports"
      exports: ["setup_logging", "get_logger"]
    - path: "src/logging/litellm_callback.py"
      provides: "LiteLLM custom callback for JSON file logging"
      exports: ["FileJsonLogger", "setup_litellm_logging"]
    - path: "src/logging/app_logger.py"
      provides: "Application logger with JSON formatter"
      exports: ["setup_app_logging"]
    - path: "logs/.gitkeep"
      provides: "Empty file to track logs/ directory in git"
      contains: ""
  key_links:
    - from: "src/logging/litellm_callback.py"
      to: "logs/lite_llm/calls.jsonl"
      via: "File append on each LLM call"
      pattern: "logs/lite_llm/calls\\.jsonl"
    - from: "src/logging/app_logger.py"
      to: "logs/app.log"
      via: "FileHandler configuration"
      pattern: "FileHandler\\('logs/app\\.log'\\)"
---

<objective>
Implement structured JSON logging for LLM calls (LiteLLM) and application logs per D-04.

Purpose: Enable monitoring of LLM calls and data source health for debugging and observability per INFRA-04.
Output: JSON log files in logs/lite_llm/calls.jsonl and logs/app.log.
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
<!-- Key types from Plan 02 -->

From src/data/base.py (Plan 02):
```python
class FetchResult:
    success: bool
    data: Optional[pd.DataFrame]
    error: Optional[str]
    source: str

class BaseFetcher:
    def get_stock_list() -> FetchResult
    def get_daily_data(ts_code: str, days: int = 1) -> FetchResult
```

From src/config/settings.py (Plan 02):
```python
class Settings(BaseSettings):
    log_level: str = "INFO"
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create logging directory structure and app logger</name>
  <files>logs/.gitkeep, logs/lite_llm/.gitkeep, src/logging/__init__.py, src/logging/app_logger.py</files>
  <action>
    1. Create directories:
       - mkdir -p logs/lite_llm
       - touch logs/.gitkeep logs/lite_llm/.gitkeep
    
    2. Create src/logging/__init__.py with exports:
       from .app_logger import setup_app_logging, get_logger
    
    3. Create src/logging/app_logger.py with:
       - setup_app_logging() function:
         - Create logs/ directory if not exists
         - Configure root logger with level from settings.log_level
         - Add FileHandler('logs/app.log') with JSON formatter
         - Add StreamHandler() for console output
         - JSON format: {"timestamp": ISO8601, "level": str, "logger": str, "message": str, "extra": dict}
         - Use python-json-logger if available, else custom JsonFormatter
       
       - get_logger(name) -> logging.Logger:
         - Return logging.getLogger(name)
         - Ensure propagate=True to reach root handler
  </action>
  <verify>
    <automated>python -c "from src.logging.app_logger import setup_app_logging; setup_app_logging(); import logging; logger = logging.getLogger('test'); logger.info('Test message'); print('OK')"</automated>
  </verify>
  <done>
    Log directories created; app logger writes to logs/app.log and console; JSON format verified.
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement LiteLLM JSON file callback logger</name>
  <files>src/logging/litellm_callback.py</files>
  <action>
    Create src/logging/litellm_callback.py with:
    
    1. FileJsonLogger class (inherits from litellm.integrations.custom_logger.CustomLogger):
       - __init__: Ensure logs/lite_llm/ directory exists
       - async_log_success_event(kwargs, response_obj, start_time, end_time):
         - Extract: model, messages, response, usage, cost (if available)
         - Create JSON entry:
           {
             "timestamp": datetime.now().isoformat(),
             "type": "success",
             "model": kwargs.get("model"),
             "messages": kwargs.get("messages"),
             "response": response_obj.model_dump() if hasattr(response_obj, 'model_dump') else str(response_obj),
             "usage": kwargs.get("usage"),
             "duration_ms": (end_time - start_time).total_seconds() * 1000
           }
         - Append to logs/lite_llm/calls.jsonl (one JSON per line)
       
       - async_log_failure_event(kwargs, exception, start_time, end_time):
         - Extract: model, messages, error type, error message
         - Create JSON entry:
           {
             "timestamp": datetime.now().isoformat(),
             "type": "failure",
             "model": kwargs.get("model"),
             "messages": kwargs.get("messages"),
             "error": {"type": type(exception).__name__, "message": str(exception)},
             "duration_ms": (end_time - start_time).total_seconds() * 1000
           }
         - Append to logs/lite_llm/calls.jsonl
    
    2. setup_litellm_logging() function:
       - Instantiate FileJsonLogger
       - Set litellm.success_callback = [file_json_logger]
       - Set litellm.failure_callback = [file_json_logger]
       - Log confirmation message
    
    Per D-04: No custom cost tracking dashboard in Phase 1.
  </action>
  <verify>
    <automated>python -c "from src.logging.litellm_callback import setup_litellm_logging; setup_litellm_logging(); print('OK')"</automated>
  </verify>
  <done>
    FileJsonLogger instantiated; litellm callbacks registered; logs/lite_llm/calls.jsonl path configured.
  </done>
</task>

<task type="auto">
  <name>Task 3: Wire logging into data fetchers for health monitoring</name>
  <files>src/data/tushare_fetcher.py, src/data/akshare_fetcher.py, src/data/efinance_fetcher.py, src/data/manager.py</files>
  <action>
    Update src/data/tushare_fetcher.py:
    - Import get_logger from src.logging
    - Add self.logger = get_logger("tushare_fetcher")
    - Log in get_stock_list(), get_daily_data():
      - Start: "Fetching {method} for {params}"
      - Success: "Fetched {count} records from {source}"
      - Error: "Failed to fetch {method}: {error}"
      - Rate limit wait: "Rate limit reached, waiting {seconds}s"
    
    Update src/data/akshare_fetcher.py and src/data/efinance_fetcher.py:
    - Same logging pattern as TushareFetcher
    
    Update src/data/manager.py:
    - Import get_logger
    - Add self.logger = get_logger("data_manager")
    - Log in failover:
      - "Attempting {method} with {fetcher_name}"
      - "Fetcher {fetcher_name} failed: {error}, trying next"
      - "Successfully fetched from {source}"
      - "All fetchers failed for {method}"
    
    This provides data source health monitoring per INFRA-04.
  </action>
  <verify>
    <automated>python -c "from src.data.manager import DataFetcherManager; m = DataFetcherManager(); print('OK')"</automated>
  </verify>
  <done>
    All fetchers log to app.log; health monitoring visible in logs (success/failure per source).
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Checkpoint: Verify LLM and data source logging</name>
  <what-built>
    Implemented JSON logging for LLM calls to logs/lite_llm/calls.jsonl.
    Implemented application logging to logs/app.log with data source health monitoring.
  </what-built>
  <how-to-verify>
    1. Run test script: python scripts/daily_job.py
    2. Check app.log: tail -30 logs/app.log
       Expected: JSON lines with timestamp, level, message
    3. Check lite_llm directory: ls -la logs/lite_llm/
       Expected: calls.jsonl exists (may be empty until Phase 3 LLM usage)
    4. Verify log rotation (optional): Confirm logs don't grow unbounded
       - Check if log file size is reasonable (< 100MB)
    
    Sample app.log output:
    {"timestamp": "2026-04-19T15:30:00.123456", "level": "INFO", "logger": "data_manager", "message": "Successfully fetched from tushare"}
    
    Sample calls.jsonl output (after Phase 3 LLM integration):
    {"timestamp": "2026-04-19T15:30:00", "type": "success", "model": "gpt-4", "messages": [...], "response": {...}, "usage": {...}}
  </how-to-verify>
  <resume-signal>
    Type "approved" after verifying logs are written correctly, or describe any issues.
  </resume-signal>
</task>

<task type="auto">
  <name>Task 4: Create logging documentation and .gitkeep files</name>
  <files>.gitignore, .planning/phases/01-infrastructure/LOGGING.md</files>
  <action>
    Update .gitignore:
    - Add: logs/*.log (ignore log files)
    - Add: !logs/.gitkeep (track directory)
    - Add: logs/lite_llm/*.jsonl (ignore JSONL logs)
    - Add: !logs/lite_llm/.gitkeep (track directory)
    
    Create .planning/phases/01-infrastructure/LOGGING.md with:
    1. Log file locations:
       - Application: logs/app.log
       - LLM calls: logs/lite_llm/calls.jsonl
       - Cron job: scripts/daily_job.log, logs/cron.log
    2. Log format (JSON):
       - Fields: timestamp, level, logger, message, extra
    3. Querying logs:
       - grep for level: grep '"level": "ERROR"' logs/app.log
       - jq for structured: jq 'select(.level == "ERROR")' logs/app.log
    4. Monitoring data source health:
       - Search for "Failed to fetch" in app.log
       - Count by source: grep -o '"logger": "[^"]*"' logs/app.log | sort | uniq -c
    5. Log retention (Phase 1 manual):
       - User responsible for log rotation/cleanup
       - Phase 3+: automated log management
  </action>
  <verify>
    <automated>test -f .planning/phases/01-infrastructure/LOGGING.md && echo "OK"</automated>
  </verify>
  <done>
    LOGGING.md created with documentation; .gitignore configured for logs directory.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Application → Log Files | Log files may contain sensitive data (API responses, errors with context) |
| Logs → Monitoring Systems | Logs may be shipped to external systems (future Phase 3+) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-13 | Information Disclosure | LLM call logs (messages, responses) | mitigate | Document in LOGGING.md that logs contain sensitive data; restrict file permissions (chmod 600) |
| T-01-14 | Information Disclosure | Tushare token in error logs | mitigate | Never log full connection strings or tokens; log only error type and message |
| T-01-15 | Integrity | Log file tampering | accept | Phase 1: file-based logs with no integrity checking; Phase 3+: consider signed logs |
| T-01-16 | Availability | Log disk exhaustion | accept | Phase 1: manual monitoring; Phase 3+: log rotation and size limits |
</threat_model>

<verification>
- App logger test: python -c "from src.logging.app_logger import setup_app_logging; setup_app_logging(); import logging; logging.getLogger('test').info('test'); print('OK')"
- LiteLLM callback test: python -c "from src.logging.litellm_callback import setup_litellm_logging; setup_litellm_logging(); import litellm; print(litellm.success_callback)"
- Log file verification: test -f logs/app.log && tail -5 logs/app.log
- Directory structure: ls -la logs/ logs/lite_llm/
</verification>

<success_criteria>
1. logs/ and logs/lite_llm/ directories created with .gitkeep files
2. App logger writes JSON format to logs/app.log and console
3. LiteLLM FileJsonLogger writes to logs/lite_llm/calls.jsonl
4. Data fetchers log health status (success/failure per source)
5. .gitignore configured to exclude log files but track directories
6. LOGGING.md documents log locations, formats, and querying
7. No custom dashboard (per D-04: LiteLLM + JSON logs only)
</success_criteria>

<output>
After completion, create .planning/phases/01-infrastructure/04-04-SUMMARY.md
</output>
