import requests
from .config import JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN, RED
from .processor import format_time

HEADERS = {
    'Authorization': requests.auth._basic_auth_str(JIRA_USERNAME, JIRA_API_TOKEN),
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}


def extract_text_from_adf(adf):
    try:
        return adf['content'][0]['content'][0]['text']
    except (KeyError, IndexError, TypeError):
        return ""


def get_existing_worklogs(issue_key):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get('worklogs', [])
        else:
            print(f"{RED}❌ Ошибка получения worklogs для {issue_key}: HTTP {response.status_code}")
            return []
    except requests.RequestException as e:
        print(f"{RED}❌ Ошибка запроса для {issue_key}: {e}")
        return []


def worklog_exists(issue_key, comment_text, started):
    worklogs = get_existing_worklogs(issue_key)
    return any(
        wl.get('started') == started and extract_text_from_adf(wl.get('comment')) == comment_text
        for wl in worklogs
    )


def add_worklog(issue_key, started, time_spent_seconds, comment_text, dry_run=False):
    comment_adf = {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment_text}]}],
    }
    if dry_run:
        return f"🔍 Worklog для {issue_key}: {comment_text} ({format_time(time_spent_seconds)})"
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"
    data = {"started": started, "timeSpentSeconds": time_spent_seconds, "comment": comment_adf}
    try:
        response = requests.post(url, headers=HEADERS, json=data, timeout=10)
        return response.status_code == 201
    except requests.RequestException as e:
        print(f"{RED}❌ Ошибка добавления worklog для {issue_key}: {e}")
        return False
