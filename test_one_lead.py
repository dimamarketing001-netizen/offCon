# test_one_lead.py

import requests
import re
import json
import tempfile
import os
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from groq import Groq
from config import (
    B24_WEBHOOK,
    GROQ_API_KEY,
    GROQ_TEXT_MODEL,
    GROQ_AUDIO_MODEL,
    METRIKA_TOKEN,
    METRIKA_COUNTER_ID,
    METRIKA_GOAL,
    MIN_CALL_DURATION,
    ALLOWED_CITIES,
    MIN_DEBT_AMOUNT
)

LEAD_ID = "16966"

client = Groq(api_key=GROQ_API_KEY)


def make_session():
    """Сессия с retry и SSL fix"""
    session = requests.Session()

    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


session = make_session()


def b24_request(method: str, params: dict = None) -> dict:
    """Базовый запрос к Б24 с SSL fix"""
    url = f"{B24_WEBHOOK}{method}.json"

    try:
        response = session.post(
            url,
            json=params or {},
            timeout=30,
            verify=True
        )
        return response.json()

    except requests.exceptions.SSLError:
        print(f"   ⚠️ SSL ошибка, пробуем без верификации...")
        try:
            import urllib3
            urllib3.disable_warnings()
            response = requests.post(
                url,
                json=params or {},
                timeout=30,
                verify=False  # Отключаем SSL верификацию
            )
            return response.json()
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return {}

    except Exception as e:
        print(f"   ❌ Ошибка {method}: {e}")
        return {}


def test_step1_get_lead():
    print("\n" + "=" * 60)
    print("🔍 ШАГ 1: Получаем лид из Б24...")

    data = b24_request("crm.lead.get", {
        "id": LEAD_ID,
        "select": ["ID", "TITLE", "COMMENTS", "STATUS_ID", "DATE_CREATE", "PHONE", "EMAIL"]
    })

    lead = data.get('result', {})

    if not lead:
        print(f"❌ Лид не найден: {data}")
        return None

    print(f"✅ Лид найден!")
    print(f"   ID:      {lead.get('ID')}")
    print(f"   Название:{lead.get('TITLE')}")
    print(f"   Статус:  {lead.get('STATUS_ID')}")
    print(f"   Телефон: {lead.get('PHONE')}")

    return lead


def test_step2_get_calls():
    print("\n" + "=" * 60)
    print(f"📞 ШАГ 2: Ищем звонки для лида {LEAD_ID}...")

    data = b24_request("crm.activity.list", {
        "filter": {
            "OWNER_TYPE_ID": 1,
            "OWNER_ID": LEAD_ID,
            "TYPE_ID": 2
        },
        "select": ["ID", "DURATION", "ORIGIN_ID", "COMPLETED", "SUBJECT"]
    })

    calls = data.get('result', [])
    print(f"   Найдено звонков: {len(calls)}")

    for c in calls:
        print(f"   - ID={c.get('ID')}, "
              f"Длит={c.get('DURATION')}с, "
              f"Завершён={c.get('COMPLETED')}, "
              f"ORIGIN_ID={c.get('ORIGIN_ID')}")

    return calls


def test_step3_get_call_record(calls):
    print("\n" + "=" * 60)
    print("🎙️ ШАГ 3: Получаем запись звонка...")

    for call in calls:
        origin_id = call.get('ORIGIN_ID')

        if not origin_id:
            continue

        print(f"   Пробуем ORIGIN_ID: {origin_id}")
        time.sleep(1)  # Пауза между запросами

        data = b24_request("telephony.externalcall.get", {
            "CALL_ID": origin_id
        })

        result = data.get('result', {})

        if result:
            duration = result.get('CALL_DURATION', 0) or 0
            record_url = result.get('RECORD_URL', '')

            print(f"   Длительность: {duration}с")
            print(f"   Запись: {str(record_url)[:80] if record_url else 'нет'}")

            if record_url and int(duration) >= MIN_CALL_DURATION:
                print(f"   ✅ Подходящий звонок найден!")
                return record_url, origin_id
            elif record_url:
                print(f"   ⚠️ Запись есть но звонок короткий ({duration}с < {MIN_CALL_DURATION}с)")
                # Возвращаем всё равно для теста
                return record_url, origin_id
        else:
            print(f"   Нет данных: {data}")

    print("   ❌ Записей не найдено")
    return None, None


def test_step4_parse_comments(comments):
    print("\n" + "=" * 60)
    print("🎯 ШАГ 4: Парсим _ym_uid из COMMENTS...")

    if not comments:
        print("❌ COMMENTS пустой")
        return None

    print(f"   COMMENTS (первые 300 символов):\n{comments[:300]}")

    match = re.search(r'_ym_uid=(\d+)', comments)
    if match:
        uid = match.group(1)
        print(f"\n✅ _ym_uid найден: {uid}")
        return uid

    print("❌ _ym_uid не найден")
    return None


def test_step5_whisper(audio_url):
    print("\n" + "=" * 60)
    print("🎵 ШАГ 5: Транскрибация через Groq Whisper...")
    print(f"   URL: {audio_url[:80]}")

    try:
        print("   Скачиваем файл...")

        resp = session.get(audio_url, timeout=120)

        content_type = resp.headers.get('content-type', '')
        size = len(resp.content)
        print(f"   Content-Type: {content_type}")
        print(f"   Размер: {size} байт ({size // 1024} KB)")

        if size < 1000:
            print(f"❌ Файл слишком маленький: {resp.text[:200]}")
            return None

        # Определяем расширение
        ext = '.mp3'
        if 'ogg' in content_type:
            ext = '.ogg'
        elif 'wav' in content_type:
            ext = '.wav'
        elif 'mp4' in content_type:
            ext = '.mp4'
        elif 'webm' in content_type:
            ext = '.webm'

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name

        print(f"   Сохранён: {tmp_path}")
        print("   Отправляем в Groq Whisper...")

        with open(tmp_path, 'rb') as f:
            transcription = client.audio.transcriptions.create(
                model=GROQ_AUDIO_MODEL,
                file=f,
                language="ru",
                response_format="text"
            )

        os.unlink(tmp_path)

        text = str(transcription).strip()
        print(f"\n✅ Транскрипт ({len(text)} символов):")
        print(f"{'-' * 40}")
        print(text[:500])
        print(f"{'-' * 40}")

        return text

    except Exception as e:
        print(f"❌ Ошибка Whisper: {e}")
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        return None


def test_step6_analyze(transcript):
    print("\n" + "=" * 60)
    print("🤖 ШАГ 6: GPT анализ транскрипта...")

    prompt = f"""Проанализируй текст телефонного разговора по банкротству.
Верни ТОЛЬКО JSON без пояснений и без markdown:

{{
  "city": "Екатеринбург" или "Челябинск" или null,
  "debt_amount": число или null,
  "city_phrase": "цитата где упомянут город" или null,
  "debt_phrase": "цитата где упомянута сумма" или null,
  "qualified": true или false
}}

Правила:
- qualified=true ТОЛЬКО если city IN [Екатеринбург, Челябинск] И debt_amount >= {MIN_DEBT_AMOUNT}
- Суммы: "триста тысяч"=300000, "полмиллиона"=500000, "1.2 млн"=1200000
- Если город не Екатеринбург и не Челябинск — city=null

Текст:
{transcript}"""

    completion = client.chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300
    )

    result = completion.choices[0].message.content.strip()
    print(f"   GPT ответ: {result}")

    json_match = re.search(r'\{.*\}', result, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            print(f"\n   🏙️  Город:     {parsed.get('city')}")
            print(f"   💰 Долг:      {parsed.get('debt_amount')}")
            print(f"   ✅ Qualified: {parsed.get('qualified')}")
            print(f"   📍 Цитата:    {parsed.get('city_phrase')}")
            print(f"   💬 Долг цит.: {parsed.get('debt_phrase')}")
            return parsed
        except:
            print("❌ Не удалось распарсить JSON")

    return None


def test_step7_metrika(ym_uid, phone=None):
    print("\n" + "=" * 60)
    print("📊 ШАГ 7: Отправка конверсии в Метрику...")

    payload = {
        "DateTime": int(time.time()),
        "Target": METRIKA_GOAL,
        "Price": 1,
        "Currency": "RUB"
    }

    if ym_uid:
        payload["ClientID"] = ym_uid
        print(f"   ClientID: {ym_uid}")

    if phone:
        phone_clean = ''.join(filter(str.isdigit, str(phone)))
        if phone_clean.startswith('8') and len(phone_clean) == 11:
            phone_clean = '7' + phone_clean[1:]
        payload["Phone"] = f"+{phone_clean}"
        print(f"   Phone: +{phone_clean}")

    print(f"   Target: {METRIKA_GOAL}")
    print(f"   Counter: {METRIKA_COUNTER_ID}")

    url = f"https://api-metrika.yandex.net/management/v1/counter/{METRIKA_COUNTER_ID}/offline_conversions/upload"

    response = requests.post(
        url,
        headers={
            "Authorization": f"OAuth {METRIKA_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={"data": json.dumps([payload])},
        timeout=30
    )

    print(f"\n   Статус: {response.status_code}")
    print(f"   Ответ:  {response.text}")

    if response.status_code == 200:
        print("✅ Конверсия принята!")
        return True
    else:
        print("❌ Ошибка Метрики")
        return False


# ===== ЗАПУСК =====
if __name__ == '__main__':

    print("=" * 60)
    print("🧪 ПОЛНЫЙ ТЕСТ СИСТЕМЫ")
    print(f"   Лид ID:    {LEAD_ID}")
    print(f"   Мин. долг: {MIN_DEBT_AMOUNT:,} руб")
    print(f"   Города:    {ALLOWED_CITIES}")
    print("=" * 60)

    # 1. Лид
    lead = test_step1_get_lead()
    if not lead:
        exit("❌ Лид не найден")

    # 2. Звонки
    calls = test_step2_get_calls()

    # 3. Запись звонка
    audio_url, call_id = test_step3_get_call_record(calls)

    # 4. ym_uid
    ym_uid = test_step4_parse_comments(lead.get('COMMENTS'))

    # 5. Whisper
    transcript = None
    if audio_url:
        transcript = test_step5_whisper(audio_url)
    else:
        print("\n🎵 ШАГ 5: Пропускаем — нет записи звонка")

    # 6. GPT анализ
    analysis = None
    if transcript:
        analysis = test_step6_analyze(transcript)
    else:
        print("\n🤖 ШАГ 6: Пропускаем — нет транскрипта")

    # 7. Метрика
    phone = None
    phones = lead.get('PHONE', [])
    if phones and isinstance(phones, list):
        phone = phones[0].get('VALUE')

    metrika_sent = False
    if analysis and analysis.get('qualified'):
        if ym_uid or phone:
            metrika_sent = test_step7_metrika(ym_uid, phone)
        else:
            print("\n📊 ШАГ 7: Пропускаем — нет идентификаторов")
    else:
        print(f"\n📊 ШАГ 7: Пропускаем — лид не квалифицирован")

    # Итог
    print("\n" + "=" * 60)
    print("📋 ФИНАЛЬНЫЙ ИТОГ:")
    print(f"  Лид ID:       {LEAD_ID}")
    print(f"  _ym_uid:      {ym_uid or '❌ не найден'}")
    print(f"  Телефон:      {phone or '❌ нет'}")
    print(f"  Звонков:      {len(calls)}")
    print(f"  Аудио:        {'✅' if audio_url else '❌'}")
    print(f"  Транскрипт:   {'✅' if transcript else '❌'}")
    if analysis:
        print(f"  Город:        {analysis.get('city') or '❌'}")
        print(f"  Долг:         {analysis.get('debt_amount') or '❌'}")
        print(f"  Qualified:    {'✅' if analysis.get('qualified') else '❌'}")
    print(f"  Метрика:      {'✅ отправлено' if metrika_sent else '❌ не отправлено'}")
    print("=" * 60)