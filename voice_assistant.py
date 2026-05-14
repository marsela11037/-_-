import os
import sys
import json
import queue
import threading
import subprocess
import datetime
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pyautogui
import numpy as np

# Vosk
try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

# Silero TTS
try:
    import torch
    import sounddevice as sd
    SILERO_AVAILABLE = True
except ImportError:
    SILERO_AVAILABLE = False
    print("⚠ Необходимые библиотеки не установлены. Установите: pip install torch sounddevice")

# ─────────────────────────────────────────────
#  Константы
# ─────────────────────────────────────────────
SAMPLE_RATE = 16000
MODEL_PATH = "model"          # папка с моделью Vosk
COMMANDS_FILE = "commands.json"
FORBIDDEN_COMMANDS = ["format c:", "del /f /s /q c:\\", "rm -rf /", "rmdir /s /q c:\\"]

# ─────────────────────────────────────────────
#  Нейросетевой синтез речи (Silero TTS)
# ─────────────────────────────────────────────
class NeuralSpeaker:
    """Нейросетевой голос на основе Silero TTS (офлайн, легкий)"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._sample_rate = 48000
        self._device = torch.device('cpu')
        self._load_model()
    
    def _load_model(self):
        """Загрузка модели Silero TTS для русского языка"""
        if not SILERO_AVAILABLE:
            print("[TTS] Torch или sounddevice не установлены")
            return
        
        try:
            print("[TTS] Загрузка нейросетевой модели Silero TTS...")
            print("[TTS] Это может занять 30-60 секунд при первом запуске...")
            
            # Загружаем модель для русского языка
            self._model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-models',
                model='silero_tts',
                language='ru',
                speaker='v3_1_ru'
            )
            self._model.to(self._device)
            
            print(f"[TTS] Модель загружена! Частота дискретизации: {self._sample_rate} Гц")
            print("[TTS] Нейросетевой голос готов к работе")
            
        except Exception as e:
            print(f"[TTS] Ошибка загрузки модели: {e}")
            print("[TTS] Проверьте подключение к интернету (модель скачивается при первом запуске)")
            self._model = None
    
    def say(self, text: str):
        """Синтез речи через нейросеть и воспроизведение"""
        if not text:
            return
        
        if self._model is None:
            print("[TTS] Модель не загружена, использую fallback")
            self._fallback_say(text)
            return
        
        def _speak():
            with self._lock:
                try:
                    # Генерация аудио через нейросеть
                    audio = self._model.apply_tts(
                        text=text,
                        speaker='xenia',  # xenia, aidar, baya, kseniya
                        sample_rate=self._sample_rate
                    )
                    
                    # Воспроизведение через sounddevice
                    sd.play(audio.cpu().numpy(), self._sample_rate)
                    sd.wait()  # Ждём окончания воспроизведения
                    
                except Exception as e:
                    print(f"[TTS] Ошибка синтеза: {e}")
                    self._fallback_say(text)
        
        threading.Thread(target=_speak, daemon=False).start()
    
    def _fallback_say(self, text: str):
        """Fallback-метод если Silero не работает"""
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            
            voices = speaker.GetVoices()
            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = voice.GetDescription()
                if "Irina" in desc or "Russian" in desc:
                    speaker.Voice = voice
                    break
            
            speaker.Rate = 0
            speaker.Volume = 100
            speaker.Speak(text, 1)
            
        except Exception as e:
            print(f"[TTS] Ошибка fallback: {e}")
            # Последняя попытка - через pyttsx3
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except:
                pass


# Создаём глобальный экземпляр спикера
speaker = NeuralSpeaker()


# ─────────────────────────────────────────────
#  Менеджер команд
# ─────────────────────────────────────────────
class CommandManager:
    """Хранит встроенные и пользовательские команды, выполняет их."""

    BUILTIN = {
        "открой калькулятор":   ("app",    "calc.exe", "Открываю калькулятор"),
        "открой блокнот":       ("app",    "notepad.exe", "Открываю блокнот"),
        "закрой окно":          ("hotkey", ["alt", "f4"], "Закрываю окно"),
        "выключи компьютер":    ("danger", "shutdown /s /t 0", "Выключаю компьютер"),
        "выключи пк":           ("danger", "shutdown /s /t 0", "Выключаю компьютер"),
        "выключи комп":         ("danger", "shutdown /s /t 0", "Выключаю компьютер"),
        "открой почту":         ("url",    "https://mail.ru", "Открываю почту"),
        "что нового":           ("url",    "https://news.yandex.ru", "Открываю новости"),
        "включи ютуб":          ("url",    "https://youtube.com", "Включаю ютуб"),
        "включи саундклауд":    ("url",    "https://soundcloud.com", "Включаю саундклауд"),
        "открой ютуб":          ("url",    "https://youtube.com", "Открываю ютуб"),
        "включи кс":            ("steam",  "730", "Включаю контр страйк"),
        "включи контр страйк":  ("steam",  "730", "Включаю контр страйк"),
        "включи дискорд":       ("app",    "discord", "Включаю дискорд"),
        "открой дискорд":       ("app",    "discord", "Открываю дискорд"),
        "заблокировать экран":  ("hotkey", ["win", "l"], "Блокирую экран"),
        "увеличь громкость":    ("volume", "+", "Я увеличил громкость"),
        "уменьши громкость":    ("volume", "-", "Я уменьшил громкость"),
        "громче":               ("volume", "+", "Громкость увеличена"),
        "тише":                 ("volume", "-", "Громкость уменьшена"),
        "какое сегодня число":  ("datetime", "date", None),
        "сколько времени":      ("datetime", "time", None),
        "который час":          ("datetime", "time", None),
        "какая дата":           ("datetime", "date", None),
        "привет":               ("reply",  None, "Привет! Чем помочь?"),
        "как дела":             ("reply",  None, "Всё отлично! Жду ваших команд."),
        "спасибо":              ("reply",  None, "Пожалуйста!"),
        "пока":                 ("reply",  None, "До свидания!"),
    }

    def __init__(self, app_callback):
        self._cb = app_callback
        self._user_commands: dict = {}
        self._load_user_commands()

    def _load_user_commands(self):
        if os.path.exists(COMMANDS_FILE):
            try:
                with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._user_commands = {
                    k: v for k, v in data.items()
                    if not k.startswith("_comment")
                }
            except Exception:
                self._user_commands = {}

    def save_user_commands(self):
        data = {"_comment": "Пользовательские команды. Формат: 'фраза': 'действие'"}
        data.update(self._user_commands)
        with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_user_command(self, phrase: str, action: str):
        self._user_commands[phrase.lower().strip()] = action
        self.save_user_commands()

    def get_all_phrases(self) -> list:
        return list(self.BUILTIN.keys()) + list(self._user_commands.keys())

    def execute(self, text: str, confirmed: bool = False) -> tuple[bool, str]:
        text = text.lower().strip()

        if text in self.BUILTIN:
            return self._run_builtin(text, self.BUILTIN[text], confirmed)

        if text in self._user_commands:
            return self._run_user(text, self._user_commands[text])

        if text.startswith("выполни команду "):
            cmd = text[len("выполни команду "):].strip()
            return self._run_shell(cmd, f"Выполняю: {cmd}")

        for phrase in self.get_all_phrases():
            if text.startswith(phrase):
                return self.execute(phrase, confirmed)

        return False, "Я не понял команду. Попробуйте ещё раз."

    def _run_builtin(self, phrase: str, spec: tuple, confirmed: bool) -> tuple[bool, str]:
        kind, value, speak_msg = spec

        if kind == "danger":
            if not confirmed:
                return None, phrase
            return self._run_shell(value, speak_msg)

        if kind == "app":
            try:
                subprocess.Popen(value, shell=True)
                return True, speak_msg
            except Exception as e:
                return False, f"Не удалось запустить: {e}"

        if kind == "steam":
            try:
                import webbrowser
                webbrowser.open(f"steam://rungameid/{value}")
                return True, speak_msg
            except Exception as e:
                return False, f"Не удалось запустить Steam: {e}"

        if kind == "hotkey":
            try:
                pyautogui.hotkey(*value)
                return True, speak_msg
            except Exception as e:
                return False, f"Ошибка: {e}"

        if kind == "url":
            try:
                import webbrowser
                webbrowser.open(value)
                return True, speak_msg
            except Exception as e:
                return False, f"Не удалось открыть: {e}"

        if kind == "volume":
            return self._change_volume(value, speak_msg)

        if kind == "datetime":
            return self._get_datetime(value)

        if kind == "reply":
            return True, speak_msg

        return False, "Неизвестная команда"

    def _run_user(self, phrase: str, action: str) -> tuple[bool, str]:
        for forbidden in FORBIDDEN_COMMANDS:
            if forbidden in action.lower():
                return False, "Команда запрещена по соображениям безопасности"

        if action.startswith("http://") or action.startswith("https://"):
            import webbrowser
            webbrowser.open(action)
            return True, f"Открываю {action}"
        elif action.startswith("cmd:"):
            return self._run_shell(action[4:].strip(), f"Выполняю: {action[4:]}")
        else:
            try:
                subprocess.Popen(action, shell=True)
                return True, f"Запускаю {action}"
            except Exception as e:
                return False, str(e)

    def _run_shell(self, cmd: str, speak_msg: str = None) -> tuple[bool, str]:
        for forbidden in FORBIDDEN_COMMANDS:
            if forbidden in cmd.lower():
                return False, "Команда запрещена по соображениям безопасности"
        try:
            subprocess.Popen(cmd, shell=True)
            return True, speak_msg or f"Выполнено: {cmd}"
        except Exception as e:
            return False, str(e)

    def _change_volume(self, direction: str, speak_msg: str) -> tuple[bool, str]:
        try:
            key = "volumeup" if direction == "+" else "volumedown"
            for _ in range(5):
                pyautogui.press(key)
            return True, speak_msg
        except Exception as e:
            return False, str(e)

    def _get_datetime(self, what: str) -> tuple[bool, str]:
        now = datetime.datetime.now()
        if what == "date":
            msg = now.strftime("Сегодня %d %B %Y года")
            months = {
                "January": "января", "February": "февраля", "March": "марта",
                "April": "апреля", "May": "мая", "June": "июня",
                "July": "июля", "August": "августа", "September": "сентября",
                "October": "октября", "November": "ноября", "December": "декабря",
            }
            for en, ru in months.items():
                msg = msg.replace(en, ru)
        else:
            msg = now.strftime("Сейчас %H часов %M минут")
        return True, msg


# ─────────────────────────────────────────────
#  Распознаватель речи
# ─────────────────────────────────────────────
class SpeechRecognizer:
    def __init__(self, on_result, on_status):
        self._on_result = on_result
        self._on_status = on_status
        self._q: queue.Queue = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._model = None
        self._load_model()

    def _load_model(self):
        if not VOSK_AVAILABLE:
            self._on_status("⚠ Vosk не установлен")
            return
        if not os.path.exists(MODEL_PATH):
            self._on_status(f"⚠ Модель не найдена: папка '{MODEL_PATH}'")
            return
        try:
            self._on_status("Загрузка модели Vosk...")
            self._model = Model(MODEL_PATH)
            self._on_status("Модель загружена. Готов к работе.")
        except Exception as e:
            self._on_status(f"Ошибка загрузки модели: {e}")

    def start(self):
        if self._running:
            return
        if self._model is None:
            self._on_status("Модель не загружена. Проверьте папку 'model'.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        self._on_status("🎤 Слушаю...")

    def stop(self):
        self._running = False
        self._on_status("⏹ Остановлено")

    def _audio_callback(self, indata, frames, time_info, status):
        if self._running:
            self._q.put(bytes(indata))

    def _listen_loop(self):
        rec = KaldiRecognizer(self._model, SAMPLE_RATE)
        try:
            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                while self._running:
                    try:
                        data = self._q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = result.get("text", "").strip()
                        if text:
                            self._on_result(text)
        except Exception as e:
            self._on_status(f"Ошибка микрофона: {e}")
            self._running = False


# ─────────────────────────────────────────────
#  Главное окно
# ─────────────────────────────────────────────
class VoiceAssistantApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Голосовой Помощник - Silero TTS Neural Voice")
        self.resizable(False, False)
        self._build_ui()

        self._cmd_manager = CommandManager(self._on_command_done)
        self._recognizer = SpeechRecognizer(
            on_result=self._on_speech_result,
            on_status=self._set_status,
        )

        self._pending_dangerous: str | None = None
        self._waiting_confirm = False

    def _build_ui(self):
        BG = "#1e1e2e"
        FG = "#cdd6f4"
        ACCENT = "#89b4fa"
        BTN_START = "#a6e3a1"
        BTN_STOP = "#f38ba8"
        LOG_BG = "#181825"

        self.configure(bg=BG)

        tk.Label(
            self, text="🎙 ГОЛОСОВОЙ ПОМОЩНИК",
            font=("Segoe UI", 16, "bold"),
            bg=BG, fg=ACCENT,
        ).pack(pady=(18, 4))

        tk.Label(
            self, text="Voice Assistant Lite • Vosk offline • Silero TTS Neural Voice",
            font=("Segoe UI", 9),
            bg=BG, fg="#6c7086",
        ).pack()

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(pady=14)

        self._btn_start = tk.Button(
            btn_frame, text="▶  СЛУШАТЬ",
            font=("Segoe UI", 11, "bold"),
            bg=BTN_START, fg="#1e1e2e",
            activebackground="#94e2a1",
            relief="flat", padx=18, pady=8,
            command=self._start_listening,
        )
        self._btn_start.grid(row=0, column=0, padx=6)

        self._btn_stop = tk.Button(
            btn_frame, text="■  СТОП",
            font=("Segoe UI", 11, "bold"),
            bg=BTN_STOP, fg="#1e1e2e",
            activebackground="#f5a0b5",
            relief="flat", padx=18, pady=8,
            state="disabled",
            command=self._stop_listening,
        )
        self._btn_stop.grid(row=0, column=1, padx=6)

        self._voice_enabled = True
        self._btn_voice = tk.Button(
            btn_frame, text="🔊 Голос: ВКЛ",
            font=("Segoe UI", 10, "bold"),
            bg="#89b4fa", fg="#1e1e2e",
            activebackground="#a8c8fa",
            relief="flat", padx=12, pady=8,
            command=self._toggle_voice,
        )
        self._btn_voice.grid(row=0, column=2, padx=6)

        self._btn_add = tk.Button(
            btn_frame, text="➕ Команда",
            font=("Segoe UI", 10),
            bg="#cba6f7", fg="#1e1e2e",
            activebackground="#d5b8f8",
            relief="flat", padx=10, pady=8,
            command=self._add_command_dialog,
        )
        self._btn_add.grid(row=0, column=3, padx=6)

        self._btn_help = tk.Button(
            btn_frame, text="❓ Команды",
            font=("Segoe UI", 10),
            bg="#fab387", fg="#1e1e2e",
            activebackground="#fbc5a3",
            relief="flat", padx=10, pady=8,
            command=self._show_commands,
        )
        self._btn_help.grid(row=0, column=4, padx=6)

        status_frame = tk.Frame(self, bg=BG)
        status_frame.pack(fill="x", padx=20)

        tk.Label(status_frame, text="Статус:", font=("Segoe UI", 10),
                 bg=BG, fg="#6c7086").pack(side="left")
        self._status_var = tk.StringVar(value="Инициализация...")
        tk.Label(status_frame, textvariable=self._status_var,
                 font=("Segoe UI", 10, "bold"),
                 bg=BG, fg=FG).pack(side="left", padx=6)

        last_frame = tk.Frame(self, bg=BG)
        last_frame.pack(fill="x", padx=20, pady=(6, 0))
        tk.Label(last_frame, text="Распознано:", font=("Segoe UI", 10),
                 bg=BG, fg="#6c7086").pack(side="left")
        self._last_var = tk.StringVar(value="—")
        tk.Label(last_frame, textvariable=self._last_var,
                 font=("Segoe UI", 10, "italic"),
                 bg=BG, fg=ACCENT).pack(side="left", padx=6)

        log_outer = tk.Frame(self, bg=BG)
        log_outer.pack(fill="both", expand=True, padx=20, pady=14)

        tk.Label(log_outer, text="ЖУРНАЛ КОМАНД",
                 font=("Segoe UI", 9, "bold"),
                 bg=BG, fg="#6c7086").pack(anchor="w")

        log_frame = tk.Frame(log_outer, bg=LOG_BG, bd=1, relief="solid")
        log_frame.pack(fill="both", expand=True)

        self._log_text = tk.Text(
            log_frame,
            font=("Consolas", 10),
            bg=LOG_BG, fg=FG,
            insertbackground=FG,
            relief="flat",
            state="disabled",
            width=62, height=12,
            padx=8, pady=6,
        )
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)

        self._log_text.tag_config("ok",  foreground="#a6e3a1")
        self._log_text.tag_config("err", foreground="#f38ba8")
        self._log_text.tag_config("info", foreground="#89dceb")

        tk.Label(
            self,
            text="Модель: Vosk + Silero TTS (нейросетевой голос) • Офлайн",
            font=("Segoe UI", 8),
            bg=BG, fg="#45475a",
        ).pack(pady=(0, 10))

        self.geometry("680x540")
        self._set_status("Готов. Нажмите 'Слушать'")

    def _toggle_voice(self):
        self._voice_enabled = not self._voice_enabled
        if self._voice_enabled:
            self._btn_voice.config(text="🔊 Голос: ВКЛ", bg="#89b4fa")
            speaker.say("Голос включён")
        else:
            self._btn_voice.config(text="🔇 Голос: ВЫКЛ", bg="#6c7086")

    def _show_commands(self):
        help_win = tk.Toplevel(self)
        help_win.title("Список команд")
        help_win.configure(bg="#1e1e2e")
        help_win.resizable(False, False)

        tk.Label(
            help_win, text="ГОЛОСОВЫЕ КОМАНДЫ",
            font=("Segoe UI", 14, "bold"),
            bg="#1e1e2e", fg="#89b4fa"
        ).pack(pady=(12, 8))

        commands_text = """
🎨 СИСТЕМА
   • открой калькулятор
   • открой блокнот
   • закрой окно
   • выключи компьютер

🌐 ИНТЕРНЕТ
   • открой почту
   • что нового
   • включи ютуб
   • включи саундклауд

🎮 ИГРЫ
   • включи кс
   • включи дискорд

🔊 УПРАВЛЕНИЕ
   • увеличь громкость
   • уменьши громкость
   • заблокировать экран

📅 ДАТА И ВРЕМЯ
   • какое сегодня число
   • сколько времени

💬 РАЗГОВОР
   • привет
   • как дела
   • спасибо
   • пока
"""
        text_widget = tk.Text(
            help_win,
            font=("Consolas", 10),
            bg="#181825", fg="#cdd6f4",
            relief="flat",
            width=42, height=26,
            padx=12, pady=8,
        )
        text_widget.pack(padx=12, pady=(0, 12))
        text_widget.insert("1.0", commands_text)
        text_widget.config(state="disabled")

        tk.Button(
            help_win, text="Закрыть",
            font=("Segoe UI", 10),
            bg="#45475a", fg="#cdd6f4",
            relief="flat", padx=20, pady=6,
            command=help_win.destroy
        ).pack(pady=(0, 12))

    def _start_listening(self):
        self._btn_start.config(state="disabled")
        self._btn_stop.config(state="normal")
        self._recognizer.start()

    def _stop_listening(self):
        self._btn_start.config(state="normal")
        self._btn_stop.config(state="disabled")
        self._recognizer.stop()

    def _on_speech_result(self, text: str):
        self.after(0, self._process_text, text)

    def _process_text(self, text: str):
        self._last_var.set(f'"{text}"')
        ts = datetime.datetime.now().strftime("%H:%M:%S")

        if self._waiting_confirm:
            self._handle_confirmation(text, ts)
            return

        success, message = self._cmd_manager.execute(text)

        if success is None:
            self._pending_dangerous = message
            self._waiting_confirm = True
            confirm_msg = "Вы уверены? Скажите «да» или «нет»"
            self._set_status(f"⚠ {confirm_msg}")
            self._log_entry(ts, text, f"⚠ {confirm_msg}", "info")
            if self._voice_enabled:
                speaker.say(confirm_msg)
        else:
            self._on_command_done(ts, text, success, message)

    def _handle_confirmation(self, text: str, ts: str):
        text_l = text.lower().strip()
        if any(w in text_l for w in ["да", "yes", "подтверждаю", "конечно"]):
            self._waiting_confirm = False
            phrase = self._pending_dangerous
            self._pending_dangerous = None
            success, message = self._cmd_manager.execute(phrase, confirmed=True)
            self._on_command_done(ts, phrase, success, message)
        elif any(w in text_l for w in ["нет", "no", "отмена", "отменить", "стоп"]):
            self._waiting_confirm = False
            self._pending_dangerous = None
            self._set_status("🎤 Слушаю...")
            self._log_entry(ts, text, "❌ Отменено пользователем", "err")
            if self._voice_enabled:
                speaker.say("Отменено")
        else:
            if self._voice_enabled:
                speaker.say("Скажите да или нет")

    def _on_command_done(self, ts: str, text: str, success: bool, message: str):
        if success:
            icon = "✅"
            tag = "ok"
            if self._voice_enabled:
                speaker.say(message)
        else:
            icon = "❌"
            tag = "err"
            if self._voice_enabled:
                speaker.say("Я не понял команду. Попробуйте ещё раз.")

        self._log_entry(ts, text, f"{icon} {message}", tag)
        self._set_status("🎤 Слушаю..." if self._recognizer._running else "⏹ Остановлено")

    def _log_entry(self, ts: str, command: str, result: str, tag: str = "ok"):
        self._log_text.config(state="normal")
        line = f"{ts}  →  \"{command}\"\n         {result}\n"
        self._log_text.insert("end", line, tag)
        self._log_text.see("end")
        self._log_text.config(state="disabled")

    def _set_status(self, text: str):
        self.after(0, self._status_var.set, text)

    def _add_command_dialog(self):
        dialog = AddCommandDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            phrase, action = dialog.result
            self._cmd_manager.add_user_command(phrase, action)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._log_entry(ts, f"Добавлена команда: «{phrase}»",
                            f"✅ Действие: {action}", "ok")
            messagebox.showinfo(
                "Команда добавлена",
                f"Фраза: «{phrase}»\nДействие: {action}\n\nКоманда сохранена в commands.json",
            )


class AddCommandDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Добавить команду")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        BG = "#1e1e2e"
        FG = "#cdd6f4"
        ACCENT = "#89b4fa"

        self.configure(bg=BG)

        tk.Label(self, text="Новая голосовая команда",
                 font=("Segoe UI", 13, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(16, 4), padx=20)

        tk.Label(self, text="Фраза (что говорить):",
                 font=("Segoe UI", 10), bg=BG, fg=FG).pack(anchor="w", padx=20)
        self._phrase_var = tk.StringVar()
        tk.Entry(self, textvariable=self._phrase_var,
                 font=("Segoe UI", 11),
                 bg="#313244", fg=FG, insertbackground=FG,
                 relief="flat", width=36).pack(padx=20, pady=(2, 10), ipady=4)

        tk.Label(self, text="Действие:",
                 font=("Segoe UI", 10), bg=BG, fg=FG).pack(anchor="w", padx=20)
        self._action_var = tk.StringVar()
        tk.Entry(self, textvariable=self._action_var,
                 font=("Segoe UI", 11),
                 bg="#313244", fg=FG, insertbackground=FG,
                 relief="flat", width=36).pack(padx=20, pady=(2, 4), ipady=4)

        tk.Label(
            self,
            text="Примеры:\n  notepad.exe\n  https://youtube.com\n  cmd:ipconfig",
            font=("Consolas", 9), bg=BG, fg="#6c7086",
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 10))

        btn_f = tk.Frame(self, bg=BG)
        btn_f.pack(pady=(0, 16))
        tk.Button(btn_f, text="Сохранить",
                  font=("Segoe UI", 10, "bold"),
                  bg="#a6e3a1", fg="#1e1e2e",
                  relief="flat", padx=14, pady=6,
                  command=self._save).grid(row=0, column=0, padx=8)
        tk.Button(btn_f, text="Отмена",
                  font=("Segoe UI", 10),
                  bg="#f38ba8", fg="#1e1e2e",
                  relief="flat", padx=14, pady=6,
                  command=self.destroy).grid(row=0, column=1, padx=8)

        self.geometry("380x340")

    def _save(self):
        phrase = self._phrase_var.get().strip()
        action = self._action_var.get().strip()
        if not phrase or not action:
            messagebox.showwarning("Ошибка", "Заполните оба поля.", parent=self)
            return
        self.result = (phrase, action)
        self.destroy()


def main():
    app = VoiceAssistantApp()
    app.mainloop()


if __name__ == "__main__":
    main()
