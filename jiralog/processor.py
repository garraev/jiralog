import re


def parse_issue_id(text):
    match = re.search(r'([A-Z]+-\d+)', text)
    return match.group(1) if match else None


def parse_task_text(text):
    issue_id = parse_issue_id(text)
    return text.replace(issue_id, '').strip() if issue_id else text.strip()


def parse_task_time(lap):
    return lap['diff'] // 1000


def format_time(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def group_laps(laps):
    grouped = {}
    invalid = []
    for lap in laps:
        issue_id = parse_issue_id(lap['text'])
        if not issue_id:
            invalid.append(lap)
            continue
        task_text = parse_task_text(lap['text'])
        key = (issue_id, task_text)
        if key not in grouped:
            grouped[key] = {'text': lap['text'], 'diff': 0}
        grouped[key]['diff'] += lap['diff']
    return list(grouped.values()), invalid


def adjust_laps_to_full_minutes(laps):
    # Jira truncates each worklog to whole minutes — compensate by rounding up
    # laps with the largest second remainders
    total_seconds = sum(lap['diff'] // 1000 for lap in laps)
    target_minutes = total_seconds // 60
    current_minutes = sum((lap['diff'] // 1000) // 60 for lap in laps)
    deficit = target_minutes - current_minutes
    if deficit <= 0:
        return laps
    order = sorted(range(len(laps)), key=lambda i: (laps[i]['diff'] // 1000) % 60, reverse=True)
    adjusted = [dict(lap) for lap in laps]
    for i in range(min(deficit, len(order))):
        idx = order[i]
        seconds = adjusted[idx]['diff'] // 1000
        adjusted[idx]['diff'] = ((seconds // 60) + 1) * 60 * 1000
    return adjusted


def process_lap(lap, started, reports, total_logged_seconds, dry_run_messages, dry_run=False):
    from .jira import worklog_exists, add_worklog

    text = lap['text']
    issue_id = parse_issue_id(text)
    if not issue_id:
        reports['failed'].append(f"Не найден ISSUE_ID в: {text}")
        return
    task_text = parse_task_text(text)
    time_spent_seconds = parse_task_time(lap)
    if time_spent_seconds <= 0 or not task_text.strip():
        reports['failed'].append(f"Недопустимые данные для {issue_id}: время={time_spent_seconds}, текст='{task_text}'")
        return
    if worklog_exists(issue_id, task_text, started):
        reports['skipped'].append(f"Worklog уже существует для {issue_id}: {task_text}")
        return
    result = add_worklog(issue_id, started, time_spent_seconds, task_text, dry_run)
    if dry_run:
        dry_run_messages.append(result)
        reports['success'].append(f"Добавлен worklog для {issue_id}: {task_text} ({format_time(time_spent_seconds)})")
        total_logged_seconds[0] += time_spent_seconds
    elif result:
        reports['success'].append(f"Добавлен worklog для {issue_id}: {task_text} ({format_time(time_spent_seconds)})")
        total_logged_seconds[0] += time_spent_seconds
    else:
        reports['failed'].append(f"Ошибка добавления worklog для {issue_id}: {task_text}")
