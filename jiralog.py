import os
import json
import requests
from datetime import datetime, timezone
import re
import argparse
import sys
from colorama import Fore, Back, Style, init
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv()

init(autoreset=True)

RED, YEL, CYN, GRN, BLU = (
    Fore.LIGHTRED_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTCYAN_EX,
    Fore.LIGHTGREEN_EX, Fore.LIGHTBLUE_EX,
)
WHT  = Fore.LIGHTWHITE_EX
BOLD = Style.BRIGHT
BBLU = Back.BLUE
BRST = Back.RESET

# Настройки Jira API
JIRA_BASE_URL = os.environ.get('JIRA_BASE_URL')
JIRA_USERNAME = os.environ.get('JIRA_USERNAME')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')
if not JIRA_BASE_URL or not JIRA_USERNAME or not JIRA_API_TOKEN:
    print(f"{RED}❌ Ошибка: Установите переменные окружения JIRA_BASE_URL, JIRA_USERNAME и JIRA_API_TOKEN.")
    exit(1)

# Конфигурация
HEADERS = {
    'Authorization': f'{requests.auth._basic_auth_str(JIRA_USERNAME, JIRA_API_TOKEN)}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(SCRIPT_DIR, 'logs')
REPORTS_DIR = os.path.join(SCRIPT_DIR, 'reports')
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Блок функций
def get_emoji(num):
    """Возвращает эмоджи для номера."""
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    if 1 <= num <= 10:
        return emojis[num - 1]
    else:
        return f"[{num}]"  # fallback для чисел > 10

def select_file():
    """Выбирает JSON файл из директории скрипта."""
    files = [f for f in os.listdir(LOGS_DIR) if f.endswith('.json')]
    if not files:
        print(f"{RED}❌ Нет JSON файлов в директории logs/.")
        return None

    # Сортировка файлов по дате из названия DESC (новые первыми), только для файлов с датой в названии
    files_with_date = []
    files_without_date = []
    for f in files:
        file_path = os.path.join(LOGS_DIR, f)
        date = parse_date_from_filename(file_path)
        if date is not None:
            files_with_date.append((date, f))
        else:
            files_without_date.append((None, f))

    # Сортировка файлов с датой по дате DESC
    files_with_date.sort(key=lambda x: x[0], reverse=True)
    # Сортировка файлов без даты по имени ASC
    files_without_date.sort(key=lambda x: x[1])

    # Объединяем: сначала с датами, потом без
    sorted_files = files_with_date + files_without_date

    print(f"{YEL}📁 Доступные файлы:")
    for i, (date, f) in enumerate(sorted_files, 1):
        emoji = get_emoji(i)
        print(f" {emoji}  {f}")
    try:
        choice = int(input(" ➡️  Введите номер файла: ")) - 1
        if 0 <= choice < len(sorted_files):
            selected_file = sorted_files[choice][1]
            return os.path.join(LOGS_DIR, selected_file)
        else:
            print(f"{RED}❌ Неверный выбор.")
            return None
    except ValueError:
        print(f"{RED}❌ Введите число.")
        return None

def load_json(file_path):
    """Загружает JSON из файла."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"{RED}❌ Ошибка загрузки JSON: {e}")
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
    print(f"{YEL}⚠️ Не удалось извлечь дату из имени файла.")
    confirm = input("Использовать текущую дату? (y/n): ").lower()
    if confirm != 'y':
        print(f"{RED}❌ Обработка отменена.")
        exit(1)
    return datetime.now(timezone.utc).date()

def parse_issue_id(text):
    """Извлекает ISSUE_ID из текста (например, PROJ-1)."""
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
            print(f"{RED}❌ Ошибка получения worklogs для {issue_key}: HTTP {response.status_code}")
            return []
    except requests.RequestException as e:
        print(f"{RED}❌ Ошибка запроса для {issue_key}: {e}")
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
        print(f"{RED}❌ Ошибка добавления worklog для {issue_key}: {e}")
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

def group_laps(laps):
    """Группирует laps по (ISSUE_ID, текст задачи), суммируя время. Возвращает (grouped, invalid)."""
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
    """Дотягивает нужное количество записей до следующей минуты, чтобы Jira показала реальное время.
    Jira усекает каждый worklog до целых минут — эта функция компенсирует потери."""
    total_seconds = sum(lap['diff'] // 1000 for lap in laps)
    target_minutes = total_seconds // 60
    current_minutes = sum((lap['diff'] // 1000) // 60 for lap in laps)
    deficit = target_minutes - current_minutes
    if deficit <= 0:
        return laps
    # Округляем вверх записи с наибольшим остатком секунд
    order = sorted(range(len(laps)), key=lambda i: (laps[i]['diff'] // 1000) % 60, reverse=True)
    adjusted = [dict(lap) for lap in laps]
    for i in range(min(deficit, len(order))):
        idx = order[i]
        seconds = adjusted[idx]['diff'] // 1000
        adjusted[idx]['diff'] = ((seconds // 60) + 1) * 60 * 1000
    return adjusted

# Парсинг аргументов командной строки
parser = argparse.ArgumentParser(description="Загрузка worklog в Jira из JSON файла.")
parser.add_argument('--dry-run', action='store_true', help="Запуск в режиме dry-run (симуляция без реальных изменений)")
args = parser.parse_args()
dry_run = args.dry_run

# Интро
logo = [
    "     ██╗██╗██████╗  █████╗ ██╗      ██████╗  ██████╗ ",
    "     ██║██║██╔══██╗██╔══██╗██║     ██╔═══██╗██╔════╝ ",
    "     ██║██║██████╔╝███████║██║     ██║   ██║██║  ███╗",
    "██   ██║██║██╔══██╗██╔══██║██║     ██║   ██║██║   ██║",
    "╚█████╔╝██║██║  ██║██║  ██║███████╗╚██████╔╝╚██████╔╝",
    " ╚════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ",
]
WIDTH = 45
INNER = WIDTH * 2 - 5  # ширина контента: (WIDTH × 2col_per_✨) - ✨(2) - space(1) - ✨(2)
border = f"{YEL}" + "✨" * WIDTH
print(border)
max_logo_w = max(len(line) for line in logo)
logo_inner_w = max_logo_w + 4
logo_left  = (INNER - logo_inner_w) // 2
logo_right = INNER - logo_left - logo_inner_w
_logo_row = f"{YEL}✨{BBLU}{' ' * (INNER + 1)}{BRST}{YEL}✨"
print(_logo_row)
for line in logo:
    inner = f"  {line:<{max_logo_w}}  "
    print(f"{YEL}✨{BBLU} {' ' * logo_left}{WHT}{inner}{' ' * logo_right}{BRST}{YEL}✨")
print(_logo_row)
print(f"{YEL}✨{BBLU} {'':{INNER}}{BRST}{YEL}✨")
print(f"{YEL}✨{BBLU} {WHT}Добро пожаловать в волшебный скрипт загрузки worklog в Atlassian Jira!               {BRST}{YEL}✨")
print(f"{YEL}✨{BBLU} {WHT}Этот инструмент поможет вам легко и безопасно добавить время работы из JSON файла.   {BRST}{YEL}✨")
print(f"{YEL}✨{BBLU} {WHT}С поддержкой dry-run, прогресс-бара и яркого цветного вывода.                        {BRST}{YEL}✨")
print(f"{YEL}✨{BBLU} {'':{INNER}}{BRST}{YEL}✨")
print(f"{YEL}✨{BBLU} {BOLD}{WHT}{'Магия начинается! 🪄':^{INNER - 1}}{BRST}{YEL}✨")
print(border)
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

# Группировка и обработка laps
grouped_laps, invalid_laps = group_laps(data['laps'])
grouped_laps = adjust_laps_to_full_minutes(grouped_laps)
for lap in invalid_laps:
    reports['failed'].append(f"Не найден ISSUE_ID в: {lap['text']}")

total = len(grouped_laps)
for i, lap in enumerate(grouped_laps, 1):
    process_lap(lap, reports, total_logged_seconds, dry_run_messages, dry_run)
    sys.stdout.write(f"\n\r{YEL} 🔄 Обработка: {i}/{total} задач ")
    sys.stdout.flush()
print()

# Вывод dry-run сообщений после прогресса
if dry_run:
    print(f"{CYN}🔍 Dry-run симуляция:")
    for msg in dry_run_messages:
        print(f"{CYN}{msg}")
    print()

# Отчет глобальный (успех/провал/есть ошибки)
success_count = len(reports['success'])
failed_count = len(reports['failed'])
skipped_count = len(reports['skipped'])

if failed_count == 0 and skipped_count == 0:
    global_status = f"{GRN}✅ Успех"
elif success_count > 0:
    global_status = f"{YEL}⚠️ Есть ошибки"
else:
    global_status = f"{RED}❌ Провал"

mode = "DRY-RUN" if dry_run else "REAL"
print(f"\n{YEL}📊 Глобальный отчет ({mode}): {global_status}")
print(f"{CYN}📅 Дата и время обрабатываемого дня: {started}")
print(f"{BLU}🧮 Обработано: {total}, Успешно: {success_count}, Пропущено: {skipped_count}, Ошибок: {failed_count}")
print(f"{GRN}🕒 Общая сумма залогированного времени: {format_time(total_logged_seconds[0])}")

# Отчет по записям issues (успех/провал)
print(f"\n{YEL}📝 Отчет по записям:")
for item in reports['success']:
    print(f"{GRN}✅ Успех: {item}")
for item in reports['skipped']:
    print(f"{YEL}⏭️  Пропущено: {item}")
for item in reports['failed']:
    print(f"{RED}❌ Ошибка: {item}")

# Экспорт отчета в файл
save_report = input("Сохранить отчет в файл? (y/n): ").lower() == 'y'
if save_report:
    report_filename = os.path.join(REPORTS_DIR, f"{file_date.strftime('%d.%m.%Y')}_report.txt")
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
    print(f"{GRN}📄 Отчет сохранен в {report_filename}")