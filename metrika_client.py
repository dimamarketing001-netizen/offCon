from typing import Optional
import time
import requests
from config import METRIKA_GOAL


def send_conversion(
        counter_id: str,
        token: str,
        client_id: str = None,
        phone: str = None,
        goal_name: str = None,
        revenue: int = None
) -> bool:

    if not client_id and not phone:
        print("   ❌ Нет идентификаторов для Метрики")
        return False

    goal = goal_name or METRIKA_GOAL
    timestamp = int(time.time())

    if client_id:
        if revenue is not None:
            csv_content = (
                f"ClientId,Target,DateTime,Revenue\n"
                f"{client_id},{goal},{timestamp},{revenue}"
            )
        else:
            csv_content = (
                f"ClientId,Target,DateTime\n"
                f"{client_id},{goal},{timestamp}"
            )
    else:
        phone_clean = ''.join(filter(str.isdigit, str(phone)))
        if phone_clean.startswith('8') and len(phone_clean) == 11:
            phone_clean = '7' + phone_clean[1:]

        if revenue is not None:
            csv_content = (
                f"Phone,Target,DateTime,Revenue\n"
                f"+{phone_clean},{goal},{timestamp},{revenue}"
            )
        else:
            csv_content = (
                f"Phone,Target,DateTime\n"
                f"+{phone_clean},{goal},{timestamp}"
            )

    print(f"   📤 Отправка в Метрику | counter={counter_id} | goal={goal} | revenue={revenue}")

    url = (
        f"https://api-metrika.yandex.net/management/v1/"
        f"counter/{counter_id}/offline_conversions/upload"
    )

    try:
        r = requests.post(
            url,
            headers={"Authorization": f"OAuth {token}"},
            files={"file": ("conversions.csv", csv_content.encode('utf-8'), "text/csv")},
            timeout=30
        )

        print(f"   📥 Метрика {r.status_code}")

        if r.status_code == 200:
            return True

        print(f"   ❌ Ошибка Метрики: {r.text[:300]}")
        return False

    except Exception as e:
        print(f"   ❌ Исключение Метрики: {e}")
        return False