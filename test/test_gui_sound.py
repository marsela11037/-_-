"""
Тест звука в GUI приложении
"""
import tkinter as tk
import threading
import time
import os
import tempfile
import wave
import numpy as np
import sounddevice as sd

# Загружаем Piper
if not os.path.exists("piper_config.txt"):
    print("❌ Piper не настроен")
    exit(1)

with open("piper_config.txt", "r", encoding="utf-8") as f:
    lines = f.read().strip().split("\n")
    model_path = lines[1].strip()
    config_path = lines[2].strip()

print("Загрузка Piper...")
from piper import PiperVoice
voice = PiperVoice.load(model_path, config_path=config_path)
print("✅ Piper загружен")

def speak(text):
    """Произнести текст"""
    print(f"[SPEAK] Начало: '{text}'")
    
    def _do_speak():
        try:
            # Создаём временный файл
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_filename = tmp_file.name
            
            print(f"[SPEAK] Генерация в {tmp_filename}")
            # Генерируем аудио
            with wave.open(tmp_filename, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(voice.config.sample_rate)
                voice.synthesize(text, wav_file)
            
            print("[SPEAK] Чтение файла")
            # Читаем и воспроизводим
            with wave.open(tmp_filename, "rb") as wf:
                audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                sample_rate = wf.getframerate()
            
            print(f"[SPEAK] Воспроизведение (rate={sample_rate})")
            # Воспроизводим
            sd.play(audio_data, sample_rate)
            sd.wait()
            print("[SPEAK] Завершено")
            
            # Удаляем
            try:
                os.remove(tmp_filename)
            except:
                pass
                
        except Exception as e:
            print(f"[SPEAK] Ошибка: {e}")
            import traceback
            traceback.print_exc()
    
    # Запускаем в потоке
    thread = threading.Thread(target=_do_speak, daemon=False)
    thread.start()

# Создаём GUI
root = tk.Tk()
root.title("Тест звука в GUI")
root.geometry("400x300")

label = tk.Label(root, text="Нажмите кнопку для теста звука", font=("Arial", 12))
label.pack(pady=20)

def test1():
    label.config(text="Говорю: 'Да'")
    speak("Да")

def test2():
    label.config(text="Говорю: 'Привет'")
    speak("Привет! Я голосовой ассистент Джо.")

def test3():
    label.config(text="Говорю: 'Открываю ютуб'")
    speak("Открываю ютуб")

btn1 = tk.Button(root, text="Тест 1: 'Да'", command=test1, font=("Arial", 10), padx=20, pady=10)
btn1.pack(pady=5)

btn2 = tk.Button(root, text="Тест 2: 'Привет'", command=test2, font=("Arial", 10), padx=20, pady=10)
btn2.pack(pady=5)

btn3 = tk.Button(root, text="Тест 3: 'Открываю ютуб'", command=test3, font=("Arial", 10), padx=20, pady=10)
btn3.pack(pady=5)

print("GUI запущен. Нажмите кнопки для теста.")
root.mainloop()
