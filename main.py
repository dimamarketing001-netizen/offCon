"""
Точка входа — запуск каждые 5 минут
"""

import time
import schedule
from datetime import datetime
from b24_client import get_unprocessed_leads
from lead_processor import process_lead
from typing import Optional, List, Dict

def run():
    print(f"\n{'#'*55}")
    print(f"🚀 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*55}")

    leads = get_unprocessed_leads()

    if not leads:
        print("📭 Нет лидов для обработки")
        return

    print(f"📋 Лидов для обработки: {len(leads)}")

    stats = {
        'sent':            0,
        'qualified_no_id': 0,
        'not_qualified':   0,
        'no_calls':        0,
        'no_transcript':   0,
        'metrika_error':   0,
        'error':           0
    }

    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{len(leads)}]")

        try:
            status = process_lead(lead)
            stats[status] = stats.get(status, 0) + 1
        except Exception as e:
            print(f"❌ Критическая ошибка лида {lead.get('ID')}: {e}")
            stats['error'] += 1

        time.sleep(1)

    print(f"\n{'='*55}")
    print(f"📊 ИТОГИ:")
    for k, v in stats.items():
        emoji = '✅' if k == 'sent' else '📊'
        print(f"  {emoji} {k}: {v}")
    print(f"{'='*55}")


if __name__ == '__main__':
    import sys

    if '--once' in sys.argv:
        run()
    else:
        print("⏰ Планировщик запущен (каждые 5 минут)")
        schedule.every(5).minutes.do(run)
        run()
        while True:
            schedule.run_pending()
            time.sleep(30)