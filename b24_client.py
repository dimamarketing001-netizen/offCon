from typing import Optional, List, Dict
import requests
import time
import urllib3
from datetime import datetime, timedelta
from config import B24_WEBHOOK

urllib3.disable_warnings()

def b24_request(method: str, params: dict = None) -> dict:
    """Базовый запрос к Б24"""
    url = f"{B24_WEBHOOK}{method}.json"

    for attempt in range(3):
        try:
            r = requests.post(
                url,
                json=params or {},
                timeout=90,
                verify=False
            )
            r.raise_for_status()
            data = r.json()

            if data.get('error') == 'QUERY_LIMIT_EXCEEDED':
                print("⚠️ Лимит Б24, ждём 2с...")
                time.sleep(2)
                continue

            return data

        except requests.exceptions.Timeout:
            print(f"⏱️ Таймаут {method}, попытка {attempt+1}/3")
            time.sleep(3)
        except Exception as e:
            print(f"❌ Ошибка Б24 {method}: {e}")
            time.sleep(2)

    return {}


def get_unprocessed_leads() -> list:
    """Лиды за 21 день которые не обработаны"""
    date_from = (datetime.now() - timedelta(days=21)).strftime("%Y-%m-%d")

    leads = []
    start = 0

    while True:
        data = b24_request("crm.lead.list", {
            "filter": {
                ">=DATE_CREATE": date_from,
                "UF_CRM_LEAD_METRIKA_SENT": False
            },
            "select": [
                "ID", "TITLE", "STATUS_ID",
                "COMMENTS", "PHONE", "EMAIL",
                "DATE_CREATE",
                "UF_CRM_LEAD_METRIKA_SENT",
                "UF_CRM_LEAD_GPT_QUALIFIED"
            ],
            "order": {"DATE_CREATE": "DESC"},
            "start": start
        })

        result = data.get('result', [])
        if not result:
            break

        leads.extend(result)
        print(f"   Загружено лидов: {len(leads)}")

        if len(result) < 50:
            break

        start += 50
        time.sleep(0.5)

    return leads


def get_calls_for_lead(lead_id: str) -> List[dict]:
    """
    Получаем звонки лида через voximplant.statistic.get
    Возвращаем только звонки >= 40 сек с записью
    """
    data = b24_request("voximplant.statistic.get", {
        "FILTER": {
            "CRM_ENTITY_TYPE": "LEAD",
            "CRM_ENTITY_ID": lead_id
        },
        "SELECT": [
            "ID",
            "CALL_DURATION",
            "CALL_RECORD_URL",
            "CALL_START_DATE",
            "CALL_FAILED_CODE",
            "PHONE_NUMBER"
        ],
        "ORDER": {"CALL_DURATION": "DESC"}
    })

    all_calls = data.get('result', [])

    good_calls = [
        c for c in all_calls
        if int(c.get('CALL_DURATION', 0) or 0) >= 40
        and c.get('CALL_RECORD_URL')
        and c.get('CALL_FAILED_CODE') == '200'
    ]

    print(f"   Всего звонков: {len(all_calls)} | "
          f"Подходящих (>=40с + запись): {len(good_calls)}")

    return good_calls


def update_lead(lead_id: str, fields: dict) -> bool:
    """Обновляем поля лида"""
    data = b24_request("crm.lead.update", {
        "id": lead_id,
        "fields": fields
    })
    return bool(data.get('result'))
