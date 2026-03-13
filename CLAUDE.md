# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

`jiralog` is a Python CLI package (`jiralog/`) that reads time-tracking JSON logs and bulk-uploads worklogs to Jira via REST API v3.

## Running the script

```bash
# Install once
pip install -e .

jiralog            # interactive mode — prompts for file selection
jiralog --dry-run  # simulate without writing to Jira
```

Required environment variables in `.env`:
- `JIRA_BASE_URL` — e.g. `https://yourcompany.atlassian.net`
- `JIRA_USERNAME` — Jira account email
- `JIRA_API_TOKEN` — Jira API token

Dependencies: `requests`, `colorama`, `python-dotenv`

## Data flow

**Input**: JSON files in `logs/`, named `DD.MM.YYYY.json` (date drives which day worklogs are posted for).

JSON structure:
```json
{
  "laps": [
    {"lapId": 1, "diff": 3366438, "elapsedTime": 32100574, "text": "PROJ-970 Development"}
  ]
}
```
- `diff`: milliseconds spent on the lap
- `text`: `"ISSUE_KEY description"` (e.g. `PROJ-970 Development`)

**Output**: Optional plain-text reports saved to `reports/DD.MM.YYYY_report.txt`.

## Code style

- Code comments — English
- UI strings (print output, error messages) — Russian

## Key logic to understand

- **Grouping**: Laps with the same `(issue_key, task_text)` pair are merged (time summed) before uploading.
- **Minute rounding** (`adjust_laps_to_full_minutes`): Jira truncates each worklog to whole minutes. This function compensates by rounding up laps with the largest second remainders so the total logged minutes match the actual total.
- **Deduplication** (`worklog_exists`): Before posting, checks Jira for an existing worklog with the same `started` timestamp and comment text to avoid duplicates.
- **Start time**: All worklogs for a given file are posted with `started = <file_date> 06:00:00 UTC`.
