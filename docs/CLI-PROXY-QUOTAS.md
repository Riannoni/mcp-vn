# CLIProxyAPI quotas — эксплуатация на игровом ПК

> Перед разработкой/администрированием прочитать [../AGENTS.md](../AGENTS.md) и [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md). Этот документ описывает **локальную установку**, а не универсальный облачный endpoint. Секреты не коммитить.

## Назначение и текущая настройка

На Bazzite ПК работает пользовательская служба `mcp-vn-universal-proxy.service`, CLIProxyAPI v8.0.46. Порт `127.0.0.1:8317` доступен **только с самого ПК**, `management.allow-remote: false`. Management API **v8** активирован; control panel включён, автоматическое обновление panel-asset отключено. Не переключать bind на `0.0.0.0` и не включать `allow-remote` для удобства: management key способен изменять настройки и через `requests/api-call` использовать подключённые OAuth credentials.

**Открыть с самого игрового ПК**: http://127.0.0.1:8317/management.html. Встроенный интерфейс умеет показывать OAuth credentials, квоты/окна Codex и поддерживаемые Grok/xAI, запросы и состояние сервисов. Чтобы авторизоваться в UI, нужен *management key*, не ключ игрового OpenAI-compatible API. Прочитать management key **непосредственно в локальном терминале ПК**, не отправлять его в чат, issue или screenshot:

```bash
cat ~/.config/mcp-vn/cli-proxy-management.key
```

Не включать «Remember password» в общем браузере. Через телефон/другой компьютер интерфейс **намеренно недоступен**: потребуется защищённый SSH-туннель или отдельный строго read-only агрегатор (не прямое открытие management в LAN/Internet).

## Команда получения квот без браузера

```bash
~/.local/bin/vn-proxy-quota
~/.local/bin/vn-proxy-quota --json
```

Команда на ПК читает файл управления локально, получает текущий `auth_index` Codex через `GET /v8/management/credentials` и вызывает официальный для клиента Codex внутренний endpoint учёта `https://chatgpt.com/backend-api/wham/usage` **через API самого CLIProxyAPI** (`POST /v8/management/requests/api-call`). Upstream bearer остаётся внутри proxy и не распечатывается. Ничего не отправляется в inference; **проверка квоты сама по себе не расходует LLM-токены**. Формат `wham/usage` внутренний и может меняться; если вернулись 401/403/502, не считать отсутствие окна «100% доступно».

Текущая поддержка локального CLI: **Codex OAuth**; окно ~5 часов и ~7 дней, plan/allowed, процент использования, время сброса в Asia/Novosibirsk. Процент `used_percent` означает **потрачено**, остаток = `100 - used_percent`. Прочие provider quotas смотреть через встроенную management UI; получение Grok/xAI зависит от типа OAuth/tier и не подтверждено этим скриптом.

**Операционное правило ночному агенту:** читать квоту перед стартом и на границах ограниченных задач. Не полагаться исключительно на `allowed=true`; кодовые/визуальные эксперименты имеют отдельный лимит времени, GPU и стоп-условия. Наличие доступной квоты Codex не доказывает независимость от других интерфейсов ChatGPT/Work и не гарантирует произвольный 8-часовой запуск. Не предполагать независимых лимитов.

## Где находится настройка (локальные приватные файлы)

- Config: `~/.local/share/mcp-vn-universal-proxy/config.yaml` (`0600`).
- Локальный management key: `~/.config/mcp-vn/cli-proxy-management.key` (`0600`), **не публиковать содержимое**.
- CLI: `~/.local/bin/vn-proxy-quota` (`0700`).
- Backup конфигурации до включения: `~/.local/share/mcp-vn-universal-proxy/backups/config.before-quota-*.yaml` (`0600`).
- Unit: `systemctl --user status mcp-vn-universal-proxy.service`.

В момент первого запуска plaintext management key в YAML был автоматически заменён CLIProxyAPI на bcrypt-хеш. Отдельный файл с исходным ключом позволяет локально пользоваться API. **Не удалять ключевой файл без плана восстановления**: хеш не позволяет восстановить исходный plaintext.

## Проверки после изменений / reboot

```bash
systemctl --user is-active mcp-vn-universal-proxy.service
ss -ltn | grep ':8317'            # только 127.0.0.1:8317
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8317/v8/management/credentials
# Ожидание без management key: 401
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8317/management.html
# Ожидание: 200
~/.local/bin/vn-proxy-quota
```

После изменения конфигурации **не перезапускать** proxy во время активного пользовательского LLM-запроса. Проверить отсутствие активных соединений/операций, сделать приватный backup, затем `systemctl --user restart mcp-vn-universal-proxy.service` и выполнить проверки. Включение management API не требует изменения OAuth auth-файлов.

## Диагностика и возврат

- `404` на management: `management.secret-key` пуст, не загружен корректный конфиг, либо URL API версии ошибочен (`/v8/management/...`).
- `401`: неверный management key; не повторять вслепую — подряд несколько ошибок могут вызвать временный ban.
- `502` на `requests/api-call`: ошибка upstream/сетевого маршрута/OAuth; не интерпретировать как исчерпание лимита.
- Доступны Codex и xAI OAuth, однако quota-check скрипт измеряет **именно Codex**. Если upstream возвращает дополнительные пулы, script сообщает их количество, не выдумывая значения.
- Rollback: в отсутствие активного LLM-запроса вернуть приватный `config.before-quota-*.yaml`, сохранить права `0600`, перезапустить **только** proxy unit. Это вновь отключит Management API, но не должно менять остальную игровую инфраструктуру. Не копировать backup или management key в GitHub.

**Документация upstream:** [CLIProxyAPI v8 Management API](https://help.router-for.me/management/apiv8), [config management options](https://help.router-for.me/configuration/options), [официальный Management Center](https://github.com/router-for-me/Cli-Proxy-API-Management-Center).
