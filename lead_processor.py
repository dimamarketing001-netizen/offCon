from typing import Optional, List, Dict
import re
from b24_client import get_calls_for_lead, update_lead, b24_request
from audio_processor import process_call_audio
from groq_client import analyze_transcript
from metrika_client import send_conversion
from config import (
    QUALIFIED_STATUSES,
    COMPANY_METRIKA_MAP,
    FIELD_METRIKA_SENT,
    FIELD_GPT_CITY,
    FIELD_GPT_DEBT,
    FIELD_GPT_QUALIFIED,
    FIELD_GPT_RESULT,
    FIELD_TRANSCRIPT
)


def parse_ym_uid(comments: str) -> Optional[str]:
    match = re.search(r'_ym_uid=(\d+)', comments or '')
    return match.group(1) if match else None


def get_phone(lead: dict) -> Optional[str]:
    phones = lead.get('PHONE', [])
    if phones and isinstance(phones, list):
        return phones[0].get('VALUE')
    return None


def get_metrika_config(lead: dict) -> Optional[dict]:
    utm_campaign = (lead.get('UTM_CAMPAIGN') or '').strip()

    if not utm_campaign:
        print(f"   ⏭️ Нет UTM_CAMPAIGN — пропускаем")
        return None

    config = COMPANY_METRIKA_MAP.get(utm_campaign)
    if not config:
        print(f"   ⏭️ UTM_CAMPAIGN={utm_campaign} не найден в маппинге")
        return None

    print(f"   ✅ UTM_CAMPAIGN={utm_campaign} → counter={config['counter_id']}")
    return config


def parse_transcript_field(transcript_field: str) -> dict:
    """
    Парсим поле транскрипта
    Формат хранения:
    [call:271856]
    текст транскрипта...
    ---
    [call:272470]
    текст транскрипта...

    Возвращает: {call_id: text, ...}
    """
    result = {}
    if not transcript_field:
        return result

    # Разбиваем по блокам звонков
    blocks = re.split(r'\[call:(\d+)\]', transcript_field)

    # blocks[0] — текст до первого маркера (пустой)
    # blocks[1] — id первого звонка
    # blocks[2] — текст первого звонка
    # blocks[3] — id второго звонка и т.д.

    i = 1
    while i < len(blocks) - 1:
        call_id = blocks[i].strip()
        text = blocks[i + 1].strip().rstrip('---').strip()
        if call_id and text:
            result[call_id] = text
        i += 2

    return result


def build_transcript_field(transcripts: dict) -> str:
    """
    Собираем поле транскрипта из словаря
    {call_id: text, ...} → строка для сохранения в Б24
    """
    parts = []
    for call_id, text in transcripts.items():
        parts.append(f"[call:{call_id}]\n{text}")
    return "\n---\n".join(parts)


def mark_lead(lead_id: str, qualified: bool, city: str = None,
              debt: float = None, result_text: str = None,
              metrika_sent: bool = False):
    fields = {
        FIELD_GPT_QUALIFIED: True if qualified else False,
        FIELD_METRIKA_SENT: True if metrika_sent else False,
        FIELD_GPT_CITY: city or '',
        FIELD_GPT_DEBT: debt or 0,
        FIELD_GPT_RESULT: result_text or ''
    }
    result = update_lead(lead_id, fields)
    if result:
        print(f"   💾 Лид {lead_id} обновлён в Б24")
    else:
        print(f"   ❌ Ошибка обновления лида {lead_id}")


def save_transcripts(lead_id: str, transcripts: dict):
    """Сохраняем все транскрипты в поле Б24"""
    text = build_transcript_field(transcripts)
    b24_request("crm.lead.update", {
        "id": lead_id,
        "fields": {FIELD_TRANSCRIPT: text}
    })
    print(f"   💾 Транскрипты сохранены: {len(transcripts)} звонков, {len(text)} симв")


def process_lead(lead: dict) -> str:
    lead_id = lead.get('ID')
    status_id = lead.get('STATUS_ID')
    comments = lead.get('COMMENTS', '')

    print(f"\n{'=' * 55}")
    print(f"📋 Лид ID={lead_id} | Статус={status_id}")
    print(f"   UTM_CAMPAIGN: {lead.get('UTM_CAMPAIGN') or '❌ нет'}")

    # 1. Проверяем UTM_CAMPAIGN
    metrika_cfg = get_metrika_config(lead)
    if not metrika_cfg:
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: нет UTM_CAMPAIGN в маппинге")
        return 'no_utm'

    # 2. Проверяем _ym_uid
    ym_uid = parse_ym_uid(comments)
    phone = get_phone(lead)

    print(f"   _ym_uid: {ym_uid or '❌'} | Телефон: {phone or '❌'}")

    if not ym_uid:
        print(f"   ⏭️ Нет _ym_uid — пропускаем")
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: нет _ym_uid")
        return 'no_ymuid'

    # 3. Статус уже квалифицирован — сразу в Метрику
    if status_id in QUALIFIED_STATUSES:
        print(f"   ✅ Статус квалифицирован: {status_id}")
        sent = send_conversion(
            counter_id=metrika_cfg['counter_id'],
            token=metrika_cfg['token'],
            client_id=ym_uid,
            phone=phone
        )
        mark_lead(lead_id, qualified=True,
                  result_text=f"Квалифицирован по статусу: {status_id}",
                  metrika_sent=sent)
        return 'sent' if sent else 'metrika_error'

    # 4. Загружаем уже сохранённые транскрипты из Б24
    transcript_field = lead.get(FIELD_TRANSCRIPT, '') or ''
    saved_transcripts = parse_transcript_field(transcript_field)

    print(f"   📄 Сохранённых транскриптов: {len(saved_transcripts)} звонков")
    for call_id in saved_transcripts:
        print(f"      - call:{call_id} ({len(saved_transcripts[call_id])} симв)")

    # 5. Получаем звонки лида
    print(f"   🔍 Проверяем звонки...")
    calls = get_calls_for_lead(lead_id)

    if not calls and not saved_transcripts:
        print("   ❌ Нет звонков и нет сохранённых транскриптов")
        return 'no_calls'

    # 6. Транскрибируем новые звонки
    new_transcribed = False

    for call in calls:
        call_id = str(call.get('ID'))
        record_url = call.get('CALL_RECORD_URL')
        duration = call.get('CALL_DURATION')

        # Уже транскрибировали этот звонок?
        if call_id in saved_transcripts:
            print(f"   ⏭️ Звонок {call_id} уже транскрибирован — пропускаем")
            continue

        print(f"\n   📞 Новый звонок ID={call_id}, {duration}с — транскрибируем...")

        transcript = process_call_audio(record_url, call_id)
        if not transcript:
            print(f"   ⚠️ Не удалось транскрибировать звонок {call_id}")
            continue

        full_text = transcript.get('full_text', '')
        if full_text:
            saved_transcripts[call_id] = full_text
            new_transcribed = True
            print(f"   ✅ Звонок {call_id} транскрибирован: {len(full_text)} симв")

    # 7. Сохраняем обновлённые транскрипты в Б24
    if new_transcribed:
        save_transcripts(lead_id, saved_transcripts)

    # 8. Если нет ни одного транскрипта
    if not saved_transcripts:
        print("   ❌ Нет транскриптов для анализа")
        return 'no_calls'

    # 9. Собираем весь текст для анализа
    all_text = "\n\n".join([
        f"[Звонок {call_id}]\n{text}"
        for call_id, text in saved_transcripts.items()
    ])

    print(f"\n   🤖 Отправляем в Groq ({len(all_text)} симв)...")
    print(f"   Текст: {all_text[:300]}")

    # 10. Анализируем через Groq
    analysis = analyze_transcript(all_text)

    if analysis.get('qualified'):
        city = analysis.get('city')
        debt = analysis.get('debt_amount')

        print(f"   ✅ КВАЛИФИЦИРОВАН! Город={city}, Долг={debt}")

        sent = send_conversion(
            counter_id=metrika_cfg['counter_id'],
            token=metrika_cfg['token'],
            client_id=ym_uid,
            phone=phone
        )
        mark_lead(
            lead_id, qualified=True,
            city=city, debt=debt,
            result_text=f"{city} | {debt} | {all_text[:300]}",
            metrika_sent=sent
        )
        return 'sent' if sent else 'metrika_error'

    # 11. Не квалифицирован
    print(f"   ❌ Не квалифицирован")
    mark_lead(lead_id, qualified=False,
              result_text="Не квалифицирован после анализа звонков")
    return 'not_qualified'