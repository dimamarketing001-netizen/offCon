from typing import Optional
from io import StringIO
from datetime import datetime
import csv
import requests

from config import METRIKA_GOAL


def send_conversion(
    counter_id: str,
    token: str,
    client_id: Optional[str] = None,
    phone: Optional[str] = None
) -> bool:
    """Отправка офлайн-конверсии в Яндекс.Метрику через CSV upload"""

    if not client_id and not phone:
        print("   ❌ Нет ClientId или телефона для Метрики")
        return False

    row = {
        "Target": METRIKA_GOAL,
        "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Price": "1",
        "Currency": "RUB",
    }

    if client_id:
        row["ClientId"] = str(client_id)

    elif phone:
        phone_clean = ''.join(filter(str.isdigit, str(phone)))
        if phone_clean.startswith("8") and len(phone_clean) == 11:
            phone_clean = "7" + phone_clean[1:]
        elif len(phone_clean) == 10:
            phone_clean = "7" + phone_clean

        row["PhoneNumber"] = f"+{phone_clean}"

    # Формируем CSV в памяти
    csv_buffer = StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=list(row.keys()))
    writer.writeheader()
    writer.writerow(row)

    csv_content = csv_buffer.getvalue().encode("utf-8")

    url = f"https://api-metrika.yandex.net/management/v1/counter/{counter_id}/offline_conversions/upload"

    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"OAuth {token}"
                # Content-Type НЕ указываем вручную
            },
            files={
                "file": ("offline_conversions.csv", csv_content, "text/csv")
            },
            timeout=30
        )

        print(f"   📤 CSV:\n{csv_buffer.getvalue()}")
        print(f"   📥 Метрика {r.status_code}: {r.text[:1000]}")

        if 200 <= r.status_code < 300:
            print(f"   ✅ Метрика: файл принят, counter={counter_id}")
            return True

        return False

    except Exception as e:
        print(f"   ❌ Ошибка Метрики: {e}")
        return False