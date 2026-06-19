import requests

# 1. Твои данные из кабинета разработчика Яндекса
CLIENT_ID = ""
CLIENT_SECRET = ""

# 2. Вставь сюда тот 7-значный код подтверждения, который видишь на экране
CONFIRMATION_CODE = ""


def get_final_token():
    url = "https://oauth.yandex.ru/token"

    data = {
        "grant_type": "authorization_code",
        "code": CONFIRMATION_CODE,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    print("Отправляю запрос в Яндекс...")
    response = requests.post(url, data=data)

    if response.status_code == 200:
        token_data = response.json()
        print("\n✅ УСПЕХ!")
        print("Твой Access Token (сохрани его в .env):")
        print("-" * 50)
        print(token_data['access_token'])
        print("-" * 50)
        print(f"Токен будет работать: {token_data['expires_in'] // 86400} дней")
    else:
        print("\n❌ ОШИБКА")
        print(f"Статус: {response.status_code}")
        print(f"Ответ: {response.text}")


if __name__ == "__main__":
    get_final_token()