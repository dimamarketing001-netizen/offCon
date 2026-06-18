import requests
import tempfile
import os
import json
import re
from groq import Groq
from config import (
    GROQ_API_KEY,
    GROQ_TEXT_MODEL,
    GROQ_AUDIO_MODEL,
    ALLOWED_CITIES,
    MIN_DEBT_AMOUNT
)

client = Groq(api_key=GROQ_API_KEY)


def transcribe_audio(audio_url: str) -> str | None:
    """
    Скачиваем аудио по URL и транскрибируем через Groq Whisper
    """
    print(f"🎵 Скачиваем аудио: {audio_url[:50]}...")

    try:
        # Скачиваем файл
        response = requests.get(audio_url, timeout=60, stream=True)
        response.raise_for_status()

        # Определяем расширение
        content_type = response.headers.get('content-type', '')
        ext = '.mp3'
        if 'ogg' in content_type:
            ext = '.ogg'
        elif 'wav' in content_type:
            ext = '.wav'
        elif 'mp4' in content_type:
            ext = '.mp4'

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name

        print(f"✅ Файл скачан: {tmp_path} ({os.path.getsize(tmp_path)} байт)")

        # Транскрибируем через Groq Whisper
        with open(tmp_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                model=GROQ_AUDIO_MODEL,
                file=audio_file,
                language="ru",  # Русский язык
                response_format="text"
            )

        # Удаляем временный файл
        os.unlink(tmp_path)

        text = str(transcription).strip()
        print(f"📝 Транскрибация ({len(text)} символов): {text[:100]}...")

        return text

    except Exception as e:
        print(f"❌ Ошибка транскрибации: {e}")
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        return None


def analyze_call_text(text: str) -> dict:
    """
    Анализируем текст звонка через Groq LLM
    Ищем: город и сумму долга
    """

    prompt = f"""Ты анализируешь текст телефонного разговора с клиентом по банкротству.

Твоя задача — извлечь из текста:
1. ГОРОД клиента (нас интересуют только Екатеринбург или Челябинск)
2. СУММУ ДОЛГА клиента (общая сумма всех долгов в рублях)

Текст разговора:
---
{text}
---

Верни ТОЛЬКО JSON без пояснений:
{{
  "city": "Екатеринбург" или "Челябинск" или null,
  "debt_amount": число или null,
  "city_found_phrase": "цитата из текста где упомянут город" или null,
  "debt_found_phrase": "цитата из текста где упомянута сумма" или null,
  "qualified": true или false
}}

Правила:
- qualified = true ТОЛЬКО если city это Екатеринбург или Челябинск И debt_amount >= 300000
- Если город не Екатеринбург и не Челябинск — city = null
- Суммы: "полмиллиона" = 500000, "триста тысяч" = 300000, "1.2 млн" = 1200000
- Если информация не найдена — ставь null"""

    try:
        completion = client.chat.completions.create(
            model=GROQ_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # Низкая температура для точности
            max_tokens=500
        )

        response_text = completion.choices[0].message.content.strip()

        # Извлекаем JSON из ответа
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            print(
                f"🤖 GPT анализ: city={result.get('city')}, debt={result.get('debt_amount')}, qualified={result.get('qualified')}")
            return result
        else:
            print(f"❌ Не удалось распарсить JSON: {response_text}")
            return {"qualified": False, "city": None, "debt_amount": None}

    except Exception as e:
        print(f"❌ Ошибка GPT анализа: {e}")
        return {"qualified": False, "city": None, "debt_amount": None}


def parse_ym_uid_from_comments(comments: str) -> str | None:
    """Извлекаем _ym_uid из поля COMMENTS"""
    if not comments:
        return None

    match = re.search(r'_ym_uid=(\d+)', comments)
    if match:
        uid = match.group(1)
        print(f"🎯 Найден _ym_uid: {uid}")
        return uid

    print("⚠️ _ym_uid не найден в COMMENTS")
    return None