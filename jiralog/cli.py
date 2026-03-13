import os
import json
import sys
import argparse
from datetime import datetime, timezone

from .config import (
    RED, YEL, CYN, GRN, WHT, BOLD, BBLU, BRST,
    JIRA_BASE_URL, JIRA_USERNAME, JIRA_API_TOKEN,
    LOGS_DIR, REPORTS_DIR,
)
from .processor import group_laps, adjust_laps_to_full_minutes, process_lap
from .report import print_report, save_report


def get_emoji(num):
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    return emojis[num - 1] if 1 <= num <= 10 else f"[{num}]"


def parse_date_from_filename(file_path):
    import re
    filename = os.path.basename(file_path)
    match = re.search(r'(\d{2}\.\d{2}\.\d{4})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%d.%m.%Y').date()
        except ValueError:
            pass
    print(f"{YEL}⚠️ Не удалось извлечь дату из имени файла.")
    if input("Использовать текущую дату? (y/n): ").lower() != 'y':
        print(f"{RED}❌ Обработка отменена.")
        sys.exit(1)
    return datetime.now(timezone.utc).date()


def select_file():
    files = [f for f in os.listdir(LOGS_DIR) if f.endswith('.json')]
    if not files:
        print(f"{RED}❌ Нет JSON файлов в директории logs/.")
        return None

    files_with_date, files_without_date = [], []
    for f in files:
        date = parse_date_from_filename(os.path.join(LOGS_DIR, f))
        (files_with_date if date else files_without_date).append((date, f))

    files_with_date.sort(key=lambda x: x[0], reverse=True)
    files_without_date.sort(key=lambda x: x[1])
    sorted_files = files_with_date + files_without_date

    print(f"{YEL}📁 Доступные файлы:")
    for i, (_, f) in enumerate(sorted_files, 1):
        print(f" {get_emoji(i)}  {f}")
    try:
        choice = int(input(" ➡️  Введите номер файла: ")) - 1
        if 0 <= choice < len(sorted_files):
            return os.path.join(LOGS_DIR, sorted_files[choice][1])
        print(f"{RED}❌ Неверный выбор.")
    except ValueError:
        print(f"{RED}❌ Введите число.")
    return None


def load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"{RED}❌ Ошибка загрузки JSON: {e}")
        return None


def print_intro():
    logo = [
        "     ██╗██╗██████╗  █████╗ ██╗      ██████╗  ██████╗ ",
        "     ██║██║██╔══██╗██╔══██╗██║     ██╔═══██╗██╔════╝ ",
        "     ██║██║██████╔╝███████║██║     ██║   ██║██║  ███╗",
        "██   ██║██║██╔══██╗██╔══██║██║     ██║   ██║██║   ██║",
        "╚█████╔╝██║██║  ██║██║  ██║███████╗╚██████╔╝╚██████╔╝",
        " ╚════╝ ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝  ╚═════╝ ",
    ]
    WIDTH = 45
    INNER = WIDTH * 2 - 5
    border = f"{YEL}" + "✨" * WIDTH
    max_logo_w = max(len(line) for line in logo)
    logo_inner_w = max_logo_w + 4
    logo_left  = (INNER - logo_inner_w) // 2
    logo_right = INNER - logo_left - logo_inner_w
    _logo_row = f"{YEL}✨{BBLU}{' ' * (INNER + 1)}{BRST}{YEL}✨"

    print(border)
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


def main():
    if not JIRA_BASE_URL or not JIRA_USERNAME or not JIRA_API_TOKEN:
        print(f"{RED}❌ Ошибка: Установите переменные окружения JIRA_BASE_URL, JIRA_USERNAME и JIRA_API_TOKEN.")
        sys.exit(1)

    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    parser = argparse.ArgumentParser(description="Загрузка worklog в Jira из JSON файла.")
    parser.add_argument('--dry-run', action='store_true', help="Симуляция без реальных изменений")
    dry_run = parser.parse_args().dry_run

    print_intro()

    file_path = select_file()
    if not file_path:
        sys.exit(1)
    data = load_json(file_path)
    if not data:
        sys.exit(1)

    file_date = parse_date_from_filename(file_path)
    start_time = datetime.combine(file_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=6)
    started = start_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '+0000'

    reports = {'success': [], 'failed': [], 'skipped': []}
    total_logged_seconds = [0]
    dry_run_messages = []

    grouped_laps, invalid_laps = group_laps(data['laps'])
    grouped_laps = adjust_laps_to_full_minutes(grouped_laps)
    for lap in invalid_laps:
        reports['failed'].append(f"Не найден ISSUE_ID в: {lap['text']}")

    total = len(grouped_laps)
    for i, lap in enumerate(grouped_laps, 1):
        process_lap(lap, started, reports, total_logged_seconds, dry_run_messages, dry_run)
        sys.stdout.write(f"\n\r{YEL} 🔄 Обработка: {i}/{total} задач ")
        sys.stdout.flush()
    print()

    if dry_run:
        print(f"{CYN}🔍 Dry-run симуляция:")
        for msg in dry_run_messages:
            print(f"{CYN}{msg}")
        print()

    print_report(reports, total_logged_seconds, started, total, dry_run)

    if input("Сохранить отчет в файл? (y/n): ").lower() == 'y':
        save_report(reports, total_logged_seconds, started, total, dry_run, file_date, REPORTS_DIR)


if __name__ == '__main__':
    main()
