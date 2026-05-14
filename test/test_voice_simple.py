"""
Простой тест голоса ассистента
"""
import os
import sys
import wave
import tempfile
import numpy as np
import sounddevice as sd

# Проверяем Piper
if not os.path.exists("piper_config.txt"):
    print("❌ Piper не настроен")
    exit(1)

# Читаем конфиг
with open("piper_config.txt", "r", encoding="utf-8") as f:
    lines = f.read().strip().split("\n")
    model_path = lines[1].strip()
    config_path = lines[2].strip()

print("Загрузка Piper...")
from piper import PiperVoice
voice = PiperVoice.load(model_path, config_path=config_path)

print("✅ Piper загружен")

# Тестовые фразы
phrases = [
    "Да",
    "Привет! Чем помочь?",
    "Открываю ютуб",
    "Включаю контр страйк",
    "Сейчас пятнадцать часов двадцать минут"
]

for i, text in enumerate(phrases, 1):
    print(f"\n{i}. Говорю: '{text}'")
    
    # Создаём временный файл
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_filename = tmp_file.name
    
    # Генерируем аудио
    with wave.open(tmp_filename, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(voice.config.sample_rate)
        voice.synthesize(text, wav_file)
    
    # Читаем и воспроизводим
    with wave.open(tmp_filename, "rb") as wf:
        audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        sample_rate = wf.getframerate()
    
    # Воспроизводим
    sd.play(audio_data, sample_rate)
    sd.wait()
    
    # Удаляем
    os.remove(tmp_filename)

print("\n✅ Все фразы произнесены!")
