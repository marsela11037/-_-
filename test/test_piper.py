"""
Тест Piper TTS голоса
"""
import os
import wave
import io
import numpy as np
import sounddevice as sd

print("=" * 60)
print("ТЕСТ PIPER TTS")
print("=" * 60)

# Проверяем наличие конфига
if not os.path.exists("piper_config.txt"):
    print("❌ Файл piper_config.txt не найден!")
    print("Запустите: python install_piper.py")
    exit(1)

# Читаем конфиг
with open("piper_config.txt", "r", encoding="utf-8") as f:
    lines = f.read().strip().split("\n")
    voice_name = lines[0].strip()
    model_path = lines[1].strip()
    config_path = lines[2].strip()

print(f"\n✅ Голос: {voice_name}")
print(f"✅ Модель: {model_path}")
print(f"✅ Конфиг: {config_path}")

# Проверяем файлы
if not os.path.exists(model_path):
    print(f"❌ Модель не найдена: {model_path}")
    exit(1)

if not os.path.exists(config_path):
    print(f"❌ Конфиг не найден: {config_path}")
    exit(1)

print("\n📦 Загрузка модели Piper...")

try:
    from piper import PiperVoice
    
    # Загружаем модель
    voice = PiperVoice.load(model_path, config_path=config_path)
    print("✅ Модель загружена успешно!")
    
    # Тестовая фраза
    test_text = "Привет! Я голосовой ассистент Джо. Готов к работе!"
    
    print(f"\n🎤 Произношу: '{test_text}'")
    print("⏳ Генерация аудио...")
    
    # Генерируем аудио в файл
    output_file = "test_output.wav"
    with wave.open(output_file, "wb") as wav_file:
        wav_file.setnchannels(1)  # Моно
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(voice.config.sample_rate)
        voice.synthesize(test_text, wav_file)
    
    print(f"✅ Аудио сгенерировано в файл: {output_file}")
    print("🔊 Воспроизведение...")
    
    # Читаем и воспроизводим
    with wave.open(output_file, "rb") as wf:
        audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        sample_rate = wf.getframerate()
    
    # Воспроизводим
    sd.play(audio_data, sample_rate)
    sd.wait()
    
    # Удаляем временный файл
    os.remove(output_file)
    
    print("\n" + "=" * 60)
    print("✅ ТЕСТ УСПЕШНО ЗАВЕРШЁН!")
    print("=" * 60)
    print("\n🚀 Теперь запустите: python voice_assistant.py")
    print("   Ассистент будет использовать этот голос!")
    
except ImportError as e:
    print(f"\n❌ Ошибка импорта: {e}")
    print("\nУстановите piper-tts:")
    print("  python -m pip install piper-tts")
    
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
