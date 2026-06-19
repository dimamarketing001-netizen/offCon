from typing import Optional, List, Dict
import re
from b24_client import get_calls_for_lead, update_lead
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
    FIELD_GPT_RESULT
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

    # 4. Анализируем звонки
    print(f"   🔍 Проверяем звонки...")
    calls = get_calls_for_lead(lead_id)

    if not calls:
        print("   ❌ Нет подходящих звонков")
        return 'no_calls'

    for call in calls:
        call_id    = call.get('ID')
        record_url = call.get('CALL_RECORD_URL')
        duration   = call.get('CALL_DURATION')

        print(f"\n   📞 Звонок ID={call_id}, {duration}с")

        transcript = process_call_audio(record_url, call_id)
        if not transcript:
            continue

        full_text = transcript.get('full_text', '')
        print(f"   📄 Текст ({len(full_text)} симв): {full_text[:200]}")

        # Groq анализ
        analysis = analyze_transcript(full_text, full_text)

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
                result_text=f"Звонок {call_id} | {city} | {debt} | {full_text[:200]}",
                metrika_sent=sent
            )
            return 'sent' if sent else 'metrika_error'

    print(f"   ❌ Не квалифицирован")
    mark_lead(lead_id, qualified=False,
              result_text="Не квалифицирован после анализа звонков",
              metrika_sent=False)
    return 'not_qualified'