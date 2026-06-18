"""
Основная логика обработки лида
"""

import re
from b24_client import get_calls_for_lead, update_lead
from audio_processor import process_call_audio
from groq_client import analyze_transcript
from metrika_client import send_conversion
from config import (
    QUALIFIED_STATUSES,
    MIN_CALL_DURATION,
    FIELD_METRIKA_SENT,
    FIELD_GPT_CITY,
    FIELD_GPT_DEBT,
    FIELD_GPT_QUALIFIED,
    FIELD_GPT_RESULT
)


def parse_ym_uid(comments: str) -> str | None:
    """Извлекаем _ym_uid из COMMENTS"""
    match = re.search(r'_ym_uid=(\d+)', comments or '')
    return match.group(1) if match else None


def get_phone(lead: dict) -> str | None:
    """Извлекаем телефон из лида"""
    phones = lead.get('PHONE', [])
    if phones and isinstance(phones, list):
        return phones[0].get('VALUE')
    return None


def mark_lead(lead_id: str, qualified: bool, city: str = None,
              debt: float = None, result_text: str = None,
              metrika_sent: bool = False):
    """Обновляем поля лида в Б24"""
    fields = {
        FIELD_GPT_QUALIFIED: "Y" if qualified else "N",
        FIELD_METRIKA_SENT:  "Y" if metrika_sent else "N",
        FIELD_GPT_CITY:      city or '',
        FIELD_GPT_DEBT:      debt or 0,
        FIELD_GPT_RESULT:    result_text or ''
    }
    update_lead(lead_id, fields)


def process_lead(lead: dict) -> str:
    """
    Обрабатываем один лид.
    Возвращает статус: sent | qualified_no_id | not_qualified |
                       no_calls | no_transcript | error
    """
    lead_id    = lead.get('ID')
    status_id  = lead.get('STATUS_ID')
    comments   = lead.get('COMMENTS', '')

    print(f"\n{'='*55}")
    print(f"📋 Лид ID={lead_id} | Статус={status_id}")

    # Извлекаем идентификаторы
    ym_uid = parse_ym_uid(comments)
    phone  = get_phone(lead)

    print(f"   _ym_uid: {ym_uid or '❌'} | Телефон: {phone or '❌'}")

    # ===================================================
    # ПУТЬ 1: Статус уже квалифицированный
    # ===================================================
    if status_id in QUALIFIED_STATUSES:
        print(f"   ✅ Статус квалифицирован: {status_id}")

        if not any([ym_uid, phone]):
            print("   ⚠️ Нет идентификаторов → не отправляем в Метрику")
            mark_lead(lead_id, qualified=True,
                      result_text=f"Квалифицирован по статусу: {status_id}",
                      metrika_sent=False)
            return 'qualified_no_id'

        sent = send_conversion(client_id=ym_uid, phone=phone)
        mark_lead(lead_id, qualified=True,
                  result_text=f"Квалифицирован по статусу: {status_id}",
                  metrika_sent=sent)

        return 'sent' if sent else 'metrika_error'

    # ===================================================
    # ПУТЬ 2: Анализируем звонки
    # ===================================================
    print(f"   🔍 Статус не квалифицирован → проверяем звонки")

    calls = get_calls_for_lead(lead_id)

    # Фильтруем: только звонки > MIN_CALL_DURATION с записью
    good_calls = [
        c for c in calls
        if int(c.get('CALL_DURATION', 0) or 0) >= MIN_CALL_DURATION
        and c.get('CALL_RECORD_URL')
    ]

    print(f"   Всего звонков: {len(calls)} | "
          f"Подходящих (>{MIN_CALL_DURATION}с): {len(good_calls)}")

    if not good_calls:
        print("   ❌ Нет подходящих звонков")
        return 'no_calls'

    # Обрабатываем каждый звонок пока не найдём квалифицированный
    for call in good_calls:
        call_id      = call.get('ID')
        record_url   = call.get('CALL_RECORD_URL')
        duration     = call.get('CALL_DURATION')

        print(f"\n   📞 Звонок ID={call_id}, {duration}с")

        # Транскрибация
        transcript = process_call_audio(record_url, call_id)

        if not transcript:
            print(f"   ⚠️ Нет транскрипта, пропускаем")
            continue

        client_text  = transcript.get('client', '')
        manager_text = transcript.get('manager', '')

        print(f"   📝 Клиент: {client_text[:100]}")
        print(f"   📝 Менеджер: {manager_text[:100]}")

        # GPT анализ
        analysis = analyze_transcript(client_text, manager_text)

        if analysis.get('qualified'):
            city   = analysis.get('city')
            debt   = analysis.get('debt_amount')
            result = (f"Звонок {call_id} | "
                      f"Город: {city} | "
                      f"Долг: {debt} | "
                      f"Клиент: {client_text[:200]}")

            print(f"   ✅ КВАЛИФИЦИРОВАН! Город={city}, Долг={debt}")

            if not any([ym_uid, phone]):
                print("   ⚠️ Нет идентификаторов для Метрики")
                mark_lead(lead_id, qualified=True,
                          city=city, debt=debt,
                          result_text=result,
                          metrika_sent=False)
                return 'qualified_no_id'

            sent = send_conversion(client_id=ym_uid, phone=phone)
            mark_lead(lead_id, qualified=True,
                      city=city, debt=debt,
                      result_text=result,
                      metrika_sent=sent)

            return 'sent' if sent else 'metrika_error'

    # Ни один звонок не дал квалификацию
    print(f"   ❌ Лид не квалифицирован после анализа {len(good_calls)} звонков")
    mark_lead(lead_id, qualified=False,
              result_text="Не квалифицирован после анализа звонков",
              metrika_sent=False)

    return 'not_qualified'