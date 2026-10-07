"""Hourly lead scoring entry point."""

import argparse
from datetime import datetime
import time

from b24_client import get_recent_leads
from lead_processor import (
    process_lead,
    process_dynamic_lead,
    reset_run_stats,
    get_run_stats,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Обработка и повторный скоринг лидов Битрикс24 за заданное количество часов."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="За сколько последних часов брать лиды из Битрикс24 (по умолчанию: 24).",
    )
    args = parser.parse_args()

    if args.hours <= 0:
        parser.error("--hours должен быть больше 0")

    return args


def run(hours: int = 24) -> None:
    print("\n" + "#" * 60)
    print(f"🚀 Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🕒 Период: последние {hours} ч.")
    print("#" * 60)

    reset_run_stats()
    leads = get_recent_leads(hours=hours)
    if not leads:
        print("📭 Нет лидов для обработки")
        return

    print(f"📋 Лидов для проверки: {len(leads)}")

    errors = 0

    for index, lead in enumerate(leads, 1):
        lead_id = lead.get("ID")
        print(f"\n[{index}/{len(leads)}] lead={lead_id}")

        try:
            process_lead(lead)
            process_dynamic_lead(lead)

        except Exception as exc:
            print(f"❌ Критическая ошибка лида {lead_id}: {exc}")
            errors += 1

        time.sleep(0.25)

    stats = get_run_stats()

    print("\n" + "=" * 60)
    print("📊 ИТОГИ ЗА ЗАПУСК")
    print(f"Всего найдено лидов: {len(leads)}")

    print("\n🧮 БАЗОВЫЙ СКОРИНГ")
    print(f"  Впервые просчитано: {stats['initial_scored']}")
    print(f"  STOP-лидов: {stats['initial_stop']}")
    print(f"  Уже были просчитаны ранее: {stats['initial_already_scored']}")
    print(f"  Не распознана анкета / нет ответов: {stats['initial_no_answers']}")
    print(f"  Нет подходящей UTM-кампании в маппинге: {stats['initial_no_utm']}")

    print("\n📈 ДИНАМИЧЕСКИЙ СКОРИНГ")
    print(f"  Регион +500: {stats['dynamic_region']}")
    print(f"  Назначена встреча +300: {stats['dynamic_meeting']}")
    print(f"  Визит +500: {stats['dynamic_visit']}")
    print(f"  Договор +3000: {stats['dynamic_contract']}")
    print(f"  Оплата +10000: {stats['dynamic_payment']}")
    print(f"  Без новых событий: {stats['dynamic_no_change']}")
    print(f"  Пропущено — базовый скоринг ещё не был сделан: {stats['dynamic_skip_not_scored']}")
    print(f"  Пропущено — STOP-лид: {stats['dynamic_skip_stop']}")
    print(f"  Пропущено — кампания в исключениях: {stats['dynamic_skip_campaign']}")

    print("\n🎯 ЯНДЕКС МЕТРИКА")
    print(f"  Уникальных лидов успешно отправлено: {stats['metrika_unique_leads']}")
    print(f"  Успешных отправок конверсий: {stats['metrika_success']}")
    print(f"  Ошибок отправки в Метрику: {stats['metrika_failed']}")
    print(f"  Не отправлено — нет идентификатора Метрики/телефона: {stats['metrika_no_id']}")
    print(f"  Не отправлено — нет счётчика для UTM-кампании: {stats['metrika_no_config']}")

    print("\n🧩 СТАРАЯ ЛОГИКА КВАЛИФИКАЦИИ")
    print(f"  Успешно отправлено: {stats['legacy_sent']}")
    print(f"  Ошибка отправки: {stats['legacy_failed']}")
    print(f"  Нет ym_uid/yclid: {stats['legacy_no_id']}")

    print(f"\n❌ Ошибок обработки Python: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    args = parse_args()
    run(hours=args.hours)
