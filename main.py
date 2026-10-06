"""Hourly lead scoring entry point."""

from datetime import datetime
import time

from b24_client import get_recent_leads
from lead_processor import process_lead, process_dynamic_lead


def run() -> None:
    print("\n" + "#" * 60)
    print(f"🚀 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 60)

    leads = get_recent_leads(days=21)
    if not leads:
        print("📭 Нет лидов для обработки")
        return

    print(f"📋 Лидов для проверки: {len(leads)}")

    stats = {
        "initial_sent": 0,
        "initial_other": 0,
        "dynamic_ok": 0,
        "dynamic_skip": 0,
        "error": 0,
    }

    for index, lead in enumerate(leads, 1):
        lead_id = lead.get("ID")
        print(f"\n[{index}/{len(leads)}] lead={lead_id}")

        try:
            initial_status = process_lead(lead)
            if initial_status == "sent":
                stats["initial_sent"] += 1
            else:
                stats["initial_other"] += 1

            dynamic_status = process_dynamic_lead(lead)
            if dynamic_status == "ok":
                stats["dynamic_ok"] += 1
            else:
                stats["dynamic_skip"] += 1

        except Exception as exc:
            print(f"❌ Критическая ошибка лида {lead_id}: {exc}")
            stats["error"] += 1

        time.sleep(0.25)

    print("\n" + "=" * 60)
    print("📊 ИТОГИ")
    for name, value in stats.items():
        print(f"  {name}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    run()
