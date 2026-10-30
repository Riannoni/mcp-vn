# web-vn Night Agent: квоты, исследования и резервная разработка — 31.10.2026

> Read [../AGENTS.md](../AGENTS.md), [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md), [NIGHT-AGENT.md](NIGHT-AGENT.md). Research is an evidence snapshot, not a new render-v1 acceptance result.

## Что произошло на самом деле

Ночной Codex CLI 0.166.0 (ChatGPT Plus OAuth → локальный CLIProxyAPI → gpt-6-astra), run \`20261031-021227\`, за первые ~23 минуты дошёл до защитного порога 5h квоты. В 02:42 Новосибирска реальный \`vn-proxy-quota --provider codex\` показывал **88% использовано за 5 часов, 23% за 7 дней**, сброс 5h окна — **07:09:20**; исходный deadline **12:12:27**. Это не ошибка \`403/429\`: supervisor намеренно остановил новую работу раньше полного исчерпания.

Четыре законченные Codex JSONL итерации (raw private logs остаются на PC), по полям \`turn.completed.usage\`:

| Iteration | Input tokens | Cached input | Output | Completed command outputs |
| --- | ---: | ---: | ---: | ---: |
| 1 | 796,361 | 695,552 | 8,437 | 46 start/completed records суммарно |
| 2 | 665,090 | 592,768 | 9,228 | 42 |
| 3 | 674,000 | 605,952 | 6,023 | 48 |
| 4 | 814,279 | 746,880 | 9,232 | 34 |
| **Σ** | **2,949,730** | **2,641,152 (~89.5%)** | **32,920** | — |

За четыре итерации в их инструментальных выводах присутствовало около **943 тыс. символов**, отдельные фрагменты доходили до ~42 тыс.; были признаки усечений. Эти счётчики **не** являются биллингом и не позволяют вычислить точную формулу списания % квоты. Ранние неуспешные вызовы, другие ChatGPT agentic инструменты и фоновые запросы также могли расходовать лимит.

## Детальные проверенные варианты

1. **Официальный бюджет Astra на Plus очень ограничен:** ориентир **5–45 локальных сообщений / 5 часов**; Sol 15–160, Luna 350–3000; это не гарантированное число, задача/контекст/инструменты меняют стоимость. [OpenAI Codex Pricing](https://learn.chatgpt.com/docs/pricing).
2. **CLIProxyAPI, OpenCode и другие агенты с ChatGPT OAuth не меняют upstream rate-limit pool** — они переиспользуют подписной Codex backend; поддерживаемого способа маршрутизировать автономный API/Responses вызов как обычное ChatGPT chat-сообщение **не найдено**. [Using Codex with ChatGPT](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan).
3. **Известная проблема большого контекста:** [openai/codex #40897](https://github.com/openai/codex/issues/40897) измерил 7.28M входных токенов за 16 минут из-за увеличивающегося tool context и повторных обращений; большинство было cached. У нас есть похожие *признаки*, не доказано тождество первопричины.
4. **Испытанный способ экономии без ухудшения решения:** [openai/codex #41450](https://github.com/openai/codex/issues/41450) — 50 независимых read-only проверок, тот же исходный клиент/модель/контекст, 100% покрытие. Если объединить подходящие проверки в один Code Mode \`exec\` + \`Promise.allSettled\`, outer cycles **60→15**, cumulative input **11.10M→2.04M (−81.6%)**. Это экономия конкретного исследования, **не гарантия** для web-vn.
5. **Избегать ожидания в модельном цикле:** [openai/codex #38495](https://github.com/openai/codex/issues/38495) зафиксировал многомиллионный контекст на модельных \`wait\` при долгом процессе. Host-side wait/systemd, а не частые запросы к LLM.
6. **ChatGPT Scheduled Tasks — самостоятельные запуски ChatGPT**, не тот же Codex CLI клиент. Они могут использовать доступные подключённые приложения и подходят как резервный источник небольших source-only задач. Но частота обычных задач **не более 1 в час**, а используемый модельный/аккаунтный ресурс и наличие SSH/GitHub write **нужно проверять на реальном запуске**. [Scheduled tasks help](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt).
7. **Grok OAuth** использует отдельный от Codex provider, но не бесконечную квоту: [официальный xAI FAQ](https://docs.x.ai/grok/faq) описывает общий недельный пул Chat+Build+Imagine. Ранее на аккаунте было **81% использовано**; поэтому нельзя рассчитывать на бесплатную ночь с Grok. По умолчанию локальная модель **не меняется**.
8. **GitHub Copilot Pro+** поддерживает GPT-6 Astra через свою модельную подписку/платный биллинг, а Plus/Pro Codex позволяют докупать кредиты/eligible usage reset. Это **другие платные лимиты**, не обход бесплатным «режимом чата». [GitHub announcement](https://github.blog/changelog/2026-09-04-gpt-6-astra-is-generally-available-in-github-copilot/), [OpenAI credits](https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-personal-plans).
9. Не использовать автоматизацию веб-чата, spoof OAuth/смену account identity/подмену клиентских признаков для обхода лимитов. Это ненадёжно и может противоречить [OpenAI Terms](https://openai.com/policies/row-terms-of-use/). Обсуждать легитимные альтернативы допустимо, но в production их не включать без решения владельца.

## Что сделано сейчас

- В корневом \`AGENTS.md\` и полном регламенте добавлено правило аккуратной упаковки **известно независимых read-only** вызовов в один Code Mode exec с обработкой каждого результата; зависимые/mutating операции остаются последовательными.
- В Codex night supervisor prompt добавлены инструкции по ограничению большого stdout, отсутствию бессмысленных poll, коротким summary вместо мегабайтного вывода и **никакому снижению тестового покрытия**.
- Контроллер сохраняет после каждого завершённого \`turn.completed\` агрегированные input/cached/output токены и размер tool output в приватном \`status.json\` и hourly report. Эти измерения не требуют новых LLM запросов.
- Запланированная ChatGPT Automation \`6ae4ec33db048191af03a0f0c102e8f4\` с **03:15 и далее каждый час** обновлена: если Codex \`paused_quota\`, не может восстановиться или блокирован, она должна в своём **собственном ChatGPT scheduled-сеансе** выполнять одну самостоятельную связанную с \`#20\` маленькую задачу исходников (GitHub read/write → новая ветка + draft PR при разрешённых инструментах), не трогать грязную ветку ночного Codex. Допустимы честный NOT APPLIED/NOT TESTED при отсутствии write/тестовой среды. Это **не запуск другого автономного интерактивного чата**, а отдельный ограниченный запланированный вызов.
- Таймеры на PC \`vn-night-quota-resume.timer\` и \`vn-night-watchdog.timer\` продолжают каждые 5 минут поддерживать процесс и квоту до первоначального дедлайна; локальный watchdog не расходует токены модели.

## Измерение после сброса

Не менять Astra на другую модель и не снимать QA ради скорости. Сравнить два source-only кейса похожей сложности на первой попытке: 5h/7d квоты до/после, \`input_tokens\`, \`cached_input_tokens\`, завершённые команды, output chars, фактически добавленные negative regression tests, G1 pass и G2 UNVERIFIED. Для реального image QA отдельно нужен private PNG review; нельзя переводить G2/G3 в PASS по сравнению токенов.

## Найденные неофициальные проекты для обычного ChatGPT Web (анализ, НЕ внедрено)

**Да, такие проекты существуют** — здесь важно не путать наличие публичного proof-of-concept с устойчивым и разрешённым API. Официального supported endpoint, который переносит затратные Codex autonomous tasks в квоту обычного ChatGPT Chat, по проверенной документации **нет**.

| Проект | Что заявляет автор | Проверенная зрелость на 31.10.2026 | Почему не поставлен |
| --- | --- | --- | --- |
| [leeguooooo/chatgpt-use](https://github.com/leeguooooo/chatgpt-use) | Использование залогиненного Chrome / ChatGPT Web как *planner/reviewer* и structured delegation в CLI агент; не Codex billing | Experimental v0.0.2, GitHub 56 stars, 3 open issues, последний push 09.10; автор прямо пишет, что реальные full-agent MCP сценарии не все end-to-end проверены, UI может зависать, requests могут throttling | Нельзя считать stable tool-calling API, рендер-критичные файлы всё равно требуют внешнего исполнителя; возможен конфликт с условиями сервиса |
| [Octo-Lex/ChatGPT-Web2API](https://github.com/Octo-Lex/ChatGPT-Web2API) | CDP/Chrome преобразователь реального ChatGPT Web в локальный OpenAI-compatible REST/MCP | Experimental third party, GitHub 91 stars/12 open issues, последний push 22.10; есть мок-тесты, opt-in real-browser E2E, автор признаёт UI/API drift и 429; image input пока не работает | Работа с аккаунтом через browser session, зависимость от UI, риски учётной записи/автоматического извлечения ответов и несоответствие native Codex tools и G2 review |

Это не доказательство, что ChatGPT-Web можно безлимитно использовать: у самого веб-чата есть message и request rate limits. Даже если в отдельных случаях расходуется другой product pool, такое решение не делает его безлимитным. **Автоматизированное или программное извлечение ответов и обход ограничений прямо запрещены [OpenAI Terms](https://openai.com/policies/row-terms-of-use/)**. Не запускать reverse-proxy, CDP/Chrome-cookie bridge, фальшивый conversation endpoint или перемаршрутизацию Chat OAuth на личном аккаунте без отдельного решения владельца и проверки легитимного способа использования. Не переносить эти инструменты в production, не хранить cookie в night-runner.

**Поддерживаемая альтернатива для данного задания:** существующая [ChatGPT Scheduled task](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt) выполняет отдельную source-only работу в рамках доступного продукта и его правил, когда Codex ждёт сброса. При штатном плане — **не чаще 1 раза в час**. Нельзя утверждать, что это новый автоматически запускаемый полноценный интерактивный чат или 24/7 free capacity; результаты оцениваются на реальных hourly runs.

