# CLIProxyAPI OAuth quotas — Codex и Grok / xAI

> **Операционная инструкция для личного игрового ПК** (Bazzite, CLIProxyAPI v8.0.46, 31 октября 2026). Перед работой: [../AGENTS.md](../AGENTS.md) и [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md). Состояние квот и установленные версии динамические: **всегда повторять проверку**. Здесь нет токенов и приватных данных.

## 1. Что именно теперь работает

Через **один существующий OAuth-прокси** доступны два независимых представления использования:

| Провайдер | Источник (через CLIProxyAPI) | Подтверждённые поля | Как трактовать |
| --- | --- | --- | --- |
| Codex / ChatGPT | `GET https://chatgpt.com/backend-api/wham/usage` | `plan_type`, `rate_limit.allowed`, `limit_reached`, `primary_window`, `secondary_window` | % **использовано** в коротком (~5 ч) и длинном (~7 д) окне, время сброса |
| Grok Build / xAI OAuth | `GET https://cli-chat-proxy.grok.com/v1/billing?format=credits` | `config.creditUsagePercent`, `config.currentPeriod.type/start/end`, fallback `billingPeriodStart/End` | % **израсходовано** в указанном upstream расчётном периоде, время сброса |

**Данные подтверждены реальными, успешными HTTP 200 вызовами на этой установке**. Формат Grok оказался `USAGE_PERIOD_TYPE_WEEKLY`; выставлять «неделю» для другого типа автоматически нельзя. Запросы — к billing/usage, **не к inference-модели**, поэтому LLM-токены не генерируются. Однако upstream может ограничивать частоту обращений; не опрашивайте API каждую секунду.

### Пример первого измерения (исторический снимок, НЕ live)

**31 октября 2026**, местный часовой пояс `Asia/Novosibirsk`:

| Провайдер | Использовано | Осталось | Следующий сброс |
| --- | ---: | ---: | --- |
| Codex, короткое окно 5 часов | 0% | 100% | 31.10, 06:58:47 |
| Codex, недельное окно | 9% | 91% | 04.11, 21:17:14 |
| Grok/xAI, недельный период | 81% | 19% | 04.11, 17:49:08 |

Даты Codex возвращаются в epoch seconds, Grok — в ISO8601 с временной зоной. Отображаемые значения в этом примере зафиксированы при настройке; **не используйте их для решения о ночной работе**. Опросите команду заново.

**Важная оговорка:** Grok Build OAuth billing представляет соответствующий период/кредиты CLI и не обязательно покрывает *все* лимиты чата grok.com, все модели, отдельные медиа-сервисы или платный xAI API-биллинг. Нельзя называть 19% «универсальным остатком всего Grok» без документального подтверждения связи конкретного endpoint и услуги. Аналогично Codex OAuth не даёт безлимитного API.

## 2. Использование на ПК: терминал

Проверенная локальная команда (доступна под пользователем `Xavok`):

```bash
~/.local/bin/vn-proxy-quota
~/.local/bin/vn-proxy-quota --provider codex
~/.local/bin/vn-proxy-quota --provider xai
~/.local/bin/vn-proxy-quota --json
~/.local/bin/vn-proxy-quota --provider xai --json
```

- Без параметров выводятся **оба** провайдера.
- `--provider` ограничивает опрос одним провайдером.
- `--json` возвращает очищенный от персональных данных объект с `checked_at`, `timezone` и `accounts[]`. В каждом элементе: `provider`, `account_number`, `status`, проценты `used_percent`/`remaining_percent`, окно/сброс и только необходимый минимум статуса.
- Код выхода **0** означает успешное чтение заявленных числовых квот для всех запрошенных аккаунтов. **1** означает, что хотя бы один провайдер недоступен, его формат изменился, числовая квота не получена или запрос завершился ошибкой. Наличие `status=ok` не означает, что есть достаточно квоты для ночной работы — смотри сами проценты и `allowed`.
- `auth_index` используется только **внутри локального процесса** для выбора токена в Management API; файл OAuth, bearer, email, user ID и сырой HTTP body не записываются и не выводятся.

Для машинного gate (пример, **не политика релиза**):

```bash
~/.local/bin/vn-proxy-quota --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print([(a["provider"],a["status"]) for a in d["accounts"]])'
```

Ночной агент обязан дополнительно установить собственные лимиты на продолжительность, стоимость, число GPU jobs и STOP-условия. Расход квоты между окнами не линейный и другие приложения/сессии тоже могут менять значения. `remaining_percent` — это **100 минус использование**, а не доллары/токены.

## 3. Веб-панель (только на игровом ПК)

Адрес: **http://127.0.0.1:8317/management.html**

Management API: `http://127.0.0.1:8317/v8/management` (в версии 8 префикс **`/v8/`**, старые `/v0/` инструкции неприменимы).

Чтобы авторизоваться в панели, *не* используйте игровой inference API key. Управляющий пароль хранится локально:

```bash
cat ~/.config/mcp-vn/cli-proxy-management.key
```

**Не передавать этот секрет в ChatGPT, GitHub, скриншоты или лог**, не хранить в общедоступном браузере. Management API разрешает не только чтение квот, но и изменяющие операции. Панель недоступна напрямую с телефона/другого ПК — это намеренная защита. Для удалённого интерфейса использовать только отдельный аутентифицированный read-only агрегатор или авторизованный SSH-туннель на loopback, но **не** переключать Management API на публичный bind.

## 4. Как устроен мониторинг

Утилита [../scripts/cli-proxy-quota.py](../scripts/cli-proxy-quota.py) — стандартная библиотека Python 3; `zoneinfo` использует `Asia/Novosibirsk` для вывода дат. Код установлен локально как `~/.local/bin/vn-proxy-quota`.

1. Читает `~/.config/mcp-vn/cli-proxy-management.key` **только локально**.
2. `GET /v8/management/credentials` — получает **сейчас действующие** `auth_index` для провайдеров `codex` и `xai`, пропускает `disabled`; не привязывается к имени OAuth-файла или аккаунту по email.
3. `POST /v8/management/requests/api-call`: только закреплённые в коде GET URLs, `Authorization: Bearer $TOKEN$` подставляется CLIProxyAPI внутри своей памяти. Никакой из OAuth bearer не передаётся вызывающему скрипту.
4. Сначала проверяет HTTP 200 и корректность JSON, потом строго и независимо парсит каждый провайдер. Если процент отсутствует, нечисловой, NaN или вне 0–100, **помечает квоту unavailable**, не подменяет её 0%.
5. В Grok `currentPeriod.type` различает weekly/monthly/daily/unknown; дата и длительность показываются только при корректных ISO8601-границах. Нельзя считать «недельный» статус универсальным, если сервер вернёт иной тип периода.
6. Сетевой таймаут 20 секунд на запрос; предел размера ответа 1 МиБ; вывод содержит только отфильтрованные поля. При ошибке нет автоматического повторного запроса и **не печатается** raw тело HTTP.
7. Выводит локальную дату сброса и код успеха. Кеш, история запросов, токены и private account identity на диск не сохраняются.

**Стабильность API:** `/backend-api/wham/usage` и `/v1/billing?format=credits` — внутренние/зависящие от версии интерфейсы; могут меняться без предупреждения. Это отдельный инструмент для личного мониторинга, не гарантия стороннего SLA.

## 5. Безопасность и сохранённые файлы

| Что | Где находится | Доступ |
| --- | --- | --- |
| конфигурация CLIProxyAPI | `~/.local/share/mcp-vn-universal-proxy/config.yaml` | `0600` |
| management key (исходный) | `~/.config/mcp-vn/cli-proxy-management.key` | `0600` |
| установленный quota CLI | `~/.local/bin/vn-proxy-quota` | `0700` |
| backup CLI до поддержки Grok | `~/.local/bin/vn-proxy-quota.before-grok-20261031` | `0700` |
| backup конфигурации до включения Management API | `~/.local/share/mcp-vn-universal-proxy/backups/config.before-quota-*.yaml` | `0600` |
| пользовательский сервис | `mcp-vn-universal-proxy.service` | `systemctl --user` |

Сервис настроен на `127.0.0.1:8317` и `management.allow-remote: false`. После первого запуска plaintext secret был заменён в YAML bcrypt-хешем; исходный ключ хранится отдельно и **не восстанавливается из хеша**. Для добавления Grok ничего в этой конфигурации менять не понадобилось. Существующие игровые подключения и GPU не затрагивались.

Проверки безопасности без публикации значений:

```bash
systemctl --user is-active mcp-vn-universal-proxy.service
ss -ltn | grep ':8317'       # только 127.0.0.1:8317
stat -c '%a %n' ~/.config/mcp-vn/cli-proxy-management.key
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8317/v8/management/credentials
# Без management key ожидается 401.
```

## 6. Установка или восстановление скрипта из GitHub

Исходник версии, которую можно переустановить: [scripts/cli-proxy-quota.py](../scripts/cli-proxy-quota.py). Тесты: [scripts/tests/test_cli_proxy_quota.py](../scripts/tests/test_cli_proxy_quota.py).

В существующей рабочей копии репозитория (в отдельной ветке/copy, не изменяя чужие незакоммиченные файлы):

```bash
python3 -m unittest discover -v -s scripts/tests -p 'test_cli_proxy_quota.py'
python3 -m py_compile scripts/cli-proxy-quota.py
install -m 700 scripts/cli-proxy-quota.py ~/.local/bin/vn-proxy-quota
~/.local/bin/vn-proxy-quota
```

Перед перезаписью установленного скрипта рекомендуется сохранить его `cp -p` в приватный backup, затем выполнить `--provider codex`, `--provider xai` и `--json`. Без локального management key восстановленный скрипт корректно откажет: секрет специально не находится в Git.

## 7. Неисправности, диагностика, rollback

| Симптом | Причина / действие |
| --- | --- |
| `no_credential` | Провайдер не подключён или отключён в CLIProxyAPI. Проверить авторизацию в локальном UI, не копировать OAuth JSON в чат. |
| `upstream_error`, HTTP 401/403 | OAuth истёк, аккаунт/тип подписки не имеет доступа или billing endpoint не подходит для платного API типа; не делать бесконечные повторы. |
| HTTP 429 | Частотный лимит самого сервиса. Остановить опрос и повторить существенно позже. |
| `request_failed` | Недоступен proxy/управление/сеть/временный upstream отказ; не считать квоту истраченной или свободной без дополнительных данных. |
| `unavailable` | Сервер ответил, но не сообщил валидный процент; период/схема могли поменяться. **Unknown ≠ 100% free**. |
| нет панели / management 404 | Проверить config `management.secret-key`, service unit, правильный URL `/v8/management`. |
| management 401 | Неверный локальный management key; не повторять десятки раз (возможна блокировка). |
| Grok 403 только на billing | Известное различие между Grok Build CLI OAuth billing и платным `api.x.ai` OAuth. Не обходить ограничение запросами к неизвестным endpoint; в таком случае показывать `unavailable`. |

**Откат только новой функции:** `cp -p ~/.local/bin/vn-proxy-quota.before-grok-20261031 ~/.local/bin/vn-proxy-quota`; proxy остаётся запущенным, Codex вернётся к прошлой утилите, Grok исчезнет из CLI. Перезапуск прокси не нужен.

**Откат включения Management API целиком:** когда нет активных LLM-вызовов, восстановить приватный `config.before-quota-*.yaml`, проверить `0600`, перезапустить только `systemctl --user restart mcp-vn-universal-proxy.service`; Management API снова будет отключён. Не менять game state, ComfyUI и OAuth credentials.

## 8. Первоисточники

- [CLIProxyAPI — xAI OAuth](https://help.router-for.me/configuration/provider/xai)
- [CLIProxyAPI — v8 Management API](https://help.router-for.me/management/apiv8)
- [Официальный код Grok Build billing (x.ai)](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-shell/src/extensions/billing.rs)
- [Совместимость платного xAI OAuth и Grok Build billing](https://github.com/router-for-me/Cli-Proxy-API-Management-Center/issues/350)

**Итог по установке (2026-10-31):** Codex и Grok OAuth успешно опрошены, обе записи `status=ok`, самостоятельный JSON-путь проверен, 7 unit-тестов прошли, скрипт поставлен без изменения игрового кода, секретов и конфигурации proxy.
