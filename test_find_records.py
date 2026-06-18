import speech_recognition as sr
from pydub import AudioSegment
import json
from vosk import Model, KaldiRecognizer, SetLogLevel
import sys
import wave
from redis import Redis
from rq import Queue
from fast_bitrix24 import Bitrix
import requests

r = Redis(host="192.168.210.150", port=6379)
q = Queue(name="task_server_TenChat", connection=r)

webhook = 'https://xn--24-9kc.xn--d1ao9c.xn--p1ai/rest/1638/imif9nsux99l0hnu/'
b = Bitrix(webhook)

MODEL_PATH = '/home/dmitry/Загрузки/vosk-model-ru-0.42'
AUDIO_FILE = '/home/dmitry/Рабочий стол/airflow/audio_file.wav'
MP3_FILE = '/home/dmitry/Рабочий стол/airflow/audio_file.mp3'

import mysql.connector

cnx = mysql.connector.connect(
    user='mufer',
    password='vRZVgh6c',
    host='localhost',
    database='data_collection'
)
cursor = cnx.cursor()

query = """
    SELECT ID
    FROM (
      SELECT ID, CRM_ENTITY_ID,
            ROW_NUMBER() OVER (PARTITION BY CRM_ENTITY_ID ORDER BY CALL_START_DATE ASC, CALL_DURATION ASC, ID ASC) AS row_num
      FROM calls
      WHERE CALL_DURATION >= 60
        AND CALL_FAILED_CODE = '200'
        AND CRM_ENTITY_TYPE = 'LEAD'
    ) AS subquery
    WHERE row_num = 1
    LIMIT 5000
"""

cursor.execute(query)
results = cursor.fetchall()

cursor.close()
cnx.close()

for row in results:
    idCall = row[0]

    if idCall not in [14574868]:

        voximplant = b.get_all(
            'voximplant.statistic.get',
            params={
                'filter': {
                    'ID': idCall,
                },
            }
        )
        if voximplant:
            call_record_url = voximplant[0]['CALL_RECORD_URL']
            filename = f'{idCall}_audio_file.mp3'

            response = requests.get(call_record_url)
            if response.status_code == 200:
                with open(filename, 'wb') as file:
                    file.write(response.content)
                print(f'Аудиофайл успешно загружен как {filename}')

                audio = AudioSegment.from_file(filename, format='mp3')
                filename = f'{idCall}_audio_file.wav'
                audio.export(filename, format='wav')

                print('Файл успешно сконвертирован в WAV!')

                # Разделение по каналам
                audio_data = AudioSegment.from_wav(filename)

                left_channel = audio_data.split_to_mono()[0]
                right_channel = audio_data.split_to_mono()[1]

                left_channel.export(f'/home/dmitry/Рабочий стол/airflow/{idCall}_left_channel.wav', format='wav')
                right_channel.export(f'/home/dmitry/Рабочий стол/airflow/{idCall}_right_channel.wav', format='wav')

                # Транскрибация аудио
                channels = [
                    {'channel': 'left', 'path': f'/home/dmitry/Рабочий стол/airflow/{idCall}_left_channel.wav'},
                    {'channel': 'right', 'path': f'/home/dmitry/Рабочий стол/airflow/{idCall}_right_channel.wav'}
                ]

                results = []
                for row in channels:
                    channel = row['channel']
                    path = row['path']

                    if channel == 'left':
                        user = 'client'
                    else:
                        user = 'manager'

                    SetLogLevel(0)

                    if len(sys.argv) == 2:
                        wf = wave.open(sys.argv[1], 'rb')
                    else:
                        wf = wave.open(path, 'rb')

                    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != 'NONE':
                        print ('Audio file must be WAV format mono PCM.')
                        exit (1)

                    model = Model(MODEL_PATH)

                    rec = KaldiRecognizer(model, wf.getframerate())
                    rec.SetWords(True)

                    TimeJson = []
                    while True:
                        data = wf.readframes(4000)
                        if len(data) == 0:
                            break
                        if rec.AcceptWaveform(data):
                            result = json.loads(rec.Result())

                            if 'text' in result:
                                words = result.get('result', [])

                                if words:
                                    start = words[0]['start']
                                    end = words[-1]['end']

                                    TimeJson.append({'start': start, 'end': end})

                    print('time:', TimeJson)

                    def split_audio_by_json_time_ranges(audio_file, time_ranges):
                        audio_data = AudioSegment.from_wav(audio_file)

                        for idx, trange in enumerate(time_ranges):
                            start_time = int((trange['start'] - 1) * 1000)
                            end_time = int((trange['end'] + 1) * 1000)

                            segment = audio_data[start_time:end_time]
                            segment.export(f"{idCall}_temp_segment_{idx}.wav", format="wav")

                            try:
                                recognizer = sr.Recognizer()
                                with sr.AudioFile(f"{idCall}_temp_segment_{idx}.wav") as source:
                                    audio_data_segment = recognizer.record(source)
                                    text = recognizer.recognize_google(audio_data_segment, language="ru-RU")
                                    results.append({user: text, 'start': trange['start'], 'end': trange['end']})
                                    print(f"Segment {idx+1} - Text: {text}")
                            except:
                                print(f"Segment {idx+1} - Text: UnknownValueError")

                    split_audio_by_json_time_ranges(path, TimeJson)

                result_sorted = sorted(results, key=lambda x: x['start'])

                print(result_sorted)

                final_results = []
                keys_to_remove = ["start", "end"]
                for result in result_sorted:
                    processed_result = {key: value for key, value in result.items() if key not in keys_to_remove}
                    final_results.append(processed_result)

                wf.close()

                final_output = []
                temp = {}

                for item in final_results:
                    key, value = list(item.items())[0]
                    if key in temp:
                        temp[key] += '. ' + value
                    else:
                        if temp:
                            final_output.append(temp)
                        temp = {key: value}

                final_output.append(temp)

                final_txt = {'idCall': idCall, 'final_output': final_output}
                task_add = q.enqueue("my_module.task_server_TenChat", json.dumps(final_txt))

                id_task = task_add.id
                print("ID новой задачи:", id_task)

            else:
                print('Ошибка при загрузке аудиофайла. Пожалуйста, проверьте ссылку и попробуйте снова.')