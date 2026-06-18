from typing import Optional, List, Dict
import os
import requests
import urllib3
import tempfile
import speech_recognition as sr
from pydub import AudioSegment
from config import TEMP_DIR, MIN_CALL_DURATION

urllib3.disable_warnings()

os.makedirs(TEMP_DIR, exist_ok=True)

def download_audio(url: str, call_id: str) -> Optional[str]:
    print(f"   📥 Скачиваем аудио...")
    try:
        resp = requests.get(url, timeout=120, verify=False)
        if resp.status_code != 200:
            print(f"   ❌ HTTP {resp.status_code}")
            return None
        if len(resp.content) < 5000:
            print(f"   ❌ Файл слишком маленький")
            return None
        mp3_path = os.path.join(TEMP_DIR, f"{call_id}_audio.mp3")
        with open(mp3_path, 'wb') as f:
            f.write(resp.content)
        print(f"   ✅ Скачан: {len(resp.content)//1024} KB")
        return mp3_path
    except Exception as e:
        print(f"   ❌ Ошибка скачивания: {e}")
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


def split_channels(wav_path: str, call_id: str) -> Optional[dict]:
    try:
        audio = AudioSegment.from_wav(wav_path)

        if audio.channels == 1:
            print("   ⚠️ Моно файл — один канал для обоих")
            mono_path = os.path.join(TEMP_DIR, f"{call_id}_mono.wav")
            audio.export(mono_path, format='wav')
            return {'client': mono_path, 'manager': mono_path}

        channels = audio.split_to_mono()
        client_path  = os.path.join(TEMP_DIR, f"{call_id}_client.wav")
        manager_path = os.path.join(TEMP_DIR, f"{call_id}_manager.wav")
        channels[0].export(client_path,  format='wav')
        channels[1].export(manager_path, format='wav')

        print(f"   ✅ Каналы разделены: клиент + менеджер")
        return {'client': client_path, 'manager': manager_path}

    except Exception as e:
        print(f"   ❌ Ошибка разделения каналов: {e}")
        return None


def split_into_segments(wav_path: str, call_id: str, role: str, segment_duration: int = 59) -> List[str]:
    try:
        audio = AudioSegment.from_wav(wav_path)
        duration_ms  = len(audio)
        segment_ms   = segment_duration * 1000
        segments     = []
        idx          = 0
        start        = 0

        while start < duration_ms:
            end     = min(start + segment_ms, duration_ms)
            segment = audio[start:end]
            seg_path = os.path.join(TEMP_DIR, f"{call_id}_{role}_seg{idx}.wav")
            segment.export(seg_path, format='wav')
            segments.append(seg_path)
            start = end
            idx  += 1

        print(f"   ✅ Нарезано {len(segments)} сегментов [{role}]")
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
    except sr.RequestError as e:
        print(f"   ⚠️ Google API ошибка: {e}")
        return ""
    except Exception as e:
        print(f"   ⚠️ Ошибка сегмента: {e}")
        return ""


def transcribe_channel(wav_path: str, call_id: str, role: str) -> str:
    print(f"   🎙️ Транскрибируем [{role}]...")
    segments = split_into_segments(wav_path, call_id, role)

    if not segments:
        return ""

    texts = []
    for i, seg_path in enumerate(segments):
        text = transcribe_segment(seg_path)
        if text:
            texts.append(text)
            print(f"      Сег {i+1}/{len(segments)}: {text[:60]}...")
        else:
            print(f"      Сег {i+1}/{len(segments)}: (тишина)")
        try:
            os.remove(seg_path)
        except:
            pass

    full_text = ". ".join(texts)
    print(f"   ✅ [{role}]: {len(full_text)} символов")
    return full_text


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
        mp3_path = download_audio(call_record_url, call_id)
        if not mp3_path:
            return None

        wav_path = convert_to_wav(mp3_path, call_id)
        if not wav_path:
            return None

        channels = split_channels(wav_path, call_id)
        if not channels:
            return None

        client_text  = transcribe_channel(channels['client'],  call_id, 'client')
        manager_text = transcribe_channel(channels['manager'], call_id, 'manager')

        cleanup_files([mp3_path, wav_path])

        if channels['client'] != channels['manager']:
            cleanup_files([channels['client'], channels['manager']])
        else:
            cleanup_files([channels['client']])

        return {
            'call_id':   call_id,
            'client':    client_text,
            'manager':   manager_text,
            'full_text': f"Клиент: {client_text}\nМенеджер: {manager_text}"
        }

    except Exception as e:
        print(f"   ❌ Критическая ошибка: {e}")
        cleanup_files([mp3_path, wav_path])
        return None
