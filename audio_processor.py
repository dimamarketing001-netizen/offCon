"""
Скачивание, конвертация, разделение каналов и транскрибация аудио
Технология: pydub + Google Speech Recognition
"""

import os
import wave
import requests
import urllib3
import tempfile
import speech_recognition as sr
from pydub import AudioSegment
from config import TEMP_DIR, MIN_CALL_DURATION

urllib3.disable_warnings()

# Создаём папку для временных файлов
os.makedirs(TEMP_DIR, exist_ok=True)


def download_audio(url: str, call_id: str) -> str | None:
    """Скачиваем MP3 файл"""
    print(f"   📥 Скачиваем аудио...")

    try:
        resp = requests.get(url, timeout=120, verify=False)

        if resp.status_code != 200:
            print(f"   ❌ HTTP {resp.status_code}")
            return None

        if len(resp.content) < 5000:
            print(f"   ❌ Файл слишком маленький: {len(resp.content)} байт")
            return None

        mp3_path = os.path.join(TEMP_DIR, f"{call_id}_audio.mp3")
        with open(mp3_path, 'wb') as f:
            f.write(resp.content)

        print(f"   ✅ Скачан: {len(resp.content) // 1024} KB → {mp3_path}")
        return mp3_path

    except Exception as e:
        print(f"   ❌ Ошибка скачивания: {e}")
        return None


def convert_to_wav(mp3_path: str, call_id: str) -> str | None:
    """Конвертируем MP3 → WAV"""
    try:
        wav_path = os.path.join(TEMP_DIR, f"{call_id}_audio.wav")
        audio = AudioSegment.from_file(mp3_path, format='mp3')
        audio.export(wav_path, format='wav')
        print(f"   ✅ Конвертирован в WAV: {wav_path}")
        return wav_path

    except Exception as e:
        print(f"   ❌ Ошибка конвертации: {e}")
        return None


def split_channels(wav_path: str, call_id: str) -> dict | None:
    """
    Разделяем стерео на два канала:
    left  = клиент
    right = менеджер
    """
    try:
        audio = AudioSegment.from_wav(wav_path)

        # Если моно — дублируем
        if audio.channels == 1:
            print("   ⚠️ Моно файл — используем один канал для обоих")
            mono_path = os.path.join(TEMP_DIR, f"{call_id}_mono.wav")
            audio.export(mono_path, format='wav')
            return {
                'client': mono_path,
                'manager': mono_path
            }

        channels = audio.split_to_mono()

        client_path = os.path.join(TEMP_DIR, f"{call_id}_client.wav")  # left
        manager_path = os.path.join(TEMP_DIR, f"{call_id}_manager.wav")  # right

        channels[0].export(client_path, format='wav')
        channels[1].export(manager_path, format='wav')

        print(f"   ✅ Каналы разделены:")
        print(f"      Клиент:  {client_path}")
        print(f"      Менеджер: {manager_path}")

        return {
            'client': client_path,
            'manager': manager_path
        }

    except Exception as e:
        print(f"   ❌ Ошибка разделения каналов: {e}")
        return None


def split_into_segments(wav_path: str, call_id: str, role: str, segment_duration: int = 59) -> list:
    """
    Нарезаем WAV на сегменты по 59 секунд
    Возвращает список путей к сегментам
    """
    try:
        audio = AudioSegment.from_wav(wav_path)
        duration_ms = len(audio)
        segment_ms = segment_duration * 1000

        segments = []
        idx = 0
        start = 0

        while start < duration_ms:
            end = min(start + segment_ms, duration_ms)
            segment = audio[start:end]

            seg_path = os.path.join(TEMP_DIR, f"{call_id}_{role}_seg{idx}.wav")
            segment.export(seg_path, format='wav')
            segments.append(seg_path)

            start = end
            idx += 1

        print(f"   ✅ Нарезано {len(segments)} сегментов по {segment_duration}с [{role}]")
        return segments

    except Exception as e:
        print(f"   ❌ Ошибка нарезки: {e}")
        return []


def transcribe_segment(seg_path: str) -> str:
    """Транскрибируем один сегмент через Google Speech Recognition"""
    try:
        recognizer = sr.Recognizer()

        with sr.AudioFile(seg_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data, language="ru-RU")
        return text

    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        print(f"   ⚠️ Google API ошибка: {e}")
        return ""
    except Exception as e:
        print(f"   ⚠️ Ошибка сегмента: {e}")
        return ""


def transcribe_channel(wav_path: str, call_id: str, role: str) -> str:
    """
    Транскрибируем весь канал:
    1. Нарезаем на сегменты по 59 сек
    2. Каждый сегмент → Google Speech
    3. Склеиваем результат
    """
    print(f"   🎙️ Транскрибируем [{role}]...")

    segments = split_into_segments(wav_path, call_id, role)

    if not segments:
        return ""

    texts = []
    for i, seg_path in enumerate(segments):
        text = transcribe_segment(seg_path)
        if text:
            texts.append(text)
            print(f"      Сегмент {i + 1}/{len(segments)}: {text[:50]}...")
        else:
            print(f"      Сегмент {i + 1}/{len(segments)}: (тишина)")

        # Удаляем сегмент после обработки
        try:
            os.remove(seg_path)
        except:
            pass

    full_text = ". ".join(texts)
    print(f"   ✅ [{role}] транскрипт: {len(full_text)} символов")
    return full_text


def process_call_audio(call_record_url: str, call_id: str) -> dict | None:
    """
    Полная обработка одного звонка:
    1. Скачиваем MP3
    2. Конвертируем в WAV
    3. Разделяем на каналы
    4. Транскрибируем каждый канал
    5. Возвращаем тексты клиента и менеджера
    """
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

        # 3. Разделяем каналы
        channels = split_channels(wav_path, call_id)
        if not channels:
            return None

        # 4. Транскрибируем каждый канал
        client_text = transcribe_channel(channels['client'], call_id, 'client')
        manager_text = transcribe_channel(channels['manager'], call_id, 'manager')

        # 5. Удаляем временные файлы
        cleanup_files([
            mp3_path, wav_path,
            channels['client'], channels['manager']
        ])

        return {
            'call_id': call_id,
            'client': client_text,
            'manager': manager_text,
            'full_text': f"Клиент: {client_text}\nМенеджер: {manager_text}"
        }

    except Exception as e:
        print(f"   ❌ Критическая ошибка: {e}")
        cleanup_files([mp3_path, wav_path])
        return None


def cleanup_files(paths: list):
    """Удаляем временные файлы"""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass