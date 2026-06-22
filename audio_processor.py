# audio_processor.py
from typing import Optional, List
import os
import requests
import urllib3
from pydub import AudioSegment
from faster_whisper import WhisperModel
from config import TEMP_DIR

urllib3.disable_warnings()
os.makedirs(TEMP_DIR, exist_ok=True)

# ===== Загружаем модель один раз при старте =====
print("🔄 Загрузка Whisper модели...")
_whisper_model = WhisperModel(
    "medium",
    device="cpu",
    compute_type="int8"
)
print("✅ Whisper модель загружена")


def download_audio(url: str, call_id: str) -> Optional[str]:
    print(f"   📥 Скачиваем аудио...")
    try:
        resp = requests.get(url, timeout=120, verify=False)
        if resp.status_code != 200 or len(resp.content) < 5000:
            print(f"   ❌ Ошибка скачивания: HTTP {resp.status_code}")
            return None
        mp3_path = os.path.join(TEMP_DIR, f"{call_id}_audio.mp3")
        with open(mp3_path, 'wb') as f:
            f.write(resp.content)
        print(f"   ✅ Скачан: {len(resp.content)//1024} KB")
        return mp3_path
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return None


def transcribe_audio(mp3_path: str, call_id: str) -> Optional[str]:
    """
    Транскрибируем MP3 через Faster-Whisper
    Весь файл целиком — без нарезки
    """
    try:
        print(f"   🎙️ Транскрибируем через Faster-Whisper...")

        segments, info = _whisper_model.transcribe(
            mp3_path,
            language="ru",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=True,
            initial_prompt=(
                "Это запись телефонного разговора между менеджером "
                "и клиентом по теме банкротства и списания долгов. "
                "Менеджер предлагает услуги по банкротству, клиент "
                "рассказывает о своих долгах, городе проживания и "
                "финансовой ситуации."
            )
        )

        texts = []
        for segment in segments:
            text = segment.text.strip()
            if text:
                texts.append(text)

        full_text = " ".join(texts)
        print(f"   ✅ Транскрипт: {len(full_text)} символов")
        print(f"   📄 Текст: {full_text[:300]}")

        return full_text

    except Exception as e:
        print(f"   ❌ Ошибка транскрибации: {e}")
        return None


def cleanup_files(paths: list):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass


def process_call_audio(call_record_url: str, call_id: str) -> Optional[dict]:
    print(f"\n   🔊 Обрабатываем звонок {call_id}...")

    mp3_path = None

    try:
        # 1. Скачиваем MP3
        mp3_path = download_audio(call_record_url, call_id)
        if not mp3_path:
            return None

        # 2. Транскрибируем целиком через Faster-Whisper
        full_text = transcribe_audio(mp3_path, call_id)

        cleanup_files([mp3_path])

        if not full_text:
            return None

        return {
            'call_id':   call_id,
            'full_text': full_text
        }

    except Exception as e:
        print(f"   ❌ Критическая ошибка: {e}")
        cleanup_files([mp3_path])
        return None