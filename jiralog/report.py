import os
from .config import RED, YEL, CYN, GRN, BLU
from .processor import format_time


def print_report(reports, total_logged_seconds, started, total, dry_run):
    mode = "DRY-RUN" if dry_run else "REAL"
    success_count = len(reports['success'])
    failed_count  = len(reports['failed'])
    skipped_count = len(reports['skipped'])

    if failed_count == 0 and skipped_count == 0:
        global_status = f"{GRN}✅ Успех"
    elif success_count > 0:
        global_status = f"{YEL}⚠️ Есть ошибки"
    else:
        global_status = f"{RED}❌ Провал"

    print(f"\n{YEL}📊 Глобальный отчет ({mode}): {global_status}")
    print(f"{CYN}📅 Дата и время обрабатываемого дня: {started}")
    print(f"{BLU}🧮 Обработано: {total}, Успешно: {success_count}, Пропущено: {skipped_count}, Ошибок: {failed_count}")
    print(f"{GRN}🕒 Общая сумма залогированного времени: {format_time(total_logged_seconds[0])}")

    print(f"\n{YEL}📝 Отчет по записям:")
    for item in reports['success']:
        print(f"{GRN}✅ Успех: {item}")
    for item in reports['skipped']:
        print(f"{YEL}⏭️  Пропущено: {item}")
    for item in reports['failed']:
        print(f"{RED}❌ Ошибка: {item}")

    return success_count, failed_count, skipped_count


def save_report(reports, total_logged_seconds, started, total, dry_run, file_date, reports_dir):
    mode = "DRY-RUN" if dry_run else "REAL"
    success_count = len(reports['success'])
    failed_count  = len(reports['failed'])
    skipped_count = len(reports['skipped'])

    if failed_count == 0 and skipped_count == 0:
        status = 'Успех'
    elif success_count > 0:
        status = 'Есть ошибки'
    else:
        status = 'Провал'

    report_filename = os.path.join(reports_dir, f"{file_date.strftime('%d.%m.%Y')}_report.txt")
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(f"Глобальный отчет ({mode}): {status}\n")
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
