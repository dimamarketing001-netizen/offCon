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


def get_existing_transcript(lead: dict) -> str:
    """Берём уже сохранённый транскрипт из поля Б24"""
    return (lead.get(FIELD_TRANSCRIPT) or '').strip()


def save_transcript(lead_id: str, new_text: str, existing_text: str):
    """
    Добавляем новый транскрипт к существующему
    Не перезаписываем — дописываем
    """
    if existing_text:
        combined = existing_text + "\n---\n" + new_text
    else:
        combined = new_text

    b24_request("crm.lead.update", {
        "id": lead_id,
        "fields": {FIELD_TRANSCRIPT: combined}
    })
    print(f"   💾 Транскрипт сохранён в Б24 ({len(combined)} симв)")
    return combined


def mark_lead(lead_id: str, qualified: bool, city: str = None,
              debt: float = None, result_text: str = None,
              metrika_sent: bool = False):
    fields = {
        FIELD_GPT_QUALIFIED: "Y" if qualified else "N",
        FIELD_METRIKA_SENT:  "Y" if metrika_sent else "N",
        FIELD_GPT_CITY:      city or '',
        FIELD_GPT_DEBT:      debt or 0,
        FIELD_GPT_RESULT:    result_text or ''
    }
    update_lead(lead_id, fields)


def process_lead(lead: dict) -> str:
    lead_id   = lead.get('ID')
    status_id = lead.get('STATUS_ID')
    comments  = lead.get('COMMENTS', '')

    print(f"\n{'='*55}")
    print(f"📋 Лид ID={lead_id} | Статус={status_id}")
    print(f"   UTM_CAMPAIGN: {lead.get('UTM_CAMPAIGN') or '❌ нет'}")

    # 1. Проверяем UTM_CAMPAIGN
    metrika_cfg = get_metrika_config(lead)
    if not metrika_cfg:
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: нет UTM_CAMPAIGN в маппинге",
                  metrika_sent=False)
        return 'no_utm'

    # 2. Проверяем _ym_uid
    ym_uid = parse_ym_uid(comments)
    phone  = get_phone(lead)

    print(f"   _ym_uid: {ym_uid or '❌'} | Телефон: {phone or '❌'}")

    if not ym_uid:
        print(f"   ⏭️ Нет _ym_uid — пропускаем")
        mark_lead(lead_id, qualified=False,
                  result_text="Пропущен: нет _ym_uid",
                  metrika_sent=False)
        return 'no_ymuid'

    # 3. Статус уже квалифицирован
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

    # 4. Берём существующий транскрипт из Б24
    existing_transcript = get_existing_transcript(lead)
    if existing_transcript:
        print(f"   📄 Найден сохранённый транскрипт: {len(existing_transcript)} симв")

    # 5. Анализируем звонки — транскрибируем новые
    print(f"   🔍 Проверяем звонки...")
    calls = get_calls_for_lead(lead_id)

    new_transcript_parts = []

    if calls:
        for call in calls:
            call_id    = call.get('ID')
            record_url = call.get('CALL_RECORD_URL')
            duration   = call.get('CALL_DURATION')

            # Проверяем не транскрибировали ли уже этот звонок
            call_marker = f"[call:{call_id}]"
            if call_marker in existing_transcript:
                print(f"   ⏭️ Звонок {call_id} уже транскрибирован — пропускаем")
                continue

            print(f"\n   📞 Звонок ID={call_id}, {duration}с")

            transcript = process_call_audio(record_url, call_id)
            if not transcript:
                continue

            full_text = transcript.get('full_text', '')
            if full_text:
                # Добавляем маркер звонка
                marked_text = f"{call_marker}\n{full_text}"
                new_transcript_parts.append(marked_text)
                print(f"   📝 Новый транскрипт: {len(full_text)} симв")

    # 6. Если есть новые транскрипты — сохраняем в Б24
    combined_transcript = existing_transcript
    if new_transcript_parts:
        new_text = "\n---\n".join(new_transcript_parts)
        combined_transcript = save_transcript(
            lead_id, new_text, existing_transcript
        )

    # 7. Если нет транскрипта вообще — пропускаем
    if not combined_transcript:
        print("   ❌ Нет транскрипта для анализа")
        return 'no_calls'

    # 8. Отправляем весь накопленный текст в Groq
    print(f"\n   🤖 Анализируем текст ({len(combined_transcript)} симв)...")
    analysis = analyze_transcript(combined_transcript)

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
            result_text=f"{city} | {debt} | {combined_transcript[:200]}",
            metrika_sent=sent
        )
        return 'sent' if sent else 'metrika_error'

    print(f"   ❌ Не квалифицирован")
    mark_lead(lead_id, qualified=False,
              result_text="Не квалифицирован",
              metrika_sent=False)
    return 'not_qualified'