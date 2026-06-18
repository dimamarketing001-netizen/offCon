"""
Flask endpoint для регистрации в Б24 как AI сервис категории 'call'
Б24 будет присылать сюда аудио файлы звонков для транскрибации
"""

from flask import Flask, request, jsonify
import requests
import threading
from groq_client import transcribe_audio

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """
    Этот endpoint Б24 проверяет при регистрации
    ОБЯЗАТЕЛЬНО должен возвращать 200
    """
    return jsonify({"status": "ok"}), 200


@app.route('/b24/ai/call', methods=['POST'])
def handle_call_transcription():
    """
    Б24 присылает сюда запрос на транскрибацию звонка
    Мы должны ответить за 5 секунд и уйти в async
    """
    data = request.json

    print(f"📞 Получен запрос на транскрибацию от Б24")

    # Извлекаем данные из запроса Б24
    prompt = data.get('prompt', {})

    # Для категории 'call' prompt это объект
    if isinstance(prompt, dict):
        audio_url = prompt.get('file')
        file_extension = prompt.get('fileExtension', '')
        fields = prompt.get('fields', {})
    else:
        audio_url = prompt
        fields = {}

    callback_url = data.get('callbackUrl')
    error_callback_url = data.get('errorCallbackUrl')
    ttl = data.get('ttl', 300)

    if not audio_url or not callback_url:
        return jsonify({"result": "OK"}), 200

    # Обрабатываем асинхронно чтобы ответить быстро
    thread = threading.Thread(
        target=process_transcription_async,
        args=(audio_url, callback_url, error_callback_url)
    )
    thread.daemon = True
    thread.start()

    # Отвечаем Б24 сразу
    return jsonify({"result": "OK"}), 202


def process_transcription_async(audio_url: str, callback_url: str, error_callback_url: str):
    """Асинхронная транскрибация и отправка результата"""

    try:
        # Транскрибируем
        text = transcribe_audio(audio_url)

        if text:
            # Отправляем результат в Б24
            response = requests.post(callback_url, json={
                "text": text
            }, timeout=30)
            print(f"✅ Результат отправлен в Б24: {response.status_code}")
        else:
            # Сообщаем об ошибке
            requests.post(error_callback_url, json={
                "error": "transcription_failed",
                "error_description": "Не удалось распознать аудио"
            }, timeout=30)

    except Exception as e:
        print(f"❌ Ошибка async транскрибации: {e}")
        try:
            requests.post(error_callback_url, json={
                "error": str(e)
            }, timeout=30)
        except:
            pass


def register_ai_engine(b24_webhook: str, completions_url: str):
    """
    Регистрируем наш сервис в Б24 как AI движок категории 'call'
    Запустить один раз!
    """
    url = f"{b24_webhook}ai.engine.register.json"

    payload = {
        "name": "Groq Whisper Транскрибация",
        "code": "groq_whisper_call",
        "category": "call",
        "completions_url": completions_url,
        "settings": {
            "code_alias": "Groq Whisper",
            "model_context_type": "token",
            "model_context_limit": 15666
        }
    }

    response = requests.post(url, json=payload)
    result = response.json()

    if 'result' in result:
        print(f"✅ AI Engine зарегистрирован! ID: {result['result']}")
    else:
        print(f"❌ Ошибка регистрации: {result}")

    return result


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)