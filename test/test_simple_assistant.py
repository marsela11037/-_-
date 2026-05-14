"""
Простой тест ассистента без GUI
"""
import os
import sys
import json
import queue
import threading
import tempfile
import wave
import numpy as np
import sounddevice as sd
from vosk import Model, KaldiRecognizer

# Загружаем Piper
print("Загрузка Piper TTS...")
if not os.path.exists("piper_config.txt"):
    print("❌ Piper не настроен")
    exit(1)

with open("piper_config.txt", "r", encoding="utf-8") as f:
    lines = f.read().strip().split("\n")
    model_path = lines[1].strip()
    config_path = lines[2].strip()

from piper import PiperVoice
piper_voice = PiperVoice.load(model_path, config_path=config_path)
print("✅ Piper TTS загружен")

def speak(text):
    """Произнести текст"""
    print(f"\n[SPEAK] Говорю: '{text}'")
    
    try:
        # Создаём временный файл
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_filename = tmp_file.name
        
        # Генерируем аудио
        with wave.open(tmp_filename, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(piper_voice.config.sample_rate)
            piper_voice.synthesize(text, wav_file)
        
        # Читаем и воспроизводим
        with wave.open(tmp_filename, "rb") as wf:
            audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            sample_rate = wf.getframerate()
        
        print(f"[SPEAK] Воспроизведение (rate={sample_rate}, len={len(audio_data)})")
        sd.play(audio_data, sample_rate)
        sd.wait()
        print("[SPEAK] ✅ Завершено")
        
        # Удаляем
        try:
            os.remove(tmp_filename)
        except:
            pass
            
    except Exception as e:
        print(f"[SPEAK] ❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

# Загружаем модель Vosk
print("\nЗагрузка модели Vosk...")
model = Model("model")
print("✅ Модель Vosk загружена")

# Распознавание
print("\nЗапуск распознавания речи...")
print("Скажи: 'Джо привет'")

q = queue.Queue()
rec = KaldiRecognizer(model, 16000)

def audio_callback(indata, frames, time_info, status):
    q.put(bytes(indata))

try:
    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=audio_callback):
        print("🎤 Слушаю... (говори в микрофон)")
        
        while True:
            try:
                data = q.get(timeout=1)
            except queue.Empty:
                continue
            
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip().lower()
                
                if text:
                    print(f"\n📝 Распознано: '{text}'")
                    
                    # Проверяем имя
                    if "джо" in text or "jo" in text:
                        print("✅ Услышал имя 'Джо'!")
                        speak("Да")
                        
                        # Ждём команду
                        print("\n🎤 Слушаю команду...")
                        for _ in range(30):  # 30 попыток
                            try:
                                data = q.get(timeout=0.5)
                            except queue.Empty:
                                continue
                            
                            if rec.AcceptWaveform(data):
                                result = json.loads(rec.Result())
                                cmd_text = result.get("text", "").strip().lower()
                                
                                if cmd_text:
                                    print(f"\n📝 Команда: '{cmd_text}'")
                                    
                                    if "привет" in cmd_text:
                                        speak("Привет! Чем помочь?")
                                    elif "ютуб" in cmd_text:
                                        speak("Открываю ютуб")
                                    else:
                                        speak(f"Команда: {cmd_text}")
                                    
                                    break
                        break
            else:
                partial = json.loads(rec.PartialResult())
                partial_text = partial.get("partial", "").strip().lower()
                if partial_text:
                    print(f"  (частичный результат: '{partial_text}')")

except KeyboardInterrupt:
    print("\n\nОстановлено пользователем")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
