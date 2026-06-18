import requests
from datetime import datetime, timedelta
from config import B24_WEBHOOK
import time


def b24_request(method: str, params: dict = None) -> dict:
    """Базовый запрос к Б24"""
    url = f"{B24_WEBHOOK}{method}.json"

    try:
        response = requests.post(url, json=params or {}, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Проверяем лимит запросов
        if data.get('error') == 'QUERY_LIMIT_EXCEEDED':
            print("⚠️ Лимит запросов Б24, ждём 2 секунды...")
            time.sleep(2)
            return b24_request(method, params)

        return data.get('result', {})

    except Exception as e:
        print(f"❌ Ошибка Б24 {method}: {e}")
        return {}


def get_leads_last_21_days() -> list:
    """
    Получаем все лиды за последние 21 день
    которые ещё не были обработаны
    """
    date_from = (datetime.now() - timedelta(days=21)).strftime("%Y-%m-%d")

    leads = []
    start = 0

    while True:
        result = b24_request("crm.lead.list", {
            "filter": {
                ">=DATE_CREATE": date_from,
                # Ещё не отправлены в Метрику
                "UF_CRM_LEAD_METRIKA_SENT": False
            },
            "select": [
                "ID",
                "TITLE",
                "COMMENTS",
                "STATUS_ID",
                "DATE_CREATE",
                "PHONE",
                "EMAIL",
                "UF_CRM_LEAD_METRIKA_SENT",
                "UF_CRM_LEAD_GPT_CITY",
                "UF_CRM_LEAD_GPT_QUALIFIED"
            ],
            "start": start
        })

        if isinstance(result, list):
            leads.extend(result)
            if len(result) < 50:
                break
            start += 50
        else:
            break

        time.sleep(0.5)  # Пауза между запросами

    print(f"📋 Найдено лидов для обработки: {len(leads)}")
    return leads


def get_calls_for_lead(lead_id: str) -> list:
    """
    Получаем звонки по лиду
    Ищем успешные звонки с нормальной длительностью
    """
    result = b24_request("telephony.externalcall.list", {
        "filter": {
            "CRM_ENTITY_TYPE": "LEAD",
            "CRM_ENTITY_ID": lead_id
        },
        "select": [
            "ID",
            "CALL_DURATION",
            "CALL_START_DATE",
            "RECORD_URL",
            "STATUS_CODE"
        ]
    })

    if isinstance(result, list):
        return result

    # Если telephony.externalcall.list не работает - пробуем через активити
    return get_calls_via_activity(lead_id)


def get_calls_via_activity(lead_id: str) -> list:
    """
    Альтернативный способ получить звонки через активити CRM
    """
    result = b24_request("crm.activity.list", {
        "filter": {
            "OWNER_TYPE_ID": 1,  # 1 = Lead
            "OWNER_ID": lead_id,
            "TYPE_ID": 2  # 2 = Звонок
        },
        "select": [
            "ID",
            "DESCRIPTION",
            "START_TIME",
            "DURATION",
            "COMPLETED",
            "ORIGIN_ID"  # ID звонка в телефонии
        ]
    })

    return result if isinstance(result, list) else []


def get_call_record_url(call_id: str) -> str | None:
    """Получаем ссылку на запись звонка"""
    result = b24_request("telephony.externalcall.get", {
        "CALL_ID": call_id
    })

    if isinstance(result, dict):
        return result.get('RECORD_URL')
    return None


def update_lead(lead_id: str, fields: dict) -> bool:
    """Обновляем поля лида в Б24"""
    result = b24_request("crm.lead.update", {
        "id": lead_id,
        "fields": fields
    })
    return bool(result)