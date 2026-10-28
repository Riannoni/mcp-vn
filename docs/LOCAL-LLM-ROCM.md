# KoboldCpp на ROCm: Cydonia + Qwen (mcp-vn 0.6.4)

## Действующая конфигурация

На игровом ПК Bazzite с Radeon RX 9070 XT (16 ГБ VRAM, 32 ГБ RAM) работает **один** защищённый, запускаемый по запросам KoboldCpp gateway. Используется официальный ROCm/HIP executable, а **не** проблемная Vulkan-сборка. Токен хранится в приватном PC EnvironmentFile и не передаётся браузеру.

| Роль | Model ID | Веса | Context | Размещение |
| --- | --- | --- | ---: | --- |
| Рассказчик **локального эпизода** | `cydonia:24b-v4.3-iq4_xs` | Cydonia 24B IQ4_XS | 4096 | 30 GPU layers + остальное RAM/CPU |
| Визуальный режиссёр JSON + fallback | `qwen3.5:9b-q4_K_M` | Qwen3.5 9B Q4_K_M | 8192 | 99 layers requested (33/33 offloaded в тесте) |
| Канонический главный сюжет | ChatGPT через MCP | — | — | Не менялся |

`compose.yaml` передаёт `VN_LOCAL_NARRATOR_MODEL` и `VN_LOCAL_NARRATOR_FALLBACK`. `src/local-scene.mjs` сначала сохраняет локальный текст, затем просит Qwen разработать JSON-состояние картинки. Ошибка Cydonia или текст, не прошедший quality gate, вызывает резервный Qwen. Изменения не возвращают приватные реплики в основную историю.

## ROCm/CPU и разделяемая видеокарта

Программный шлюз `deploy/kobold-gateway.py` запускает отдельный процесс KoboldCpp на запрос и завершает его после ответа, освобождая VRAM для ComfyUI. Перед стартом он проверяет наличие активных ComfyUI jobs. GPU-конфликт с новым заданием, пришедшим **во время** LLM, всё ещё возможен: это координация приложения, не аппаратный scheduler.

Активный systemd user override (пример `deploy/mcp-vn-kobold-rocm.conf`):

```ini
[Service]
Environment="VN_KOBOLD_BACKEND=rocm"
Environment="VN_KOBOLD_CPU_ONLY=0"
Environment="HIP_VISIBLE_DEVICES=0"
```

При ошибке ROCm gateway один раз повторяет запрос на CPU и на текущий срок жизни службы отключает новые ROCm-попытки именно для проблемной модели (circuit breaker). Следующий запрос показывается как `koboldcpp-cpu`. Не скрывайте фактический backend в метриках — UI Model Lab отдельно отображает GPU/ROCm или CPU.

Qwen загружается с параметрами `--reasoningeffort none` и `--jinjathink false`, чтобы ответ локального рассказчика не начинался с служебного `<think>`.

## Результаты контрольных тестов

| Модель | Холодная загрузка | Короткая генерация | Важно |
| --- | ---: | ---: | --- |
| Qwen 9B, ROCm | ~7,2 с | ~54 ток/с | Контекст 8192 |
| Cydonia 24B, ROCm | ~8,6 с | ~12,6 ток/с | Контекст 4096, частичный offload |

Дополнительная проверка через **рабочий** авторизованный gateway: Cydonia 101 токен за 19,1 с, Qwen 71 токен за 7,7 с после исправления чата. Все цифры относятся к коротким нейтральным запросам на конкретном оборудовании, а не к целому сюжету с заполненным контекстом.

После переключения обеих LLM контрольные рендеры ComfyUI на Pony, WAI и Anima прошли. Ранее Vulkan вызывал два сброса вычислительной очереди AMD — возвращать его без отдельной диагностики не рекомендуется.

## Бинарный файл и происхождение

Поставщик: https://github.com/LostRuins/koboldcpp/releases/download/rocm-rolling/koboldcpp-linux-x64-rocm

На момент установки:
- ROCm build 1.121; размер 661999280 байт.
- SHA-256: `418016f2d0945a1b3092cba53ff16a76224e289f7c47284ca3115962152ba71d`.
- Путь PC: `~/.local/share/mcp-vn-kobold/bin/koboldcpp-rocm`.
- CPU fallback binary остаётся `~/.local/share/mcp-vn-kobold/bin/koboldcpp`.
- Код gateway в репозитории: `deploy/kobold-gateway.py`. Проверенный download helper — `deploy/download-koboldcpp-rocm.sh`.

**Внимание:** тег `rocm-rolling` со временем изменяется. Перед обновлением сверяйте контрольную сумму с актуальным upstream asset API; старая SHA действительна только для указанного бинарника.

## Диагностика

На ПК:

```bash
systemctl --user status mcp-vn-kobold-gateway.service
journalctl --user -u mcp-vn-kobold-gateway.service -n 100 --no-pager
curl -fsS http://127.0.0.1:8188/queue
```

На домашнем сервере: MCP `local_model_health` показывает доступность модели и тип GPU-блокировки. Логи gateway могут содержать текст запроса и должны обрабатываться как частные.

`tests/pc-kobold-backends.test.py` на ПК проверяет выбор ROCm, CPU override, резервный повтор и circuit breaker. Это тест маршрутизации, **не** измерение скорости.

## Быстрый CPU rollback

При проблемах с ROCm не меняйте игровой сюжет и сохранения. Создайте второй пользовательский systemd override с более высоким номером:

```bash
mkdir -p ~/.config/systemd/user/mcp-vn-kobold-gateway.service.d
printf '[Service]\nEnvironment="VN_KOBOLD_CPU_ONLY=1"\n' \
  > ~/.config/systemd/user/mcp-vn-kobold-gateway.service.d/99-force-cpu.conf
systemctl --user daemon-reload
systemctl --user restart mcp-vn-kobold-gateway.service
```

Возврат на ROCm: удалите **только** `99-force-cpu.conf`, выполните `daemon-reload` и перезапустите `mcp-vn-kobold-gateway.service`.

### Почему не держим Cydonia в VRAM постоянно

24B IQ4_XS с контекстом и KV-кешем занимает значительную часть 16 ГБ. На той же карте работают Pony/WAI/Anima и Wan. Warm-pool здесь может ухудшить доступность ComfyUI и вызвать memory thrashing. При наличии второй GPU стратегия может измениться; для текущей машины оптимальнее запускать LLM на время хода и освобождать память.
