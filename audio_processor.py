# audio_processor.py
from typing import Optional, List
import os
import time
import traceback
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
        # --- Получаем размер файла ---
        file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
        print(f"   🎙️ Транскрибируем через Faster-Whisper...")
        print(f"   📁 Размер файла: {file_size_mb:.2f} MB")
        print(f"   ⚙️  Устройство: CPU | Модель: medium | int8")
        print(f"   ⏳ Запускаем transcribe()...")

        start_time = time.time()

        # --- Запуск транскрибации ---
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

        print(f"   ✅ transcribe() вернул генератор за {time.time() - start_time:.1f}с")
        print(f"   🌍 Определён язык: {info.language} (вероятность: {info.language_probability:.2f})")
        print(f"   ⏱️  Длительность аудио: {info.duration:.1f} сек ({info.duration / 60:.1f} мин)")
        print(f"   🔄 Начинаем итерацию по сегментам...")

        # --- Итерация с логами ---
        texts = []
        segment_count = 0
        last_log_time = time.time()

        for segment in segments:
            segment_count += 1
            text = segment.text.strip()

            # Лог каждые 5 секунд реального времени
            now = time.time()
            if now - last_log_time >= 5:
                elapsed = now - start_time
                print(
                    f"   ⏳ Сегмент #{segment_count} | "
                    f"[{segment.start:.1f}s → {segment.end:.1f}s] | "
                    f"Прошло: {elapsed:.0f}с"
                )
                last_log_time = now

            if text:
                texts.append(text)
                # Первые 3 сегмента всегда логируем
                if segment_count <= 3:
                    print(f"   📝 [{segment.start:.1f}→{segment.end:.1f}] {text[:80]}")

        elapsed_total = time.time() - start_time
        print(f"   ✅ Итерация завершена: {segment_count} сегментов за {elapsed_total:.1f}с")

        full_text = " ".join(texts)
        print(f"   ✅ Транскрипт: {len(full_text)} символов")
        print(f"   📄 Текст (первые 300): {full_text[:300]}")

        return full_text if full_text else None

    except Exception as e:
        print(f"   ❌ Ошибка транскрибации: {e}")
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
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
        print(f"   🔍 Traceback:\n{traceback.format_exc()}")
        cleanup_files([mp3_path])
        return None