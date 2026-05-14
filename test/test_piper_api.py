"""
Тест API Piper TTS
"""
import os

# Загружаем Piper
with open("piper_config.txt", "r", encoding="utf-8") as f:
    lines = f.read().strip().split("\n")
    model_path = lines[1].strip()
    config_path = lines[2].strip()

from piper import PiperVoice
voice = PiperVoice.load(model_path, config_path=config_path)

# Проверяем методы
print("Методы PiperVoice:")
for attr in dir(voice):
    if not attr.startswith('_'):
        print(f"  - {attr}")

# Проверяем synthesize
print("\nПроверяем synthesize:")
import inspect
sig = inspect.signature(voice.synthesize)
print(f"Сигнатура: {sig}")

# Пробуем использовать synthesize_stream
print("\nПроверяем synthesize_stream:")
if hasattr(voice, 'synthesize_stream'):
    sig = inspect.signature(voice.synthesize_stream)
    print(f"Сигнатура: {sig}")
    
    # Пробуем
    print("\nТест synthesize_stream:")
    audio_chunks = list(voice.synthesize_stream("Привет"))
    print(f"Получено чанков: {len(audio_chunks)}")
    if audio_chunks:
        print(f"Размер первого чанка: {len(audio_chunks[0])} байт")
