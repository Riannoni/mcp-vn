# Установка и обновление VN Web 0.7.0

## Перед началом

Это не однокомандный installer. Исходная установка рассчитана на домашний Ubuntu-сервер с Docker Compose и отдельный игровой ПК на Bazzite/Fedora с AMD ROCm, ComfyUI и systemd user services. Потребуются локальная сеть, запущенные графические модели и доступ к выбранному рассказчику через локальную модель или OAuth провайдера. MCP/VPS-шлюз для работы VN Web не нужен.

**В репозитории нет весов AI, сохранений, ключей и токенов.** Пользователь самостоятельно получает совместимые модели с учётом их лицензий и авторизации. См. [MODELS.md](MODELS.md).

### Топология и порты

| Сервис | Пример | Доступ |
| --- | --- | --- |
| Node game | домашний сервер:3100 | разрешён только доверенным хостам LAN/VPN |
| ComfyUI | ПК `127.0.0.1:8188` | только ПК |
| Vision QA | ПК `127.0.0.1:9312` | только ПК |
| KoboldCpp gateway | ПК:11434 | только домашний game server + bearer token |
| VN Web | `http://YOUR_PC:8190/vn/` | Домашняя сеть, пароль приложения |

В `compose.yaml` и `deploy/*.service` сохранены IP-адреса и пути **исходного личного развёртывания**. Для новой установки замените адреса и пользовательский каталог PC (`/home/Xavok`), иначе сервисы будут пытаться обращаться к чужой машине.

## 1. Домашний сервер

```bash
git clone https://github.com/Riannoni/mcp-vn.git /opt/mcp-vn
cd /opt/mcp-vn
cp .env.example .env
chmod 600 .env
```

Создайте **три независимых секрета**, не используйте текст из шаблона:

```bash
openssl rand -hex 32    # VN_WORKER_TOKEN
openssl rand -hex 32    # VN_ASSET_SECRET
```

Заполните приватную `.env`:

- `VN_PUBLIC_ORIGIN` — публичный HTTPS origin с префиксом `/vn`, если он используется.
- `VN_WORKER_TOKEN` — идентичный ключ для Node game и GPU-воркера/локального LLM gateway.
- `VN_ASSET_SECRET` — секрет HMAC ссылок на изображения.

Проверьте `compose.yaml`: текущие привязки портов и адрес `VN_LOCAL_MODEL_URL` относятся к исходной LAN. При новой установке исправьте **до запуска**.

```bash
docker compose config --quiet
docker compose build game
docker compose up -d --no-deps game
docker compose ps
curl -fsS http://YOUR_HOME_LAN_IP:3100/healthz
```

Контейнер использует read-only filesystem, `/tmp` как tmpfs, `/data` для состояния игры и ограничение памяти 1 GiB. Убедитесь, что папка `data/` доступна пользователю контейнера (`node`) на запись; не публикуйте её в веб-сервере напрямую.

## 2. ПК: ComfyUI на Radeon

В репозитории есть образ-пример `deploy/Containerfile.gfx1201` для RDNA4, Quadlet `deploy/comfyui.container` и `deploy/extra_model_paths.yaml`. **Перед копированием замените все абсолютные пути** на реальный домашний каталог ПК.

На ПК подготовьте:

```bash
mkdir -p ~/.local/share/mcp-vn-comfy/{models,input,output,temp,user,custom_nodes}
mkdir -p ~/.config/containers/systemd
```

Для RX 9070 XT требуется корректно работающая версия ROCm/драйвера. Проверить устройства `/dev/kfd` и `/dev/dri`, наличие Radeon в системе. Собрать ComfyUI-образ по примерному Containerfile, настроить Quadlet под локальный каталог и установить совместимые custom nodes, необходимые используемому pipeline (ComfyUI IPAdapter Plus, ControlNet/OpenPose, ComfyUI-GGUF для экспериментальной Z-Image, инструменты video для Wan).

В модельном каталоге ComfyUI (`/data/models` внутри контейнера) создайте `checkpoints/`, `diffusion_models/`, `text_encoders/`, `vae/`, `loras/` и необходимые папки для ControlNet/IPAdapter. Положите модели согласно [MODELS.md](MODELS.md) и проверьте их контрольные суммы у поставщика.

```bash
# На ПК после настройки/копирования Quadlet:
systemctl --user daemon-reload
systemctl --user enable --now mcp-vn-comfy.service
systemctl --user status mcp-vn-comfy.service
curl -fsS http://127.0.0.1:8188/system_stats
```

**Не** копируйте ключи в `deploy/` или в Docker image. ComfyUI должен быть доступен на `127.0.0.1`, не на публичном интерфейсе.

## 3. ПК: игровой воркер и QA

В пользовательском каталоге разместите:

- `worker/worker.py`, `worker/pose_presets.py`, `worker/scene_compositor.py`, `worker/scene_qa_rules.py`, `worker/visual_contract.py`;
- `worker/vision_daemon.py` и `worker/vision_qa.py`;
- Python virtualenv с Pillow, image processing / QA-зависимостями, установленными для данной ОС.

Для первичной установки можно копировать исходники по SFTP/rsync в `~/.local/share/mcp-vn/`. В исходной установке сервис `deploy/pc-worker.service` использует `/usr/bin/python3`, а Python-зависимости приложения развернуты для этого окружения. Если вы выбираете отдельный venv, измените `ExecStart` на соответствующий Python и убедитесь в доступности библиотек.

```bash
mkdir -p ~/.config/mcp-vn ~/.config/systemd/user
cp deploy/worker.env.example ~/.config/mcp-vn/worker.env
chmod 600 ~/.config/mcp-vn/worker.env
# Отредактируйте адрес сервера и ТОТ ЖЕ секрет, что VN_WORKER_TOKEN на home.
# Установите pc-worker.service в ~/.config/systemd/user/mcp-vn-worker.service
systemctl --user daemon-reload
systemctl --user enable --now mcp-vn-worker.service
journalctl --user -u mcp-vn-worker.service -n 80 --no-pager
```

Опциональная CPU Vision QA из `worker/vision_daemon.py` работает отдельно. На конкретном ПК она запускается как `mcp-vn-vision.service` на localhost:9312. Её модельные файлы и зависимости тоже не входят в репозиторий.

## 4. ПК: KoboldCpp / ROCm

Два GGUF должны лежать в `~/.local/share/mcp-vn-kobold/models/`. В репозитории есть:

- `deploy/kobold-gateway.py` — защищённый сервер для локального текста;
- `deploy/mcp-vn-kobold-gateway.service` — пример systemd user service;
- `deploy/mcp-vn-kobold-rocm.conf` — drop-in с предпочтительным ROCm;
- `deploy/download-koboldcpp-rocm.sh` — загрузчик конкретной проверенной сборки ROCm.

Установите KoboldCpp CPU executable как запасной вариант, а ROCm build — отдельно, не перезаписывая CPU binary. Проверьте контрольную сумму и модели согласно [LOCAL-LLM-ROCM.md](LOCAL-LLM-ROCM.md).

```bash
systemctl --user daemon-reload
systemctl --user enable --now mcp-vn-kobold-gateway.service
systemctl --user status mcp-vn-kobold-gateway.service
```

Исходное развёртывание: **Cydonia** (`cydonia:24b-v4.3-iq4_xs`) — основной рассказчик локального эпизода; **Qwen** (`qwen3.5:9b-q4_K_M`) — визуальный режиссёр и текстовый fallback. Эти имена задаются в `compose.yaml`, а не передаются с фронтенда без авторизации.

## 5. VN Web и подключение моделей

Игровой сервер в Docker предоставляет только защищённые HTTP API для VN Web и локального GPU-воркера. Публичный `/mcp` отключён. Не публикуйте Worker API, ComfyUI, KoboldCpp или каталог `data` в Интернет.

В браузере откройте VN Web на ПК и выберите локальный рассказчик либо авторизуйте Grok/ChatGPT через раздел «Подключения». Для этого работает локальный универсальный прокси, а не прежний MCP gateway.

## 6. Проверка установки

```bash
cd /opt/mcp-vn
docker compose build game   # Vite + Node tests
curl -fsS http://YOUR_HOME_LAN_IP:3100/healthz
docker compose logs --tail=100 game
```

На ПК:

```bash
curl -fsS http://127.0.0.1:8188/queue
systemctl --user is-active mcp-vn-worker.service mcp-vn-comfy.service
systemctl --user is-active mcp-vn-kobold-gateway.service
```

Сначала проверьте нейтральный рендер, затем загрузку UI через `open_game_v64`. Сравните результат на ПК и загрузку ассета в UI. Подробные коды ошибок и сценарии отката описаны в [OPERATIONS.md](OPERATIONS.md).

## Обновления

```bash
cd /opt/mcp-vn
# Сначала сделайте резервную копию data/ и .env вне Git
git fetch origin
git status
git pull --ff-only origin main
docker compose build game
docker compose up -d --no-deps game
curl -fsS http://YOUR_HOME_LAN_IP:3100/healthz
```

На ПК обновите `worker.py`, модельные/QA компоненты и пользовательские сервисы **только если изменились соответствующие файлы**. Зависимости image/LLM обновляйте отдельно с тестом neutral render. Старые веса не удаляйте до проверки новых.

Сохранения `data/` ни при обновлении, ни при откате кода не следует перезаписывать старой копией без явного решения игрока.

## Самостоятельный VN Web / Model Lab

На игровом ПК нужны Python 3.9+, доступ к домашнему worker API и настроенный CLIProxyAPI. Node/npm для запуска самого веб-интерфейса не нужны. Исходники находятся в `standalone-web/`; общие сохранения остаются на домашнем сервере.

1. Скопируй содержимое `standalone-web/` в `~/.local/share/mcp-vn-model-lab/` на ПК. Не заменяй каталог целиком: он также содержит результаты Model Lab и локальные данные.
2. Для другой сети измени `HOST`, `LAN` в `server.py`, `HOME` в `vn_web.py` и адрес шлюза `ROUTER`. Текущие значения описаны в [VN-WEB.md](VN-WEB.md).
3. Worker token читается из `~/.config/mcp-vn/worker.env`. CLIProxyAPI должен слушать localhost:8317; его ключ хранится в `~/.local/share/mcp-vn-universal-proxy/client-key`. Эти файлы не входят в Git.
4. Только при первой установке выполни `python3 ~/.local/share/mcp-vn-model-lab/server.py --init`. Сохрани выданный пароль в менеджере паролей. При обновлении не используй `--reset-password`.
5. Скопируй `deploy/mcp-vn-model-lab.service` в `~/.config/systemd/user/`, выполни `systemctl --user daemon-reload`, затем `systemctl --user enable --now mcp-vn-model-lab.service`.
6. Открой `http://PC_LAN_IP:8190/vn/`, войди паролем Model Lab, выбери сохранение и рассказчика. Для внешнего аккаунта используй «Подключения» и код устройства.

Сервис рассчитан на доверенную LAN. Не перенаправляй порт 8190 в интернет без отдельного проектирования защищённого доступа. Конфигурация CLIProxyAPI и его бинарный файл управляются отдельно от этого репозитория; должны поддерживаться `/v1/models`, `/v1/chat/completions`, `-codex-device-login` и `-xai-login`.
