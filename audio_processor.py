from typing import Optional, List
import os
import requests
import urllib3
import speech_recognition as sr
from pydub import AudioSegment
from config import TEMP_DIR

urllib3.disable_warnings()
os.makedirs(TEMP_DIR, exist_ok=True)


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


def convert_to_wav(mp3_path: str, call_id: str) -> Optional[str]:
    try:
        wav_path = os.path.join(TEMP_DIR, f"{call_id}_audio.wav")
        audio = AudioSegment.from_file(mp3_path, format='mp3')
        audio.export(wav_path, format='wav')
        print(f"   ✅ Конвертирован в WAV")
        return wav_path
    except Exception as e:
        print(f"   ❌ Ошибка конвертации: {e}")
        return None


def split_into_segments(wav_path: str, call_id: str, segment_duration: int = 59) -> List[str]:
    try:
        audio      = AudioSegment.from_wav(wav_path)
        duration_ms = len(audio)
        segment_ms  = segment_duration * 1000
        segments    = []
        idx = 0
        start = 0

        while start < duration_ms:
            end      = min(start + segment_ms, duration_ms)
            segment  = audio[start:end]
            seg_path = os.path.join(TEMP_DIR, f"{call_id}_seg{idx}.wav")
            segment.export(seg_path, format='wav')
            segments.append(seg_path)
            start = end
            idx  += 1

        print(f"   ✅ Нарезано {len(segments)} сегментов по {segment_duration}с")
        return segments
    except Exception as e:
        print(f"   ❌ Ошибка нарезки: {e}")
        return []


def transcribe_segment(seg_path: str) -> str:
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(seg_path) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="ru-RU")
        return text
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        print(f"   ⚠️ Ошибка сегмента: {e}")
        return ""


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
    wav_path = None

    try:
        # 1. Скачиваем
        mp3_path = download_audio(call_record_url, call_id)
        if not mp3_path:
            return None

        # 2. Конвертируем
        wav_path = convert_to_wav(mp3_path, call_id)
        if not wav_path:
            return None

        # 3. Нарезаем на сегменты
        segments = split_into_segments(wav_path, call_id)
        if not segments:
            return None

        # 4. Транскрибируем каждый сегмент
        texts = []
        for i, seg_path in enumerate(segments):
            text = transcribe_segment(seg_path)
            if text:
                texts.append(text)
                print(f"      Сег {i+1}/{len(segments)}: {text[:80]}...")
            else:
                print(f"      Сег {i+1}/{len(segments)}: (тишина)")
            cleanup_files([seg_path])

        # 5. Склеиваем
        full_text = ". ".join(texts)
        print(f"   ✅ Транскрипт: {len(full_text)} символов")
        print(f"   📄 Полный текст:\n   {full_text}")

        cleanup_files([mp3_path, wav_path])

        return {
            'call_id':   call_id,
            'client':    full_text,
            'manager':   full_text,
            'full_text': full_text
        }

    except Exception as e:
        print(f"   ❌ Критическая ошибка: {e}")
        cleanup_files([mp3_path, wav_path])
        return None