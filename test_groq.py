import os
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
import httpx

api_key = os.getenv("GROQ_API_KEY")
print(f"API Key: {api_key[:20] if api_key else 'НЕ НАЙДЕН'}...")

# Прокси
PROXY = "socks5://mufer:vRZVgh6c@185.94.167.13:10000"

# Клиент с прокси
http_client = httpx.Client(
    proxy=PROXY,
    timeout=30
)

client = Groq(
    api_key=api_key,
    http_client=http_client
)

# Тест 1: простой запрос
print("\n🤖 Тест 1: простой запрос через прокси...")
try:
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "привет"}],
        max_tokens=50
    )
    print(f"✅ Ответ: {r.choices[0].message.content}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

# Тест 2: проверяем IP через прокси
print("\n🌐 Тест 2: проверяем IP...")
try:
    r = httpx.get(
        "https://api.ipify.org?format=json",
        proxy=PROXY,
        timeout=10
    )
    print(f"✅ Наш IP: {r.json()}")
except Exception as e:
    print(f"❌ Ошибка: {e}")