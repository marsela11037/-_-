"""
Тест класса Speaker
"""
import os
import sys
import json
import threading
import tempfile
import wave
import numpy as np
import sounddevice as sd

# Копируем класс Speaker
class Speaker:
    """Улучшенный голосовой вывод с поддержкой Piper TTS."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._engine = None
        self._piper_model = None
        self._use_piper = False
        self._init_engine()
        print("[TTS] Инициализация голоса...")

    def _init_engine(self):
        """Инициализация TTS движка (Piper или pyttsx3)."""
        if self._try_init_piper():
            print("[TTS] ✅ Используется Piper TTS (высокое качество)")
            return
        
        print("[TTS] ⚠ Piper TTS не найден, используется pyttsx3")
        self._init_pyttsx3()

    def _try_init_piper(self):
        """Попытка инициализации Piper TTS."""
        try:
            if not os.path.exists("piper_config.txt"):
                return False
            
            with open("piper_config.txt", "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")
                if len(lines) < 3:
                    return False
                voice_name = lines[0].strip()
                model_path = lines[1].strip()
                config_path = lines[2].strip()
            
            if not os.path.exists(model_path) or not os.path.exists(config_path):
                return False
            
            from piper import PiperVoice
            
            self._piper_model = PiperVoice.load(model_path, config_path=config_path)
            self._use_piper = True
            print(f"[TTS] Загружен голос Piper: {voice_name}")
            return True
            
        except ImportError:
            print("[TTS] Библиотека piper-tts не установлена")
            return False
        except Exception as e:
            print(f"[TTS] Ошибка загрузки Piper: {e}")
            return False

    def _init_pyttsx3(self):
        """Инициализация pyttsx3 с оптимальными настройками."""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', 170)
            self._engine.setProperty('volume', 1.0)
        except Exception as e:
            print(f"[TTS] Ошибка инициализации pyttsx3: {e}")
            self._engine = None

    def say(self, text: str):
        """Произнести текст с улучшенным качеством."""
        if not text:
            return
        
        print(f"[TTS] Произношу: '{text}'")
        
        def _speak():
            with self._lock:
                try:
                    if self._use_piper and self._piper_model:
                        print("[TTS] Используется Piper TTS")
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                            tmp_filename = tmp_file.name
                        
                        print(f"[TTS] Генерация аудио в {tmp_filename}")
                        with wave.open(tmp_filename, "wb") as wav_file:
                            wav_file.setnchannels(1)
                            wav_file.setsampwidth(2)
                            wav_file.setframerate(self._piper_model.config.sample_rate)
                            self._piper_model.synthesize(text, wav_file)
                        
                        print("[TTS] Чтение аудио файла")
                        with wave.open(tmp_filename, "rb") as wf:
                            audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                            sample_rate = wf.getframerate()
                        
                        print(f"[TTS] Воспроизведение (sample_rate={sample_rate})")
                        sd.play(audio_data, sample_rate)
                        sd.wait()
                        print("[TTS] Воспроизведение завершено")
                        
                        try:
                            os.remove(tmp_filename)
                        except:
                            pass
                        
                    elif self._engine:
                        print("[TTS] Используется pyttsx3")
                        self._engine.say(text)
                        self._engine.runAndWait()
                        
                except Exception as e:
                    print(f"[TTS] Ошибка воспроизведения: {e}")
                    import traceback
                    traceback.print_exc()
        
        thread = threading.Thread(target=_speak, daemon=False)
        thread.start()
        thread.join()  # Ждём завершения

# Тест
print("=" * 60)
print("ТЕСТ КЛАССА SPEAKER")
print("=" * 60)

speaker = Speaker()

print("\n1. Тест короткой фразы:")
speaker.say("Да")

print("\n2. Тест длинной фразы:")
speaker.say("Привет! Я голосовой ассистент Джо. Готов к работе!")

print("\n3. Тест команды:")
speaker.say("Открываю ютуб")

print("\n✅ Тест завершён!")
