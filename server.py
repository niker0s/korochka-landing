# -*- coding: utf-8 -*-
"""Сервер лендинга «Корочка».

Делает две вещи:
  1. отдаёт файлы сайта (index.html, styles.css, script.js, assets/);
  2. принимает заявки с формы на POST /api/order и пересылает их в Telegram.

Только стандартная библиотека Python, ничего ставить не нужно.

Запуск:
    python server.py              # http://127.0.0.1:8000
    python server.py --port 9000

Настройки берутся из переменных окружения или из файла .env рядом:
    TELEGRAM_BOT_TOKEN=123456789:AA...
    TELEGRAM_CHAT_ID=000000000

Если токена нет — заявки не теряются, а пишутся в orders.jsonl.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
ORDERS_PATH = BASE_DIR / "orders.jsonl"

MAX_BODY = 8 * 1024          # больше 8 КБ от формы не ждём
RATE_LIMIT = 10              # не больше 10 заявок
RATE_WINDOW = 10 * 60        # за 10 минут с одного адреса

# Файлы, которые наружу отдавать нельзя
BLOCKED_SUFFIXES = (".py", ".env", ".jsonl", ".bat", ".ps1", ".md")

HITS: dict[str, list[float]] = {}


def load_env() -> dict[str, str]:
    """Переменные окружения + .env рядом со скриптом (.env главнее)."""
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "PORT"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def validate(data: dict) -> dict[str, str]:
    """Те же правила, что в script.js. Возвращает словарь ошибок."""
    errors: dict[str, str] = {}

    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    address = str(data.get("address", "")).strip()
    pie = str(data.get("pie", "")).strip()
    note = str(data.get("note", "")).strip()

    if len(name) < 2:
        errors["name"] = "Напишите имя, чтобы знать, как к вам обращаться"
    elif len(name) > 80:
        errors["name"] = "Слишком длинное имя"

    if not 10 <= len(digits(phone)) <= 15:
        errors["phone"] = "Нужен телефон из 10–11 цифр"

    if len(address) < 5:
        errors["address"] = "Укажите улицу, дом и квартиру"
    elif len(address) > 200:
        errors["address"] = "Слишком длинный адрес"

    if len(pie) > 80 or len(note) > 500:
        errors["note"] = "Слишком длинный текст"

    if data.get("consent") is not True:
        errors["consent"] = "Без согласия на обработку данных заявку принять нельзя"

    return errors


def too_many_requests(ip: str) -> bool:
    now = time.time()
    history = [t for t in HITS.get(ip, []) if now - t < RATE_WINDOW]
    if len(history) >= RATE_LIMIT:
        HITS[ip] = history
        return True
    history.append(now)
    HITS[ip] = history
    return False


def save_order(order: dict) -> None:
    """Резервное хранилище: одна заявка — одна строка JSON."""
    with ORDERS_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(order, ensure_ascii=False) + "\n")


def send_to_telegram(order: dict, token: str, chat_id: str) -> None:
    text = (
        "Новая заявка с сайта\n\n"
        f"Имя: {order['name']}\n"
        f"Телефон: {order['phone']}\n"
        f"Пирог: {order['pie'] or 'не выбран'}\n"
        f"Адрес: {order['address']}\n"
        f"Пожелания: {order['note'] or '—'}\n"
        f"Время: {order['created_at']}"
    )
    body = parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    req = request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with request.urlopen(req, timeout=15) as response:
        response.read()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    # --- отдача файлов ---
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self.send_json(200, {"ok": True, "telegram": bool(TELEGRAM_TOKEN)})
            return
        if self.is_blocked(path):
            self.send_error(404)
            return
        super().do_GET()

    # --- приём заявки ---
    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/order":
            self.send_error(404)
            return

        ip = self.client_address[0]
        if too_many_requests(ip):
            self.send_json(429, {"ok": False, "error": "Слишком много заявок. Позвоните нам."})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self.send_json(400, {"ok": False, "error": "Пустая или слишком большая заявка"})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"ok": False, "error": "Не удалось прочитать заявку"})
            return

        if not isinstance(payload, dict):
            self.send_json(400, {"ok": False, "error": "Неверный формат заявки"})
            return

        errors = validate(payload)
        if errors:
            self.send_json(422, {"ok": False, "errors": errors})
            return

        order = {
            "name": str(payload.get("name", "")).strip(),
            "phone": str(payload.get("phone", "")).strip(),
            "pie": str(payload.get("pie", "")).strip(),
            "address": str(payload.get("address", "")).strip(),
            "note": str(payload.get("note", "")).strip(),
            "created_at": time.strftime("%d.%m.%Y %H:%M"),
            "ip": ip,
        }

        save_order(order)

        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            try:
                send_to_telegram(order, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
                print(f"[{time.strftime('%H:%M:%S')}] заявка отправлена в Telegram: {order['phone']}")
            except (error.URLError, error.HTTPError, TimeoutError) as exc:
                # Заявка уже в файле, поэтому клиента не пугаем.
                print(f"[{time.strftime('%H:%M:%S')}] Telegram не ответил: {exc}. Заявка в orders.jsonl")
        else:
            print(f"[{time.strftime('%H:%M:%S')}] токена нет, заявка в orders.jsonl: {order['phone']}")

        self.send_json(200, {"ok": True})

    # --- служебное ---
    def is_blocked(self, path: str) -> bool:
        lowered = path.lower()
        return any(lowered.endswith(suffix) for suffix in BLOCKED_SUFFIXES) or "/." in lowered

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        """Страницу, стили и скрипт браузер каждый раз перепроверяет.

        Иначе после правки текста или цены клиент видит старую версию
        и думает, что изменения не сохранились.
        """
        path = self.path.split("?", 1)[0].lower()
        if path in ("/", "/index.html") or path.endswith((".css", ".js")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {fmt % args}")


def main() -> None:
    global TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

    env = load_env()
    TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")

    port = int(env.get("PORT", "8000"))
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    print(f"Сайт: http://127.0.0.1:{port}/")
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        print("Заявки уходят в Telegram.")
    else:
        print("Telegram не настроен: заявки пишутся в orders.jsonl.")
    print("Остановить: Ctrl+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен")
    finally:
        server.server_close()


TELEGRAM_TOKEN = ""
TELEGRAM_CHAT_ID = ""

if __name__ == "__main__":
    main()
