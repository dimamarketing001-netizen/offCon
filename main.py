"""
Точка входа
Запускается каждые 5 минут через cron
"""

import time
import schedule
from datetime import datetime
from b24_client import get_leads_last_21_days
from lead_processor import process_lead
from config import B24_WEBHOOK


def run_processing():
    """Основной цикл обработки"""

    print(f"\n{'#' * 60}")
    print(f"🚀 Запуск обработки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}")

    # Получаем лиды
    leads = get_leads_last_21_days()

    if not leads:
        print("📭 Нет лидов для обработки")
        return

    # Статистика
    stats = {
        'sent': 0,
        'not_qualified': 0,
        'no_calls': 0,
        'no_audio': 0,
        'no_identifiers': 0,
        'error': 0
    }

    # Обрабатываем каждый лид
    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{len(leads)}]")

        try:
            status = process_lead(lead)
            stats[status] = stats.get(status, 0) + 1
        except Exception as e:
            print(f"❌ Критическая ошибка лида {lead.get('ID')}: {e}")
            stats['error'] += 1

        # Пауза между лидами чтобы не перегружать API
        time.sleep(1)

    # Итоги
    print(f"\n{'=' * 50}")
    print(f"📊 ИТОГИ:")
    print(f"  ✅ Отправлено в Метрику: {stats['sent']}")
    print(f"  ❌ Не квалифицированы:  {stats['not_qualified']}")
    print(f"  📵 Нет звонков:         {stats['no_calls']}")
    print(f"  🔇 Нет аудио:           {stats['no_audio']}")
    print(f"  🔑 Нет идентификаторов: {stats['no_identifiers']}")
    print(f"  💥 Ошибки:              {stats['error']}")
    print(f"{'=' * 50}")


def setup_ai_engine():
    """
    Регистрируем AI Engine в Б24 (один раз!)
    Раскомментируйте и запустите один раз
    """
    from ai_engine_endpoint import register_ai_engine

    YOUR_SERVER_URL = "https://ваш-сервер.ru"

    register_ai_engine(
        b24_webhook=B24_WEBHOOK,
        completions_url=f"{YOUR_SERVER_URL}/health"  # Для проверки
    )


if __name__ == '__main__':
    import sys

    if '--register-engine' in sys.argv:
        # python main.py --register-engine
        setup_ai_engine()

    elif '--once' in sys.argv:
        # python main.py --once (разовый запуск)
        run_processing()

    else:
        # Запуск по расписанию каждые 5 минут
        print("⏰ Планировщик запущен (каждые 5 минут)")

        schedule.every(5).minutes.do(run_processing)

        # Сразу запускаем при старте
        run_processing()

        while True:
            schedule.run_pending()
            time.sleep(30)