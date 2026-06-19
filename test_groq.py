import os
from dotenv import load_dotenv
load_dotenv()

from groq import Groq

api_key = os.getenv("GROQ_API_KEY")
print(f"API Key: {api_key[:20] if api_key else 'НЕ НАЙДЕН'}...")

client = Groq(api_key=api_key)

# Тест 1: простой запрос
print("\n🤖 Тест 1: простой запрос...")
try:
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "привет"}],
        max_tokens=50
    )
    print(f"✅ Ответ: {r.choices[0].message.content}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

# Тест 2: список доступных моделей
print("\n📋 Тест 2: список моделей...")
try:
    models = client.models.list()
    for m in models.data:
        print(f"   - {m.id}")
except Exception as e:
    print(f"❌ Ошибка: {e}")

# Тест 3: другая модель
print("\n🤖 Тест 3: модель llama-3.1-8b-instant...")
try:
    r = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "привет"}],
        max_tokens=50
    )
    print(f"✅ Ответ: {r.choices[0].message.content}")
except Exception as e:
    print(f"❌ Ошибка: {e}")