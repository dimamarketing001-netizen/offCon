from typing import Optional
import re
import json
import os
import httpx
import time
from groq import Groq
from dotenv import load_dotenv
load_dotenv()

from config import GROQ_API_KEY, GROQ_TEXT_MODEL, MIN_DEBT_AMOUNT

# ===== ПРОКСИ =====
PROXY = "socks5://mufer:vRZVgh6c@185.94.167.13:10000"

# ===== ТАЙМАУТЫ (были слишком мягкие) =====
TIMEOUT = httpx.Timeout(
    connect=15.0,    # подключение к прокси
    read=90.0,       # чтение ответа (GPT может думать долго)
    write=15.0,      # отправка запроса
    pool=15.0        # ожидание из пула
)

http_client = httpx.Client(
    proxy=PROXY,
    timeout=TIMEOUT
)

client = Groq(
    api_key=GROQ_API_KEY,
    http_client=http_client
)


def analyze_transcript(client_text: str, manager_text: str, max_retries: int = 3) -> dict:
    """
    Анализируем текст звонка через Groq
    Ищем город и сумму долга
    """

    # ===== ОБРЕЗАЕМ ТЕКСТ ЕСЛИ СЛИШКОМ ДЛИННЫЙ =====
    # Groq может зависать на очень длинных промптах через прокси
    MAX_TEXT_LEN = 15000
    if client_text and len(client_text) > MAX_TEXT_LEN:
        client_text = client_text[:MAX_TEXT_LEN] + "..."
        print(f"   ✂️ Текст обрезан до {MAX_TEXT_LEN} символов")

    prompt = f"""Ты анализируешь транскрипт телефонного разговора по банкротству.

Текст разговора:
{client_text or '(нет текста)'}

Твоя задача — найти:
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
- Суммы: "триста тысяч"=300000, "полмиллиона"=500000, "1.2 млн"=1200000
- Если город не Екатеринбург и не Челябинск → city=null"""

    # ===== RETRY ЛОГИКА =====
    for attempt in range(1, max_retries + 1):
        try:
            print(f"   🤖 Groq запрос (попытка {attempt}/{max_retries})...")

            completion = client.chat.completions.create(
                model=GROQ_TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=400
            )

            result = completion.choices[0].message.content.strip()

            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                print(f"   🤖 Groq: city={parsed.get('city')}, "
                      f"debt={parsed.get('debt_amount')}, "
                      f"qualified={parsed.get('qualified')}")
                if parsed.get('city_phrase'):
                    print(f"   📍 Город цитата: {parsed.get('city_phrase')}")
                if parsed.get('debt_phrase'):
                    print(f"   💰 Долг цитата: {parsed.get('debt_phrase')}")
                return parsed
            else:
                print(f"   ⚠️ JSON не найден в ответе: {result[:200]}")

        except httpx.TimeoutException as e:
            print(f"   ⏱️ Таймаут прокси (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait = attempt * 5  # 5, 10, 15 секунд
                print(f"   ⏳ Ждём {wait}с перед повтором...")
                time.sleep(wait)
            else:
                print(f"   ❌ Все {max_retries} попытки исчерпаны (таймаут)")

        except httpx.ProxyError as e:
            print(f"   🔌 Ошибка прокси (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait = attempt * 5
                print(f"   ⏳ Ждём {wait}с перед повтором...")
                time.sleep(wait)
            else:
                print(f"   ❌ Все {max_retries} попытки исчерпаны (прокси)")

        except json.JSONDecodeError as e:
            print(f"   ⚠️ Ошибка парсинга JSON: {e}")
            # JSON ошибка — не повторяем, это не таймаут
            break

        except Exception as e:
            print(f"   ❌ Ошибка Groq (попытка {attempt}/{max_retries}): {type(e).__name__}: {e}")
            if attempt < max_retries:
                wait = attempt * 5
                print(f"   ⏳ Ждём {wait}с перед повтором...")
                time.sleep(wait)
            else:
                print(f"   ❌ Все {max_retries} попытки исчерпаны")

    return {"qualified": False, "city": None, "debt_amount": None}