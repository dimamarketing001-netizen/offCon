from typing import Optional
import re
import json
import httpx
import threading
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

from config import GROQ_API_KEY, GROQ_TEXT_MODEL, MIN_DEBT_AMOUNT

PROXY = "socks5://mufer:vRZVgh6c@185.94.167.13:10000"


def get_client() -> Groq:
    http_client = httpx.Client(
        proxy=PROXY,
        timeout=httpx.Timeout(15.0)
    )
    return Groq(api_key=GROQ_API_KEY, http_client=http_client)


def call_groq_in_thread(prompt: str, result_container: list):
    """Запускаем Groq в отдельном потоке"""
    try:
        client = get_client()
        completion = client.chat.completions.create(
            model=GROQ_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400
        )
        result_container.append(completion.choices[0].message.content.strip())
    except Exception as e:
        result_container.append(f"ERROR: {e}")


def call_groq(prompt: str, max_attempts: int = 3, timeout: int = 45) -> Optional[str]:
    """
    Вызываем Groq в отдельном потоке с жёстким таймаутом
    Если поток завис — убиваем и пробуем снова
    """

    for attempt in range(1, max_attempts + 1):
        print(f"   🤖 Groq запрос (попытка {attempt}/{max_attempts}, таймаут {timeout}с)...")

        result_container = []

        thread = threading.Thread(
            target=call_groq_in_thread,
            args=(prompt, result_container),
            daemon=True  # Поток умрёт вместе с основным процессом
        )

        thread.start()
        thread.join(timeout=timeout)  # Ждём максимум timeout секунд

        if thread.is_alive():
            # Поток завис — не можем убить, но идём дальше
            print(f"   ⏱️ Таймаут {timeout}с (попытка {attempt}/{max_attempts}) — поток завис, пробуем снова")
            continue

        if not result_container:
            print(f"   ⚠️ Пустой ответ (попытка {attempt}/{max_attempts})")
            continue

        result = result_container[0]

        if result.startswith("ERROR:"):
            print(f"   ❌ Ошибка (попытка {attempt}/{max_attempts}): {result}")
            continue

        print(f"   ✅ Groq ответил успешно")
        return result

    print("   ❌ Все попытки исчерпаны — пропускаем лид")
    return None


def analyze_transcript(text: str) -> dict:
    """Анализируем текст звонка — ищем город и долг"""

    prompt = f"""Ты анализируешь транскрипт телефонного разговора по банкротству.

Текст разговора:
{text or '(нет текста)'}

Найди:
1. ГОРОД клиента (только Екатеринбург или Челябинск)
2. СУММУ ДОЛГА клиента в рублях (именно долг/задолженность, не просто любую сумму)

Верни ТОЛЬКО валидный JSON без markdown:
{{
  "city": "Екатеринбург" или "Челябинск" или null,
  "debt_amount": число или null,
  "city_phrase": "цитата где упомянут город" или null,
  "debt_phrase": "цитата где упомянут долг" или null,
  "qualified": true или false
}}

Правила:
- qualified=true ТОЛЬКО если city IN [Екатеринбург, Челябинск] И debt_amount >= {MIN_DEBT_AMOUNT}
- Ищем именно ДОЛГ/ЗАДОЛЖЕННОСТЬ а не просто любую сумму
- "триста тысяч"=300000, "полмиллиона"=500000, "1.2 млн"=1200000
- Если город не Екатеринбург и не Челябинск → city=null"""

    result = call_groq(prompt)

    if not result:
        return {"qualified": False, "city": None, "debt_amount": None}

    try:
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            print(f"   📊 city={parsed.get('city')}, "
                  f"debt={parsed.get('debt_amount')}, "
                  f"qualified={parsed.get('qualified')}")
            if parsed.get('city_phrase'):
                print(f"   📍 {parsed.get('city_phrase')}")
            if parsed.get('debt_phrase'):
                print(f"   💰 {parsed.get('debt_phrase')}")
            return parsed
    except Exception as e:
        print(f"   ❌ Ошибка парсинга JSON: {e}")

    return {"qualified": False, "city": None, "debt_amount": None}