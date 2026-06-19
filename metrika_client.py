from typing import Optional
import io
import time
import requests
from config import METRIKA_GOAL


def send_conversion(
        counter_id: str,
        token: str,
        client_id: str = None,
        phone: str = None
) -> bool:
    if not client_id and not phone:
        print("   ❌ Нет идентификаторов для Метрики")
        return False

    # Формируем CSV
    timestamp = int(time.time())

    rows = []

    if client_id:
        # ClientID конверсия
        csv_content = f"ClientId,Target,DateTime\n{client_id},{METRIKA_GOAL},{timestamp}"
        client_id_type = "CLIENT_ID"
    elif phone:
        phone_clean = ''.join(filter(str.isdigit, str(phone)))
        if phone_clean.startswith('8') and len(phone_clean) == 11:
            phone_clean = '7' + phone_clean[1:]
        csv_content = f"Phone,Target,DateTime\n+{phone_clean},{METRIKA_GOAL},{timestamp}"
        client_id_type = "CLIENT_ID"

    print(f"   📤 Отправляем в Метрику:")
    print(f"      counter_id:     {counter_id}")
    print(f"      ClientID:       {client_id}")
    print(f"      Target:         {METRIKA_GOAL}")
    print(f"      CSV:\n{csv_content}")

    url = (f"https://api-metrika.yandex.net/management/v1/"
           f"counter/{counter_id}/offline_conversions/upload")

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"OAuth {token}",
            },
            files={
                "file": ("conversions.csv", csv_content.encode('utf-8'), "text/csv")
            },
            timeout=30
        )

        print(f"   📥 Метрика {r.status_code}: {r.text}")

        if r.status_code == 200:
            result = r.json()
            status = result.get('uploading', {}).get('status', '')
            print(f"   ✅ Метрика принята! status={status}, counter={counter_id}")
            return True
        else:
            print(f"   ❌ Метрика ошибка {r.status_code}: {r.text[:300]}")
            return False

    except Exception as e:
        print(f"   ❌ Ошибка Метрики: {e}")
        return False