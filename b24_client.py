from datetime import datetime, timedelta
import time
from typing import Optional

import requests

from config import B24_WEBHOOK


def _method_url(method: str) -> str:
    return f"{B24_WEBHOOK.rstrip('/')}/{method}.json"


def b24_request(method: str, params: Optional[dict] = None) -> dict:
    url = _method_url(method)

    for attempt in range(1, 4):
        try:
            response = requests.post(url, json=params or {}, timeout=60)

            if response.status_code >= 400:
                print(
                    f"❌ Bitrix24 HTTP {response.status_code} | {method} | "
                    f"{response.text[:500]}"
                )
                if response.status_code in (429, 502, 503, 504):
                    time.sleep(attempt * 2)
                    continue

            response.raise_for_status()
            data = response.json()

            if data.get("error") == "QUERY_LIMIT_EXCEEDED":
                print(f"⚠️ Лимит Б24 | {method} | попытка {attempt}/3")
                time.sleep(attempt * 2)
                continue

            if data.get("error"):
                print(
                    f"❌ Bitrix24 API | {method} | "
                    f"{data.get('error')}: {data.get('error_description', '')}"
                )

            return data

        except requests.exceptions.Timeout:
            print(f"⏱️ Таймаут {method} | попытка {attempt}/3")
            time.sleep(attempt * 2)
        except requests.RequestException as exc:
            print(f"❌ Сетевая ошибка Б24 {method}: {exc}")
            time.sleep(attempt * 2)
        except ValueError as exc:
            print(f"❌ Некорректный JSON от Б24 {method}: {exc}")
            return {}

    return {}


LEAD_SELECT = ["*", "UF_*"]


def get_recent_leads(hours: int = 24) -> list:
    if hours <= 0:
        raise ValueError("hours должен быть больше 0")

    date_from = (datetime.now().astimezone() - timedelta(hours=hours)).isoformat(
        timespec="seconds"
    )

    print(f"   🕒 DATE_CREATE >= {date_from}")

    leads = []
    start = 0

    while True:
        data = b24_request(
            "crm.lead.list",
            {
                "filter": {">=DATE_CREATE": date_from},
                "select": LEAD_SELECT,
                "order": {"DATE_CREATE": "DESC"},
                "start": start,
            },
        )

        result = data.get("result", [])
        if not result:
            break

        leads.extend(result)
        print(f"   Загружено лидов: {len(leads)}")

        next_start = data.get("next")
        if next_start is None:
            break

        start = int(next_start)
        time.sleep(0.25)

    return leads


def get_lead(lead_id: str) -> Optional[dict]:
    data = b24_request("crm.lead.get", {"id": lead_id})
    result = data.get("result")
    return result if isinstance(result, dict) else None


def update_lead(lead_id: str, fields: dict) -> bool:
    data = b24_request(
        "crm.lead.update",
        {
            "id": lead_id,
            "fields": fields,
        },
    )
    return bool(data.get("result"))
