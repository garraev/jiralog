import os
import json
import requests
from datetime import datetime, timezone
import re
import argparse
import sys
from colorama import Fore, init

# Инициализация colorama для цветного вывода
init(autoreset=True)

# Настройки Jira API
JIRA_BASE_URL = ''
JIRA_USERNAME = ''
JIRA_API_TOKEN = ''

# Конфигурация
HEADERS = {
    'Authorization': f'{requests.auth._basic_auth_str(JIRA_USERNAME, JIRA_API_TOKEN)}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Блок функций
def select_file():
    """Выбирает JSON файл из директории скрипта."""
    files = [f for f in os.listdir(SCRIPT_DIR) if f.endswith('.json')]
    if not files:
        print(f"{Fore.LIGHTRED_EX}❌ Нет JSON файлов в директории.")
        return None
    print(f"{Fore.LIGHTYELLOW_EX}📁 Доступные файлы:")
    for i, f in enumerate(files, 1):
        print(f"{i}. {f}")
    try:
        choice = int(input("Введите номер файла: ")) - 1
        if 0 <= choice < len(files):
            return os.path.join(SCRIPT_DIR, files[choice])
        else:
            print(f"{Fore.LIGHTRED_EX}❌ Неверный выбор.")
            return None
    except ValueError:
        print(f"{Fore.LIGHTRED_EX}❌ Введите число.")
        return None

def load_json(file_path):
    """Загружает JSON из файла."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"{Fore.LIGHTRED_EX}❌ Ошибка загрузки JSON: {e}")
        return None

def parse_date_from_filename(file_path):
    """Извлекает дату из имени файла (формат: DD.MM.YYYY)."""
    filename = os.path.basename(file_path)
    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', filename)
    if match:
        date_str = match.group(1)
        try:
            return datetime.strptime(date_str, '%d.%m.%Y').date()
        except ValueError:
            pass
    print(f"{Fore.LIGHTYELLOW_EX}⚠️ Не удалось извлечь дату из имени файла.")
    confirm = input("Использовать текущую дату? (y/n): ").lower()
    if confirm != 'y':
        print(f"{Fore.LIGHTRED_EX}❌ Обработка отменена.")
        exit(1)
    return datetime.now(timezone.utc).date()

def parse_issue_id(text):
    """Извлекает ISSUE_ID из текста (например, RS-1)."""
    match = re.search(r'([A-Z]+-\d+)', text)
    return match.group(1) if match else None

def parse_task_text(text):
    """Возвращает текст задачи без issue_key."""
    issue_id = parse_issue_id(text)
    return text.replace(issue_id, '').strip() if issue_id else text.strip()

def parse_task_time(lap):
    """Парсит время задачи: возвращает timeSpentSeconds."""
    return lap['diff'] // 1000

def format_time(seconds):
    """Форматирует секунды в 'HH:MM'."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

def extract_text_from_adf(adf):
    """Извлекает текст из Atlassian Document Format (ADF)."""
    try:
        return adf['content'][0]['content'][0]['text']
    except (KeyError, IndexError, TypeError):
        return ""

def get_existing_worklogs(issue_key):
    """Получает существующие worklogs для issue."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json().get('worklogs', [])
        else:
            print(f"{Fore.LIGHTRED_EX}❌ Ошибка получения worklogs для {issue_key}: HTTP {response.status_code}")
            return []
    except requests.RequestException as e:
        print(f"{Fore.LIGHTRED_EX}❌ Ошибка запроса для {issue_key}: {e}")
        return []

def worklog_exists(issue_key, comment_text, started):
    """Проверяет, существует ли worklog с таким comment и started (в рамках дня)."""
    worklogs = get_existing_worklogs(issue_key)
    return any(wl.get('started') == started and extract_text_from_adf(wl.get('comment')) == comment_text for wl in worklogs)

def add_worklog(issue_key, started, time_spent_seconds, comment_text, dry_run=False):
    """Добавляет worklog в Jira. В dry-run режиме симулирует."""
    comment_adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": comment_text
                    }
                ]
            }
        ]
    }
    if dry_run:
        return f"🔍 Worklog для {issue_key}: {comment_text} ({format_time(time_spent_seconds)})"
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/worklog"
    data = {
        "started": started,
        "timeSpentSeconds": time_spent_seconds,
        "comment": comment_adf
    }
    try:
        response = requests.post(url, headers=HEADERS, json=data, timeout=10)
        return response.status_code == 201
    except requests.RequestException as e:
        print(f"{Fore.LIGHTRED_EX}❌ Ошибка добавления worklog для {issue_key}: {e}")
        return False

def process_lap(lap, reports, total_logged_seconds, dry_run_messages, dry_run=False):
    """Обрабатывает один lap: парсит и добавляет worklog если нужно."""
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

# Парсинг аргументов командной строки
parser = argparse.ArgumentParser(description="Загрузка worklog в Jira из JSON файла.")
parser.add_argument('--dry-run', action='store_true', help="Запуск в режиме dry-run (симуляция без реальных изменений)")
args = parser.parse_args()
dry_run = args.dry_run

# Интро
width = 45
print("✨" * width)
print(f"✨ {Fore.LIGHTYELLOW_EX}Добро пожаловать в волшебный скрипт загрузки worklog в Jira!                         ✨")
print(f"✨ {Fore.LIGHTYELLOW_EX}Этот инструмент поможет вам легко и безопасно добавить время работы из JSON файла.   ✨")
print(f"✨ {Fore.LIGHTYELLOW_EX}С поддержкой dry-run, прогресс-бара и яркого цветного вывода.                        ✨")
print(f"✨ {Fore.LIGHTCYAN_EX}Магия начинается! 🪄                                                                 ✨")
print("✨" * width)
print()

# Загрузка JSON
file_path = select_file()
if not file_path:
    exit(1)
data = load_json(file_path)
if not data:
    exit(1)

# Извлекаем дату из имени файла и устанавливаем start_time как 6:00 UTC того дня
file_date = parse_date_from_filename(file_path)
start_time = datetime.combine(file_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=6)
started = start_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+0000'

# Инициализация отчетов и суммы времени
reports = {'success': [], 'failed': [], 'skipped': []}
total_logged_seconds = [0]
dry_run_messages = []

# Обработка laps с прогресс-баром
total = len(data['laps'])
for i, lap in enumerate(data['laps'], 1):
    process_lap(lap, reports, total_logged_seconds, dry_run_messages, dry_run)
    sys.stdout.write(f"\r{Fore.LIGHTYELLOW_EX}🔄 Обработка: {i}/{total} laps ")
    sys.stdout.flush()
print()

# Вывод dry-run сообщений после прогресса
if dry_run:
    print(f"{Fore.LIGHTCYAN_EX}🔍 Dry-run симуляция:")
    for msg in dry_run_messages:
        print(f"{Fore.LIGHTCYAN_EX}{msg}")
    print()

# Отчет глобальный (успех/провал/есть ошибки)
success_count = len(reports['success'])
failed_count = len(reports['failed'])
skipped_count = len(reports['skipped'])

if failed_count == 0 and skipped_count == 0:
    global_status = f"{Fore.LIGHTGREEN_EX}✅ Успех"
elif success_count > 0:
    global_status = f"{Fore.LIGHTYELLOW_EX}⚠️ Есть ошибки"
else:
    global_status = f"{Fore.LIGHTRED_EX}❌ Провал"

mode = "DRY-RUN" if dry_run else "REAL"
print(f"\n{Fore.LIGHTYELLOW_EX}📊 Глобальный отчет ({mode}): {global_status}")
print(f"{Fore.LIGHTCYAN_EX}📅 Дата и время обрабатываемого дня: {started}")
print(f"{Fore.LIGHTBLUE_EX}🧮 Обработано: {total}, Успешно: {success_count}, Пропущено: {skipped_count}, Ошибок: {failed_count}")
print(f"{Fore.LIGHTGREEN_EX}🕒 Общая сумма залогированного времени: {format_time(total_logged_seconds[0])}")

# Отчет по записям issues (успех/провал)
print(f"\n{Fore.LIGHTYELLOW_EX}📝 Отчет по записям:")
for item in reports['success']:
    print(f"{Fore.LIGHTGREEN_EX}✅ Успех: {item}")
for item in reports['skipped']:
    print(f"{Fore.LIGHTYELLOW_EX}⏭️  Пропущено: {item}")
for item in reports['failed']:
    print(f"{Fore.LIGHTRED_EX}❌ Ошибка: {item}")

# Экспорт отчета в файл
save_report = input("Сохранить отчет в файл? (y/n): ").lower() == 'y'
if save_report:
    report_filename = f"worklog_report_{file_date}.txt"
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(f"Глобальный отчет ({mode}): {'Успех' if failed_count == 0 and skipped_count == 0 else 'Есть ошибки' if success_count > 0 else 'Провал'}\n")
        f.write(f"Дата и время обрабатываемого дня: {started}\n")
        f.write(f"Обработано: {total}, Успешно: {success_count}, Пропущено: {skipped_count}, Ошибок: {failed_count}\n")
        f.write(f"Общая сумма залогированного времени: {format_time(total_logged_seconds[0])}\n\n")
        f.write("Отчет по записям:\n")
        for item in reports['success']:
            f.write(f"Успех: {item}\n")
        for item in reports['skipped']:
            f.write(f"Пропущено: {item}\n")
        for item in reports['failed']:
            f.write(f"Ошибка: {item}\n")
    print(f"{Fore.LIGHTGREEN_EX}📄 Отчет сохранен в {report_filename}")