# mcp-vn — визуальная новелла в ChatGPT

Личный игровой сервер с MCP Apps-интерфейсом: сцена со спрайтами, прокручиваемая история сообщений, **свободные действия игрока**, необязательные подсказки, сохранения и автоматическая генерация иллюстраций/коротких видео на RX 9070 XT.

## Архитектура

- **Домашний Ubuntu-сервер**: Docker `mcp-vn`, игровой движок, сохранения, очередь и библиотека медиа.
- **Игровой ПК Bazzite**: ComfyUI (ROCm gfx1201) и `mcp-vn-worker.service`. Воркер самостоятельно забирает задания, входящие порты на ПК не нужны.
- **VPS**: авторизованный шлюз с проверкой Auth0 JWT по адресу `https://xavoks.jo3.org/vn/mcp`. Media URLs защищены HMAC.
- **ChatGPT**: ведущий игры; MCP Apps даёт игровой интерфейс в чате.

## Поддерживаемые изображения и видео

- `anime` — Animagine XL 4.0.
- `semireal` — DreamShaper XL Turbo v2.1.
- `realistic` — RealVisXL V5.0.
- `poster` — Juggernaut XL v9.
- `video` — Wan 2.2 TI2V 5B (первые тесты: короткие ролики 512×288).

В интерфейсе один личный режим для вымышленных совершеннолетних персонажей, без пользовательских переключателей рейтинга или предупреждений. Ответы ChatGPT подчиняются его собственным правилам.

## Развёртывание

```bash
git clone https://github.com/Riannoni/mcp-vn.git /opt/mcp-vn
cd /opt/mcp-vn
# Заполнить приватную .env: VN_PUBLIC_ORIGIN, VN_WORKER_TOKEN,
# VN_MCP_TOKEN и VN_ASSET_SECRET. Не размещать её в GitHub!
docker compose build
docker compose up -d
```

На ПК используются `deploy/comfyui.container`, `deploy/Containerfile.gfx1201`, `deploy/pc-worker.service` и `worker/worker.py`. Секрет подключения воркера хранится только в `~/.config/mcp-vn/worker.env`.

## Как играть

Открыть приватный плагин **mcp-vn Visual Novel** в ChatGPT, авторизовать его через уже настроенный Auth0 и написать: «Открой mcp-vn и продолжи игру». Игровое окно вызывается инструментом `open_game`.

Сам URL `/vn/mcp` в обычном браузере возвращает 401 — это ожидаемая защита. Обязательно проверить фактическую поддержку `App.sendMessage` после подключения приложения к своему аккаунту ChatGPT.

## Импорт

`import_story` принимает JSON-пакеты собственных или разрешённых для переноса историй. Текущий ISEKAI ZERO MCP позволяет читать свои персонажи и сюжеты, но не скрытые промпты чужих историй из всего каталога. Генерация через ISEKAI ZERO не используется и не расходует Mana.

## Инструменты

`open_game`, `list_stories`, `list_games`, `start_game`, `get_game`, `get_game_context`, `submit_action`, `gm_continue`, `undo_last_turn`, `queue_art`, `list_art_jobs`, `import_story`.

Игры хранятся в `data/games`, сюжеты в `data/stories`, задания в `data/jobs`, изображения и видео в `data/assets`. `npm test` проверяет основной игровой цикл.
