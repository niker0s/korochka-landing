# Как выложить сайт в интернет

Коротко: сайту нужен **Python-сервер**, потому что форма отправляет заявки через
`server.py`. Обычный статический хостинг (GitHub Pages, Netlify, Tilda) форму
обслужить не сможет — там Python не запускается.

Три рабочих варианта. Первый — для показа демо, второй и третий — для клиента.

---

## Вариант A. Render.com — бесплатно, демо уже опубликовано

**Живой адрес: https://korochka-landing.onrender.com**
Репозиторий: `github.com/niker0s/korochka-landing` (папка `zakaz-01-pirogi`
без `.env` и `orders.jsonl`).

Сервер на бесплатном тарифе засыпает через 15 минут без посетителей: первый
заход после паузы грузится около минуты, дальше быстро.

Что настроено в Render:

- Name: `korochka-landing` (из него получается адрес сайта);
- Language: Python 3, Branch: `main`, Region: Frankfurt (ближе к Москве);
- **Build Command: `echo "no dependencies"`** — у сайта нет зависимостей,
  а стандартная команда `pip install -r requirements.txt` падает, потому что
  файла требований нет;
- Start Command: `python server.py`;
- Compute: Free.

Порт Render передаёт сам в переменной `PORT`, `server.py` её читает.

Переменные окружения (вкладка **Environment** → Add variable), значения — из
своего `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Проверка после деплоя: открыть `https://korochka-landing.onrender.com/api/health`
— должно быть `{"ok": true, "telegram": true}`. Потом отправить заявку с формы.

### Как обновить опубликованный сайт

Правки делаются в `zakaz-01-pirogi`, а в GitHub лежит их копия. Рабочая копия
репозитория — папка `deploy/korochka-landing` в корне сессии (в git не попадает).
После правок:

```powershell
$src = "D:\MyProjects\New sessions\session-2026-10-30\zakaz-01-pirogi"
$dst = "D:\MyProjects\New sessions\session-2026-10-30\deploy\korochka-landing"
Copy-Item "$src\*" -Destination $dst -Recurse -Force
cd $dst
git add -A
git commit -m "что поменяли"
git push
```

Render сам увидит новый коммит в `main` и пересоберёт сайт (1–2 минуты).
`.env` и `orders.jsonl` в копию не попадут: они в `.gitignore`.

Если папки `deploy` нет (например, почистили):

```powershell
cd "D:\MyProjects\New sessions\session-2026-10-30\deploy"
git clone https://github.com/niker0s/korochka-landing.git
```

---

## Вариант B. VPS или хостинг клиента — для боевого сайта

Нужно: сервер с Python 3.10+ (Timeweb, Beget, любой за 200–500 ₽/мес), домен
клиента.

1. Скопировать папку `zakaz-01-pirogi` на сервер (SFTP или `scp`).
2. На сервере создать `.env` с токеном и chat_id.
3. Проверить запуск вручную:

   ```bash
   cd /var/www/korochka
   python3 server.py --port 8000
   ```

4. Автозапуск через systemd — файл `/etc/systemd/system/korochka.service`:

   ```ini
   [Unit]
   Description=Korochka landing
   After=network.target

   [Service]
   WorkingDirectory=/var/www/korochka
   ExecStart=/usr/bin/python3 server.py --port 8000
   Restart=always
   User=www-data

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl enable --now korochka
   ```

5. Домен и HTTPS. Проще всего поставить nginx как «приёмную» и получить
   бесплатный сертификат:

   ```bash
   sudo apt install nginx certbot python3-certbot-nginx
   ```

   Конфиг nginx: слушать 80/443 и передавать запросы на `127.0.0.1:8000`.
   Затем `sudo certbot --nginx -d домен.ру` — сертификат обновится сам.

6. В DNS домена — A-запись на IP сервера (делает клиент или тот, у кого домен).

Что важно на боевом сервере:

- порт 8000 наружу не открывать, только через nginx;
- `.env` с правами `600`, владелец — пользователь сервиса;
- `orders.jsonl` периодически выгружать: сейчас это единственное хранилище
  заявок на сервере.

---

## Вариант C. Статика + serverless

Если клиент уже платит за Netlify/Vercel и не хочет сервер: сайт остаётся
статичным, а форма отправляет запрос в функцию.

1. `index.html`, `styles.css`, `script.js`, `assets/` — на Netlify.
2. В `script.js` заменить `fetch('api/order', …)` на `fetch('/.netlify/functions/order', …)`.
3. Добавить `netlify/functions/order.js` — функция принимает JSON, проверяет
   поля и вызывает `https://api.telegram.org/bot<TOKEN>/sendMessage`.
4. Токен и chat_id — в настройках сайта: **Site settings → Environment
   variables**, в код не писать.

Плюс: бесплатно и быстро. Минус: логика проверки полей дублируется на JS —
`server.py` в этом варианте не используется.

---

## Что отдать клиенту после публикации

- ссылку на сайт и доступы к хостингу (не к домену, если домен его);
- файл `Инструкция-клиенту.md` — как менять тексты, цены и фото;
- договорённость про поддержку: правки текста — по часам, обновление цен —
  можно показать один раз, дальше сам.

## Чек-лист перед сдачей

- [ ] заменить временные фото на снимки клиента (лицензии — `CREDITS.md`);
- [ ] вписать настоящие телефон, адрес, почту, часы работы;
- [ ] проверить форму на боевом адресе: заявка доходит в Telegram;
- [ ] проверить `/api/health` и что `/.env`, `/server.py` отдают 404;
- [ ] открыть сайт на телефоне клиента (не только на своём);
- [ ] добавить сайт в Яндекс.Вебмастер и Google Search Console;
- [ ] если сайт переезжает на другой домен — поменять адрес в `og:url`,
      `og:image` (`index.html`) и в поле `image` разметки `schema.org`;
- [ ] в `privacy.html` вписать настоящие реквизиты и срок хранения, убрать
      абзац «Демонстрационный сайт»;
- [ ] проверить разметку `schema.org` на https://validator.schema.org/.
