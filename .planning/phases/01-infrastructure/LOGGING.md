# Logging Guide

## Log File Locations

| Log Type | Path | Format |
|----------|------|--------|
| Application logs | `logs/app.log` | JSON lines |
| LLM calls | `logs/lite_llm/calls.jsonl` | JSON lines |
| Daily job | `scripts/daily_job.log` | Text |
| Cron output | `logs/cron.log` | Text |

## Log Format

### Application Logs (JSON)

```json
{"timestamp": "2026-04-19T15:30:00.123456", "level": "INFO", "logger": "data_manager", "message": "Successfully fetched from tushare", "extra": {}}
```

Fields:
- `timestamp`: ISO8601 format
- `level`: DEBUG, INFO, WARNING, ERROR
- `logger`: Logger name (module)
- `message`: Log message
- `extra`: Additional context (if any)

### LLM Call Logs (JSONL)

Success entry:
```json
{"timestamp": "2026-04-19T15:30:00", "type": "success", "model": "gpt-4", "messages": [...], "response": {...}, "usage": {...}, "duration_ms": 1234.56}
```

Failure entry:
```json
{"timestamp": "2026-04-19T15:30:00", "type": "failure", "model": "gpt-4", "messages": [...], "error": {"type": "APIError", "message": "..."}, "duration_ms": 500.0}
```

## Querying Logs

### Grep for error level
```bash
grep '"level": "ERROR"' logs/app.log
```

### jq for structured queries
```bash
jq 'select(.level == "ERROR")' logs/app.log
```

### Count logs by source
```bash
grep -o '"logger": "[^"]*"' logs/app.log | sort | uniq -c
```

### Find data source failures
```bash
grep "Failed to fetch" logs/app.log
```

### Find LLM call failures
```bash
grep '"type": "failure"' logs/lite_llm/calls.jsonl
```

## Monitoring Data Source Health

Check which fetcher is being used:
```bash
grep "Successfully fetched" logs/app.log | grep -o "from [a-z]*" | sort | uniq -c
```

Check failover events:
```bash
grep "Fetcher.*failed" logs/app.log
```

## Log Retention (Phase 1 Manual)

Phase 1 does not include automated log rotation. User is responsible for:
- Monitoring log file sizes
- Archiving or deleting old logs
- Setting up logrotate if needed

Phase 3+ will include automated log management.

## Configuration

Log level is set via `.env`:
```
LOG_LEVEL=INFO
```

Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
