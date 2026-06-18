import requests
import json
from datetime import datetime
from config import METRIKA_TOKEN, METRIKA_COUNTER_ID, METRIKA_GOAL


def send_conversion(
        client_id: str = None,
        phone: str = None,
        email: str = None,
        goal: str = None,
        price: float = 1
) -> tuple[bool, dict]:
    """
    Отправляем офлайн конверсию в Яндекс.Метрику
    """

    goal = goal or METRIKA_GOAL

    url = f"https://api-metrika.yandex.net/management/v1/counter/{METRIKA_COUNTER_ID}/offline_conversions/upload"

    headers = {
        "Authorization": f"OAuth {METRIKA_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    # Формируем запись конверсии
    conversion = {
        "DateTime": int(datetime.now().timestamp()),
        "Target": goal,
        "Price": price,
        "Currency": "RUB"
    }

    # Добавляем идентификаторы (хотя бы один обязателен)
    if client_id:
        conversion["ClientID"] = client_id

    if phone:
        # Нормализуем телефон
        phone_clean = ''.join(filter(str.isdigit, phone))
        if phone_clean.startswith('8') and len(phone_clean) == 11:
            phone_clean = '7' + phone_clean[1:]
        conversion["Phone"] = f"+{phone_clean}"

    if email:
        conversion["Email"] = email.lower().strip()

    # Проверяем что есть хотя бы один идентификатор
    if not any([client_id, phone, email]):
        print("❌ Нет идентификаторов для Метрики")
        return False, {"error": "no_identifiers"}

    data = {"data": json.dumps([conversion])}

    print(f"📊 Отправляем в Метрику: ClientID={client_id}, goal={goal}")

    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        result = response.json()

        if response.status_code == 200:
            print(f"✅ Метрика: конверсия принята")
            return True, result
        else:
            print(f"❌ Метрика ошибка: {result}")
            return False, result

    except Exception as e:
        print(f"❌ Ошибка запроса к Метрике: {e}")
        return False, {"error": str(e)}