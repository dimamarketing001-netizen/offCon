from typing import Optional
import json
import time
import requests
from config import METRIKA_GOAL


def send_conversion(
    counter_id: str,
    token: str,
    client_id: str = None,
    phone: str = None
) -> bool:
    """Отправляем офлайн конверсию в Яндекс.Метрику"""

    payload = {
        "DateTime": int(time.time()),
        "Target":   METRIKA_GOAL,
        "Price":    1,
        "Currency": "RUB"
    }

    if client_id:
        payload["ClientID"] = client_id

    if phone:
        phone_clean = ''.join(filter(str.isdigit, str(phone)))
        if phone_clean.startswith('8') and len(phone_clean) == 11:
            phone_clean = '7' + phone_clean[1:]
        payload["Phone"] = f"+{phone_clean}"

    if not client_id and not phone:
        print("   ❌ Нет идентификаторов для Метрики")
        return False

    url = (f"https://api-metrika.yandex.net/management/v1/"
           f"counter/{counter_id}/offline_conversions/upload")

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"OAuth {token}",
                "Content-Type":  "application/x-www-form-urlencoded"
            },
            data={"data": json.dumps([payload])},
            timeout=30
        )

        if r.status_code == 200:
            print(f"   ✅ Метрика: принята! counter={counter_id}")
            return True
        else:
            print(f"   ❌ Метрика {r.status_code}: {r.text[:200]}")
            return False

    except Exception as e:
        print(f"   ❌ Ошибка Метрики: {e}")
        return False