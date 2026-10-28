# Установка и обновление mcp-vn 0.6.4

## Перед началом

Это не однокомандный installer. Исходная установка рассчитана на домашний Ubuntu-сервер с Docker Compose и отдельный игровой ПК на Bazzite/Fedora с AMD ROCm, ComfyUI и systemd user services. Потребуются настроенные LAN/VPN, учётная запись ChatGPT и защищённый OAuth gateway на VPS.

**В репозитории нет весов AI, сохранений, ключей и токенов.** Пользователь самостоятельно получает совместимые модели с учётом их лицензий и авторизации. См. [MODELS.md](MODELS.md).

### Топология и порты

| Сервис | Пример | Доступ |
| --- | --- | --- |
| Node game | домашний сервер:3100 | разрешён только доверенным хостам LAN/VPN |
| ComfyUI | ПК `127.0.0.1:8188` | только ПК |
| Vision QA | ПК `127.0.0.1:9312` | только ПК |
| KoboldCpp gateway | ПК:11434 | только домашний game server + bearer token |
| Streamable HTTP MCP | `https://YOUR_DOMAIN/vn/mcp` | Internet через OAuth proxy |

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
openssl rand -hex 32    # VN_MCP_TOKEN
openssl rand -hex 32    # VN_ASSET_SECRET
```

Заполните приватную `.env`:

- `VN_PUBLIC_ORIGIN` — публичный HTTPS origin с префиксом `/vn`, если он используется.
- `VN_WORKER_TOKEN` — идентичный ключ для Node game и GPU-воркера/локального LLM gateway.
- `VN_MCP_TOKEN` — отдельный ключ для защищённого MCP API за VPS gateway.
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

## 5. VPS: публичный MCP и ChatGPT

Установите HTTPS reverse proxy / MCP gateway с проверкой OAuth/JWT, который принимает только аутентифицированные подключения к `/vn/mcp` и доверенным образом маршрутизирует их к домашнему серверу (например, по VPN). **Не** публикуйте порты worker, ComfyUI, KoboldCpp или `/data` в Интернет.

В этом репозитории находится сервер mcp-vn, **не полноценный Auth0/VPS gateway**; его нужно настраивать отдельно. Инструкция по пользовательской регистрации в ChatGPT: [CONNECT-CHATGPT.md](CONNECT-CHATGPT.md).

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
