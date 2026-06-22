# groq_client.py
from typing import Optional
import os
import re
import json
import time
import threading
from google import genai
from dotenv import load_dotenv
load_dotenv()

from config import MIN_DEBT_AMOUNT

# ===== НАСТРОЙКИ =====
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PROXY          = "socks5://mufer:vRZVgh6c@185.94.167.13:10000"

MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

PROMPT_TEMPLATE = """Ты анализируешь транскрипт телефонного разговора между менеджером и клиентом по теме банкротства.

Текст разговора:
{text}

Твоя задача — найти:
1. ГОРОД клиента (только Екатеринбург или Челябинск)
2. ОБЩУЮ СУММУ ДОЛГА клиента в рублях

ВАЖНО по долгу:
- Нужна именно ОБЩАЯ СУММА ВСЕХ ДОЛГОВ/ЗАДОЛЖЕННОСТЕЙ клиента
- НЕ путай с ежемесячным платежом по кредиту (то что платит в месяц)
- НЕ путай с суммой одного кредита если их несколько
- Если клиент говорит "плачу 15 000 в месяц" — это НЕ долг
- Если клиент говорит "долг 500 000" или "задолженность миллион" — это долг
- Сокращения переводи: "500к" = 500000, "1.5 млн" = 1500000, "полмиллиона" = 500000

Верни ТОЛЬКО валидный JSON без markdown:
{{
  "city": "Екатеринбург" или "Челябинск" или null,
  "debt_amount": число в рублях или null,
  "city_phrase": "точная цитата из текста где упомянут город" или null,
  "debt_phrase": "точная цитата из текста где упомянут долг, а если несколько долгов, то несколько цитат" или null,
  "qualified": true или false
}}

Правила квалификации:
- qualified=true ТОЛЬКО если city IN [Екатеринбург, Челябинск] И debt_amount >= {min_debt}
- Если город не Екатеринбург и не Челябинск → city=null, qualified=false"""


def _extract_retry_delay(error_str: str) -> float:
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?([\d.]+)s", error_str)
    if match:
        return min(round(float(match.group(1))) + 1, 60)
    return 10


def _set_proxy():
    os.environ["HTTP_PROXY"]  = PROXY
    os.environ["HTTPS_PROXY"] = PROXY
    os.environ["http_proxy"]  = PROXY
    os.environ["https_proxy"] = PROXY


def _clear_proxy():
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ.pop(key, None)


def _call_gemini_in_thread(prompt: str, result_container: list):
    """Запускаем Gemini в отдельном потоке"""
    try:
        _set_proxy()
        client = genai.Client(api_key=GEMINI_API_KEY)

        for model_name in MODELS:
            try:
                print(f"   🤖 Gemini модель: {model_name}...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt]
                )

                if not response.text:
                    print(f"   ⚠️ {model_name}: пустой ответ")
                    continue

                result_container.append(response.text.strip())
                return

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    delay = _extract_retry_delay(error_str)
                    print(f"   ⏳ {model_name}: 429 лимит, ждём {delay}с...")
                    time.sleep(delay)
                    continue
                print(f"   ❌ {model_name}: {e}")
                continue

        result_container.append("ERROR: все модели недоступны")

    except Exception as e:
        result_container.append(f"ERROR: {e}")
    finally:
        _clear_proxy()


def call_gemini(prompt: str, max_attempts: int = 3, timeout: int = 60) -> Optional[str]:
    """Вызываем Gemini через поток с таймаутом"""

    for attempt in range(1, max_attempts + 1):
        print(f"   🌐 Gemini запрос (попытка {attempt}/{max_attempts})...")

        result_container = []

        thread = threading.Thread(
            target=_call_gemini_in_thread,
            args=(prompt, result_container),
            daemon=True
        )

        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            print(f"   ⏱️ Таймаут {timeout}с (попытка {attempt}/{max_attempts}) — повторяем")
            continue

        if not result_container:
            print(f"   ⚠️ Пустой контейнер (попытка {attempt}/{max_attempts})")
            continue

        result = result_container[0]

        if result.startswith("ERROR:"):
            print(f"   ❌ {result}")
            continue

        return result

    print("   ❌ Все попытки исчерпаны")
    return None


def analyze_transcript(text: str) -> dict:
    """Анализируем текст звонка через Gemini"""

    prompt = PROMPT_TEMPLATE.format(
        text=text or "(нет текста)",
        min_debt=MIN_DEBT_AMOUNT
    )

    result = call_gemini(prompt)

    if not result:
        return {"qualified": False, "city": None, "debt_amount": None}

    try:
        # Убираем markdown если есть
        clean = re.sub(r"```json|```", "", result).strip()
        json_match = re.search(r'\{.*\}', clean, re.DOTALL)

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
        print(f"   ❌ Ошибка парсинга JSON: {e}, ответ: {result[:200]}")

    return {"qualified": False, "city": None, "debt_amount": None}