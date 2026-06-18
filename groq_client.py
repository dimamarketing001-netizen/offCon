import re
import json
from groq import Groq
from config import GROQ_API_KEY, GROQ_TEXT_MODEL, MIN_DEBT_AMOUNT

client = Groq(api_key=GROQ_API_KEY)


def analyze_transcript(client_text: str, manager_text: str) -> dict:
    """
    Анализируем текст звонка через Groq LLM
    Ищем город и сумму долга
    """

    prompt = f"""Ты анализируешь транскрипт телефонного разговора по банкротству.

Разговор разделён по участникам:
КЛИЕНТ: {client_text or '(нет текста)'}
МЕНЕДЖЕР: {manager_text or '(нет текста)'}

Твоя задача — найти:
1. ГОРОД клиента (только Екатеринбург или Челябинск)
2. ОБЩУЮ СУММУ ДОЛГА клиента в рублях

Верни ТОЛЬКО валидный JSON без markdown:
{{
  "city": "Екатеринбург" или "Челябинск" или null,
  "debt_amount": число или null,
  "city_phrase": "цитата из текста" или null,
  "debt_phrase": "цитата из текста" или null,
  "qualified": true или false
}}

Правила:
- qualified=true ТОЛЬКО если city IN [Екатеринбург, Челябинск] И debt_amount >= {MIN_DEBT_AMOUNT}
- Суммы: "триста тысяч"=300000, "полмиллиона"=500000, "1.2 млн"=1200000
- Если город не Екатеринбург и не Челябинск → city=null"""

    try:
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
            print(f"   🤖 GPT: city={parsed.get('city')}, "
                  f"debt={parsed.get('debt_amount')}, "
                  f"qualified={parsed.get('qualified')}")
            return parsed

    except Exception as e:
        print(f"   ❌ Ошибка Groq: {e}")

    return {"qualified": False, "city": None, "debt_amount": None}