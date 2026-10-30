# Night Agent — автономная разработка web-vn

> **Нормативно:** перед любым новым запуском изучить [../AGENTS.md](../AGENTS.md) и [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md). Сведения о рендере в [RENDER-HANDOFF-2026-10-31.md](RENDER-HANDOFF-2026-10-31.md) и issue #20 — исходное состояние, но не доказательство текущего runtime. Этот документ описывает установленный ночной контур на личном Bazzite-PC по состоянию на 31.10.2026.

## 1. Возможности и ограничения

Ночной агент — самостоятельный **Codex CLI, работающий на ПК после завершения чата**. Использует OpenAI Responses API через уже работающий CLIProxyAPI с Codex OAuth. Это не непрерывная сессия ChatGPT; качество и доступное время зависят от модели/квот. **Модель по умолчанию GPT-6 Astra (High reasoning)**. Другую модель разрешено выбирать только явной командой владельца, варианты: GPT-6.1 Sol или GPT-6.1 Terra. Нет автоматического fallback на Grok, локальную модель либо платный API.

Цель — source-only P0 исправления, регрессионные тесты, доказательства и передача результата. Нельзя самостоятельно менять production worker, системные службы, игровые сохранения, принятые CG, GPU очередь, установленные модели, сеть, секреты и настройки OAuth. Нельзя самостоятельно git push, merge в main или выкатывать в prod. Изолированная рабочая копия, локальная ветка, явный disabled push URL. Просмотр реальных PNG как G2 требует отдельного доступа к кадрам и независимой визуальной приёмки, поэтому ночной агент **не имеет права заявлять render-v1 готовым**.

## 2. Вход: команда владельца из ChatGPT

Например: «Запусти ночного агента на 10 часов, продолжай текущий P0». Тогда ассистент:
1. Читает AGENTS.md, DEVELOPMENT-AND-TESTING.md и эту инструкцию; убеждается, что нет другого запуска, отдельный ПК и Codex OAuth доступны.
2. Через установленный SSH-MCP вызывает infra_exec(host="home", as_root=true), затем с home строго проверенным SSH к Xavok-PC (см. [REMOTE-ACCESS.md](REMOTE-ACCESS.md)). Не публикует приватный ключ.
3. На ПК выполняет:

~~~
~/.local/bin/vn-night start --hours 10
~/.local/bin/vn-night status --json
~~~

4. При выборе **пользователем** иной модели: 

~~~
~/.local/bin/vn-night start --hours 24 --model gpt-6.1-sol --task 'Явно указанная цель'
~~~

5. Создаёт отдельную Automation ChatGPT с почасовым расписанием и read-only сбором /home/Xavok/.local/bin/vn-night status --json через тот же SSH-MCP, включая последний hourly report. Automation **не запускает второй агент** и не правит код. Когда приватный SSH недоступен scheduled-turn, Automation обязана сообщить о недоступности, а не выдумывать статус.
6. Возвращает проверенный run_id, модель, начало, deadline по Asia/Novosibirsk, квоту и текущий state.

Остановка только по явной команде владельца:

~~~
~/.local/bin/vn-night stop
~~~

Бинарник поддерживает 0.1–72 часа на один старт. Для 24/7 требуются отдельные последовательные разрешённые интервалы, их лимиты и непрерывный внешний supervisor; **существующий 10-часовой запуск не продлевается автоматически**.

## 3. Команды статуса и отчётов

На ПК:

~~~
~/.local/bin/vn-night status
~/.local/bin/vn-night status --json
~/.local/bin/vn-proxy-quota --provider codex
systemctl --user is-active vn-night-20261031-021227.service
~~~

Для первого запуска:
- ID 20261031-021227.
- Начало: 31.10.2026 02:12:27 (Asia/Novosibirsk).
- Плановый конец: 31.10.2026 12:12:27 (Asia/Novosibirsk).
- Systemd unit: vn-night-20261031-021227.service.
- Рабочая ветка: night/20261031-p0-shadow, SHA источника при старте ca10be4.
- Приоритет: issue #49 + #20, read-only **shadow** atomic required object/actor-contact evidence с fail-closed и нейтральными регрессионными тестами.
- Почасовая Automation: ID 6ae4ec33db048191af03a0f0c102e8f4; Asia/Novosibirsk, с 03:15 каждый час, COUNT=10, последний запуск около 12:15.
- Все частные логи и статусы: ~/.local/share/web-vn-night-runner/runs/20261031-021227/.

Структура внутри run:
- status.json — актуальные state, heartbeat timestamp, iteration, model, quota, git head/число изменённых файлов, краткое agent summary. Выдача через status --json дополнительно проверяет systemd unit.
- events.jsonl — время/название события, без приватных данных/сырого токена.
- latest-hourly.md — последнее готовое почасовое резюме; hourly.md — нарастающая история.
- codex-XX.jsonl и codex-XX.stderr.log — приватные подробные агентные журналы. **Могут содержать исходный код и внутренние prompt: не выгружать целиком в GitHub**.
- last-message.txt — результат последнего законченного Codex цикла; NIGHT_HANDOFF.md пишется агентом в изолированном checkout.

Значения состояния: starting, working, paused_quota, blocked_repeated_error, completed_time_limit, stopped, failed, ended_unexpectedly, stale_heartbeat. При stale_heartbeat или когда unit не active — не говорить, что он работает, даже если в JSON сохранился state=working.

## 4. Состав установленного окружения

- Codex CLI 0.166.0: ~/.local/share/web-vn-night-runner/bin/codex
- Code Mode Host той же официальной версии: ~/.local/share/web-vn-night-runner/bin/codex-code-mode-host
- wrapper: ~/.local/share/web-vn-night-runner/bin/proxy-codex — локально читает existing access key CLIProxyAPI, передаёт только дочернему процессу env VN_NIGHT_PROXY_KEY. В stdout и args ключ не появляется.
- отдельный config: ~/.local/share/web-vn-night-runner/codex-home/config.toml (0600). model=gpt-6-astra, model_reasoning_effort=high, model_provider=vnproxy, wire_api=responses, env_key=VN_NIGHT_PROXY_KEY, base_url=http://127.0.0.1:8317/v1, sandbox=workspace-write, разрешён network_access ради локального endpoint.
- пользовательский CLI: ~/.local/bin/vn-night (0700), source в [../scripts/night-agent.py](../scripts/night-agent.py).
- независимый git checkout: ~/.local/share/web-vn-night-runner/work/web-vn. НЕ использовать /opt/mcp-vn, production home git или директории экспериментального worker на PC. Push URL origin специально установлен в disabled://night-runner-no-push.
- никакие токены/секреты/сохранения не коммитятся, локальный Management API остается loopback.

Bootstrap: бинарник Codex CLI, загруженный из официального release, **не включал** codex-code-mode-host. Первые короткие ответы Codex возвращали ошибку, так что их нельзя считать настоящей разработкой. Matching Code Mode Host установлен из того же release с проверенным SHA256. Дальнейший код начал выдавать инструментальные события. Сам факт инструмента != успешное исправление, вывод берётся из реальных тестов и handoff.

## 5. Лимиты, гейты, остановка

Перед каждым циклом запускается [CLI-PROXY-QUOTAS.md](CLI-PROXY-QUOTAS.md), то есть read-only quota-check через локальный прокси. Контролируется Codex OAuth: **не начинать новый цикл, если использовано >=85% в любом из 5-часового и недельного окон**, если upstream сообщает limit_reached/allowed=false или квота недоступна. Не переключать на другую модель для обхода лимита. Отсутствующие данные никогда не означают 100% свободно.

Один Codex exec ограничен 45 минутами; supervisor отслеживает время каждую ~15 секунд и снимает группу процессов по достижении предела. При двух ошибках цикла подряд останавливается, вместо бесконечной серии. Systemd дополнительно ограничивает общую длительность на (hours + 180 секунд). Проверки GPU и визуальная приёмка не подменяются зелёными unit tests. Ночной агент не имеет разрешения делать GPU эксперименты, пока пользователь параллельно работает с игрой.

## 6. Качество и приёмка результата

Каждая итерация обязана: перечитать базовые правила и handoff, найти ровно одну проверяемую причину, создать negative regression first, сделать минимальный fix, провести подходящие source-тесты, просмотреть git diff, обновить NIGHT_HANDOFF.md и оставить только **локальный коммит** проверенного исходника. Никаких генерируемых приватных PNG/GPU. Если данные отсутствуют: BLOCKED / G2 UNVERIFIED. Целевые P0-критерии render-v1 остаются прежними: отдельный проход 1 Sprite + 3 CG и golden >=30 сцен с human labels. Работа ночью — источник исходников/гипотез, а не автоматический релиз.

С утра: получить status и последний handoff, проверить локальные коммиты и source diff относительно точного main SHA, прогнать тесты, обсудить G2/G3, затем **отдельной разрешённой командой** переносить проверенный результат в main/production. Код в main не должен меняться автоматически из-за запуска/завершения этого runner.

## 7. Установка из исходников, тесты, rollback

Source: [../scripts/night-agent.py](../scripts/night-agent.py); tests [../scripts/tests/test_night_agent.py](../scripts/tests/test_night_agent.py).

~~~
python3 -m py_compile scripts/night-agent.py
python3 -m unittest discover -v -s scripts/tests -p 'test_night_agent.py'
# Только после остановки работающего агента:
install -m 700 scripts/night-agent.py ~/.local/bin/vn-night
~~~

Для восстановления после сбоя: `~/.local/bin/vn-night status --json`, затем systemctl --user status UNIT, локальные журналы. Прежде чем запустить заново, проверить, не остался ли активный child Codex, изменённые файлы в isolated checkout и последнюю квоту. Не запускать второй параллельный контроллер.

Для rollback новых файлов supervisor: остановить текущий unit, сохранить приватные отчёты и локальные git-коммиты, вернуть предыдущий сохранённый CLI/версию Codex. **Не откатывать production или канонические сохранения**, потому что они не затрагивались. Не открывать management API наружу.

## 8. Источники

- [Официальная документация Codex CLI](https://learn.chatgpt.com/docs/cli)
- [Официальные CLI-параметры exec](https://learn.chatgpt.com/docs/cli/reference)
- [CLIProxyAPI для Codex](https://github.com/router-for-me/CLIProxyAPIDocs/blob/main/docs/en/agent-client/codex.md)
- [OAuth quota monitoring](CLI-PROXY-QUOTAS.md)

## 9. Дополнительные реальные bootstrap-инциденты и восстановление

После установки Code Mode Host ранние рабочие циклы вызвали **HTTP 413 Payload Too Large** от локального CLIProxyAPI: ранее для игры был задан `server.max-request-body-bytes: 200000`, а после нескольких source/read-tool событий тело запроса Codex Responses выросло. Перед изменением проверено `ss`: активных соединений на `127.0.0.1:8317` не было. Создан private backup `~/.local/share/mcp-vn-universal-proxy/backups/config.before-night-payload-20261031.yaml`, увеличен `max-request-body-bytes` до `16000000` (16 MB), перезапущен **только** user `mcp-vn-universal-proxy.service`. Проверены loopback bind, 37 models и активность сервиса. Никаких прав управления сетью/публикаций наружу не добавлено. Изменение нужно учитывать при обновлении CLIProxyAPI и откатывать только при отсутствии активных LLM-запросов.

Ночной запуск был **возобновлён под тем же run ID** с новым systemd unit `vn-night-20261031-021227-resume`, сохранением исходного deadline **12:12:27 31 октября** и перенастроенным `runs/current.json`. Это важно: старый `vn-night-20261031-021227.service` после аварии завершился, поэтому `status --json` обращается к unit из current.json, а не к жёстко зашитому имени. Первые 5 итераций **НЕ** считаются кодовым успехом, G2 НЕ ПРОВЕРЕН.

Реальные ошибки показали, что Codex CLI иногда может вернуть нулевой код выхода, даже если Code Mode не выполнил ни одной команды. В новой версии исходника добавлена проверка JSONL-событий: отсутствие законченного `command_execution` или ошибки Code Mode/HTTP 413 формально дают failed-iteration. Эта версия будет применяться **к следующему запуску** после тестов, не подменяет уже загруженный в память текущий 10-часовой процесс. Это причина проверять не только exit code, но и реальный semantic progress. 

## 10. Контроль новых файлов и коммитов

Первый фактический source-only цикл создал `worker/atomic_prop_gate.py`, две новые regression tests и `NIGHT_HANDOFF.md`. Отчёт агента сообщил о 35 прошедших тестах, но Git-коммит невозможен внутри `workspace-write` sandbox (метаданные `.git` доступны только для чтения). Это **не потеря изменений**: файлы сохранены в изолированном checkout до независимого ревью. Поэтому новый supervisor больше не требует от агента коммита и учитывает untracked файлы при подсчёте `changed_files`. Эти поправки вступают в силу в **следующем** запуске. Живой процесс продолжает работать на своей прежней загруженной версии, а Cloud Automation дополнительно проверяет `git status --short`. Публикация изменений в GitHub из ночного процесса запрещена.

## 11. Автоматическое возобновление после сброса короткой квоты (установлено)

**Проблема:** GPT-6 Astra за первые минуты начал быстро расходовать 5-часовой пул Codex OAuth. Завершать 10-часовую работу окончательно на `85%` короткого окна неправильно: следующий 5-часовой цикл может открыться до общего дедлайна. **Модель автоматически не меняется**.

Поставлен отдельный маленький **read-only для production**, idempotent quota-resumer: [scripts/night-quota-resume.py](../scripts/night-quota-resume.py), тесты [scripts/tests/test_night_quota_resume.py](../scripts/tests/test_night_quota_resume.py).

Systemd user:
- `vn-night-quota-resume.timer` — проверка раз в **5 минут**, `OnCalendar=*:0/5`, без LLM-вызовов.
- `vn-night-quota-resume.service` — Python one-shot, читает **только локальный current.json, status.json и квоту Codex**.
- Скрипт не запускает второй агент, когда текущий unit active, а также **никогда** после `deadline_epoch`, при `blocked_repeated_error`, `failed`, `stopped`, при исчерпании **недельного** окна или неизвестном лимите.
- Только если предыдущий state=`paused_quota`, причина строго `5h_or_primary used >= 85%`, systemd unit уже завершился и оба окна снова ниже 85%, запускается новый user systemd-run **с тем же run_id и прежним deadline**. Новое имя unit сохраняется в current.json; монитор статуса должен читать его оттуда.
- Перед повторным запуском архивирует прежние `codex-*.jsonl` и stderr в приватной папке `paused-before-HHMMSS/`, чтобы не перезатереть доказательства. Общие `hourly.md`, handoff и git-worktree сохраняются.
- Единственный stop-фактор для всей 10-часовой работы — изначальный дедлайн или необратимый блокер/достижение недельного предела. Объём inference может быть значительно меньше 10 часов из-за ожидания квоты. **Никаких гарантий 10 часов непрерывной генерации.**

Проверить:

~~~
systemctl --user is-enabled vn-night-quota-resume.timer
systemctl --user is-active vn-night-quota-resume.timer
systemctl --user list-timers --all vn-night-quota-resume.timer
# Проверка вручную (без запуска нового агента при активном действующем):
systemctl --user start vn-night-quota-resume.service
~~~

После дня запуска timer может оставаться включённым: если нет подходящего `paused_quota`, он не выполняет изменений и не отправляет запросов модели. Чтобы полностью убрать периодическую проверку: `systemctl --user disable --now vn-night-quota-resume.timer`. Не удалять runtime-логи, статус или приватные сохранённые файлы.

Код на ПК: `~/.local/share/web-vn-night-runner/bin/night-quota-resume.py`, установлен из того же tested source; 5/5 unit tests (guards: active, wrong state, weekly, deadline, short window). Для будущей переустановки поставить source Python в этот путь с режимом `0700`, положить вышеописанные два user units, запустить `systemctl --user daemon-reload` и `enable --now`.

**Замечание о версиях:** существующий 10-часовой процесс работает на исходной версии `vn-night` в памяти; matching quota-resumer импортирует этот установленный CLI. Перед обновлением running supervisor выполнять ручной review совместимости, не подменять его без остановки.
