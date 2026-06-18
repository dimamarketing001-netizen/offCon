"""
Основная бизнес логика обработки лида
"""

from b24_client import (
    get_calls_for_lead,
    get_call_record_url,
    update_lead
)
from groq_client import (
    transcribe_audio,
    analyze_call_text,
    parse_ym_uid_from_comments
)
from metrika_client import send_conversion
from config import (
    MIN_CALL_DURATION,
    FIELD_METRIKA_SENT,
    FIELD_GPT_CITY,
    FIELD_GPT_DEBT,
    FIELD_GPT_QUALIFIED,
    FIELD_GPT_RESULT
)


def process_lead(lead: dict) -> str:
    """
    Обрабатываем один лид
    Возвращает статус: 'sent', 'not_qualified', 'no_calls', 'no_audio', 'error'
    """

    lead_id = lead.get('ID')
    comments = lead.get('COMMENTS', '')

    print(f"\n{'=' * 50}")
    print(f"🔍 Обрабатываем лид ID={lead_id}")

    # ШАГ 1: Проверяем звонки
    calls = get_calls_for_lead(lead_id)

    if not calls:
        print(f"📵 Лид {lead_id}: нет звонков, пропускаем")
        return 'no_calls'

    # Ищем успешный звонок с нормальной длительностью
    suitable_call = None

    for call in calls:
        duration = int(call.get('CALL_DURATION', 0) or call.get('DURATION', 0))
        record_url = call.get('RECORD_URL', '')

        print(f"  📞 Звонок: длительность={duration}с, запись={'есть' if record_url else 'нет'}")

        if duration >= MIN_CALL_DURATION and record_url:
            suitable_call = call
            break  # Берём первый подходящий

    if not suitable_call:
        print(f"❌ Лид {lead_id}: нет подходящих звонков (длит < {MIN_CALL_DURATION}с или нет записи)")
        return 'no_calls'

    record_url = suitable_call.get('RECORD_URL')

    # ШАГ 2: Транскрибация
    print(f"🎵 Транскрибируем звонок...")
    transcript = transcribe_audio(record_url)

    if not transcript:
        print(f"❌ Лид {lead_id}: не удалось транскрибировать")
        return 'no_audio'

    # ШАГ 3: GPT анализ
    print(f"🤖 Анализируем текст через GPT...")
    analysis = analyze_call_text(transcript)

    city = analysis.get('city')
    debt_amount = analysis.get('debt_amount')
    is_qualified = analysis.get('qualified', False)

    # ШАГ 4: Обновляем лид в Б24 (в любом случае)
    update_fields = {
        FIELD_GPT_CITY: city or '',
        FIELD_GPT_DEBT: debt_amount or 0,
        FIELD_GPT_QUALIFIED: 1 if is_qualified else 0,
        FIELD_GPT_RESULT: f"Город: {city}, Долг: {debt_amount}, Транскрипт: {transcript[:200]}"
    }

    if not is_qualified:
        update_fields[FIELD_METRIKA_SENT] = 0  # Не отправляем, но помечаем как обработан
        update_lead(lead_id, update_fields)
        print(f"❌ Лид {lead_id}: не квалифицирован (город={city}, долг={debt_amount})")
        return 'not_qualified'

    # ШАГ 5: Извлекаем _ym_uid
    ym_uid = parse_ym_uid_from_comments(comments)

    # Получаем телефон из лида
    phone = None
    phones = lead.get('PHONE', [])
    if phones and isinstance(phones, list):
        phone = phones[0].get('VALUE')

    # ШАГ 6: Отправляем в Метрику
    if not any([ym_uid, phone]):
        print(f"⚠️ Лид {lead_id}: квалифицирован но нет идентификаторов для Метрики")
        update_fields[FIELD_METRIKA_SENT] = 0
        update_lead(lead_id, update_fields)
        return 'no_identifiers'

    success, response = send_conversion(
        client_id=ym_uid,
        phone=phone
    )

    # ШАГ 7: Помечаем лид
    update_fields[FIELD_METRIKA_SENT] = 1 if success else 0
    update_lead(lead_id, update_fields)

    if success:
        print(f"✅ Лид {lead_id}: ОТПРАВЛЕН В МЕТРИКУ! Город={city}, Долг={debt_amount}")
        return 'sent'
    else:
        print(f"❌ Лид {lead_id}: ошибка отправки в Метрику")
        return 'error'