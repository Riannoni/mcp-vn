# Historical development notes, v3–v6.4

> ARCHIVED: records past implementations and measurements. NOT current installation instructions. Use the root README and docs/OPERATIONS.md instead.

---

# mcp-vn — визуальная новелла в ChatGPT

Личный игровой сервер с MCP Apps-интерфейсом: сцена со спрайтами, прокручиваемая история сообщений, **свободные действия игрока**, необязательные подсказки, сохранения и автоматическая генерация иллюстраций/коротких видео на RX 9070 XT.

## Архитектура

- **Домашний Ubuntu-сервер**: Docker `mcp-vn`, игровой движок, сохранения, очередь и библиотека медиа.
- **Игровой ПК Bazzite**: ComfyUI (ROCm gfx1201) и `mcp-vn-worker.service`. Воркер самостоятельно забирает задания, входящие порты на ПК не нужны.
- **VPS**: авторизованный шлюз с проверкой Auth0 JWT по адресу `https://xavoks.jo3.org/vn/mcp`. Media URLs защищены HMAC.
- **ChatGPT**: ведущий игры; MCP Apps даёт игровой интерфейс в чате.

## Поддерживаемые изображения и видео

- `anime` — WAI-Illustrious SDXL v17.
- `semireal` — CyberRealistic Pony v18.
- `realistic` — CyberRealistic Pony v18.
- `animation` — Anima BAS:NSFW v1.0 (animated illustration, not Japanese anime).
- `poster` — CyberRealistic Pony v18.
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

## Подключение к ChatGPT — важный шаг

**ZIP-плагин сам по себе не регистрирует облачное MCP-приложение.** Поэтому созданный ранее `mcp-vn Visual Novel` может отображаться как требующий десктоп, а в обычном веб-чате его инструменты недоступны.

Для веб-версии требуется **Plugins → + → Add custom MCP server** с URL `https://xavoks.jo3.org/vn/mcp` и OAuth, а затем новая беседа в **ChatGPT Work**, если эта возможность доступна в аккаунте. После подключения можно вызывать `open_game`.

Полная инструкция: [docs/CONNECT-CHATGPT.md](../CONNECT-CHATGPT.md).

Анонимный запрос к `/vn/mcp` возвращает 401 — это штатная защита. Поддержку `App.sendMessage` внутри виджета ещё требуется проверить после регистрации приложения.

## Импорт

`import_story` принимает JSON-пакеты собственных или разрешённых для переноса историй. Текущий ISEKAI ZERO MCP позволяет читать свои персонажи и сюжеты, но не скрытые промпты чужих историй из всего каталога. Генерация через ISEKAI ZERO не используется и не расходует Mana.

## Инструменты

`open_game`, `list_stories`, `list_games`, `start_game`, `get_game`, `get_game_context`, `submit_action`, `gm_continue`, `undo_last_turn`, `queue_art`, `list_art_jobs`, `import_story`.

Игры хранятся в `data/games`, сюжеты в `data/stories`, задания в `data/jobs`, изображения и видео в `data/assets`. `npm test` проверяет основной игровой цикл.

## v4: визуальная композиция и контроль качества (26.10.2026)

**Как открыть свежий UI:** после обновления подключения MCP выберите
\`open_game_v4(game_id="...")\` или \`open_game_latest\`. URI нового ресурса —
\`ui://mcp-vn/visual-novel-v4.html\`. Прежние UI-ресурсы сохранены для
обратной совместимости, но в ChatGPT старый инструмент может быть закеширован.

В игровом интерфейсе доступны «✦ CG-сцена», «▧ Фон», «♙ Персонажи» и «▶ Видео».
Предпочтительный стиль нового арта — \`realistic\` (Lustify SDXL v2.0).
Каждая сцена имеет **один background**, на котором отображаются прозрачные PNG
персонажей (layered mode). В режиме CG выполняется inpainting исходного
background средствами ComfyUI и показывается цельный кадр; исходный фон и
спрайты не перезаписываются, переключение режимов доступно в интерфейсе.

### Путь от запроса до готового арта

1. MCP \`queue_art\` фиксирует локацию, исходный фоновый ассет, текущие
   изображения персонажей, параметры художественного стиля и разрешение;
   сохраняет \`spec_version=4\` в задании.
2. Worker сам извлекает референс фонового изображения через защищённый
   \`GET /worker/asset/{uuid}.png\`; изображение никогда не требуется
   загружать через внешние облачные API.
3. Для спрайтов генератор использует фон текущей сцены как указание по цвету
   и свету, а предыдущий спрайт того же персонажа в том же стиле — как
   условный img2img-референс. ISNet (\`rembg\`) удаляет собственный задник
   спрайта, результат проходит цветовую коррекцию и сохраняется с RGBA.
4. Для CG ComfyUI получает существующий фон и маску области персонажей,
   выполняет \`InpaintModelConditioning\` и сохраняет неперерисованную
   часть изображения. Согласованность лица в CG не гарантируется;
   для сложных композиций потребуется отдельный identity-conditioning узел.
5. Worker проверяет тип файла, геометрию, границы объекта, наличие прозрачности
   и статистику альфа-канала. Локальная CPU-модель
   \`HuggingFaceTB/SmolVLM2-500M-Video-Instruct\` при включении пытается
   распознать очевидные расхождения: отсутствующий или лишний персонаж,
   явная ошибка с одеждой. Проверка учитывает ошибки модели и предназначена
   для грубых несоответствий, **не гарантирует** художественной корректности.
   Русскоязычные текстовые описания персонажей дополнительно разбираются
   на важнейшие англоязычные признаки внешности для SDXL (тип одежды,
   цвет, причёска, особые детали). Неуверенное несовпадение палитры
   записывается как \`qa.warnings\`, а не как доказанная ошибка.
6. Только после \`POST /worker/qa/{job_id}\` со статусом passed сервер
   принимает файл через \`POST /worker/complete/{job_id}\` и независимо
   проверяет фактические пиксели альфа-канала PNG. Неуспешные проверки
   повторяются максимум три раза; последний принятый ассет не заменяется.
7. Перед публикацией результат сопоставляется с локацией и ID текущего
   фона. Задания, сгенерированные для уже сменившейся сцены, сохраняются
   как результат job, но не устанавливаются в активную игру.

### Развёртывание

Из \`/opt/mcp-vn\` на домашнем сервере:

\`\`\`bash
docker compose build
docker compose up -d --no-deps game
docker compose ps
curl -fsS http://192.168.50.29:3100/healthz
\`\`\`

Worker на игровом ПК \`xavok-pc\` использует файлы
\`~/.local/share/mcp-vn/{worker.py,vision_qa.py}\`, venv
\`~/.local/share/mcp-vn/venv\` и systemd \`mcp-vn-worker.service\`.
Он обращается к ComfyUI на \`127.0.0.1:8188\` (ROCm, AMD RX 9070 XT).
Для быстрой диагностики:

\`\`\`bash
systemctl --user status mcp-vn-worker.service
journalctl --user -u mcp-vn-worker.service -n 60 --no-pager
\`\`\`

Переменная \`VN_VISION_QA=0\` в конфигурации worker отключает только
**семантическую** проверку: alpha/geometry и публикационные проверки
остаются активными. По умолчанию CPU-VLM включена; не требует отправки
изображений сторонним службам. При её недоступности статус
\`semantic_status: unavailable\` показывается как ограничение, а не
как доказанное соответствие арта промпту.

**Ограничения:** отделение фона может повреждать тонкие детали (волосы,
полупрозрачную ткань). Отдельно сгенерированные спрайты, несмотря на
выравнивание освещения, не всегда точно совпадают по перспективе;
для важных сюжетных моментов используйте CG. Композиция сцен с
несколькими NPC основана на масках и может потребовать ручной коррекции.

## v5: стабильные лица, правильные локации, быстрый CPU/GPU конвейер

### Почему не будет комнаты вместо рыночной площади

\`src/environment.mjs\` выводит тип окружения из названия сцены
или использует явный \`scene.environment={id,positive,negative,indoor}\`.
Для открытой рыночной площади принудительно формируется SDXL-промпт
\`outdoor_market_square\` с открытым небом, прилавками, фасадами и мощными
негативными ограничениями на интерьер. Текст локации и тип среды
проверяются независимо от физической корректности PNG.

Постоянный CPU QA-сервис \`worker/vision_daemon.py\` на игровом ПК использует
CLIP ViT-B/32 для быстрой классификации среды. При очевидной ошибке
(outdoor -> interior) арт отклоняется без медленного вызова SmolVLM.
Для неопределённых случаев и базовых персонажей используется подробная
VLM. Несоответствие среды не заменяет последний принятый background.
Сервис доступен только на \`127.0.0.1:9312\` и не использует внешние API.

### Постоянные образы персонажей

В каждом сохранении есть \`identities[name]\`: первый принятый
прозрачный PNG навсегда становится \`base_sprite_url\`, а из области
головы выделяется \`face_url\`. Новые наряды, эмоции и позы добавляются
в \`variants\`, не заменяя канон. Существующие v4 спрайты мигрируются
через \`ensure_character_anchors(game_id)\` без перерисовки лица.

На Bazzite установлен ComfyUI_IPAdapter_plus (upstream cubiq, commit
\`a0f451a\`) и модели SDXL Plus Face / CLIP-ViT-H. Новая генерация
с референсом лица использует IPAdapterAdvanced 0.78, а полный базовый
спрайт — img2img опору для тела и стиля. Если IPAdapter недоступен,
worker может откатиться на стандартный img2img. Визуальная QA измеряет
CLIP face similarity; ниже 0.75 — отклонение, 0.75–0.84 — предупреждение.
Это не биометрическая гарантия, но позволяет выявлять очевидный drift.

\`queue_art\` принимает \`outfit,pose,emotion,force,quality,priority\`.
Точная повторная комбинация возвращается из кэша без генерации,
если не указан \`force=true\`. UI v5 автоматически запрашивает отсутствующий
фон, а затем первые identity-anchored спрайты после очередного хода.
Изменение одежды/позы запускает новую вариацию с сохранением базового лица;
готовое старое изображение остаётся на экране до принятия нового.

### CG без потери персонажей

Кнопка CG отправляет CPU-задание на \`worker/scene_compositor.py\`.
Оно включает точно тех персонажей, чьи **принятые альфа-спрайты**
находятся в текущей сцене; каждый берётся из текущего ассета, без
перерисовки лиц. Фон и перспектива остаются прежними; композитор
масштабирует фигуры и создаёт мягкие тени. Успешный CG отображается
отдельно от layered-режима, и можно возвращаться к слоям.
Для CG больше не требуется расходовать GPU на генерацию людей заново.
Возможен дальнейший опциональный художественный inpaint только вокруг
теней/контактов, без изменения канонических лиц.

### Параллелизм и измерение времени

- GPU: один поток SDXL/Wan, чтобы не создавать VRAM thrash на 16 GB.
- CPU: отдельный пул до \`VN_CPU_WORKERS=2\` на игровом ПК,
  удаление фона ISNet, постобработка и CG.
- CPU VLM: постоянный отдельный сервис с CLIP и SmolVLM,
  \`VN_VISION_THREADS=5\`; модель не перезагружается на каждый арт.
- Передача CPU-постобработки в executor не блокирует GPU:
  следующий ComfyUI job может выполняться во время проверки предыдущего.
- Очереди отделены \`GET /worker/next?pool=gpu|cpu\` и приоритетом 0–100.
- В ComfyUI polling по умолчанию 1 сек вместо 4 сек.
- У каждого job есть \`stage\` и \`timings\`: queue_wait_ms,
  generation_ms, postprocess_ms, qa_ms, publish_ms, total_ms.

Параметр качества \`fast\` уменьшает steps и запускает только
обязательные проверки; \`standard\` сохраняет базовые 28 SDXL steps;
\`cinematic\` повышает количество steps и усиливает VLM QA.
Если проверка возвращает ошибку, файл не заменяет принятый;
повторных попыток не больше 2–3. Публикация также проверяет
неизменность локации, фона и состава спрайтов CG.

Внутренняя сеть: сервер \`/opt/mcp-vn\`, порт 3100 (авторизация worker),
игровой ПК \`xavok-pc\`, ComfyUI \`127.0.0.1:8188\`, QA
\`127.0.0.1:9312\`. Данные истории находятся отдельно в \`data/\`
и исключены из Git. Полная предрелизная копия v5 находится в
\`/opt/mcp-vn-backups/pre-v5-20261026T172024Z.tgz\`.

### Минимальные команды диагностики

\`\`\`bash
# Ubuntu home server
cd /opt/mcp-vn
docker compose ps
docker compose build
docker compose up -d --no-deps game
docker logs --tail 50 mcp-vn

# Gaming PC
systemctl --user status mcp-vn-worker mcp-vn-vision mcp-vn-comfy
curl -s http://127.0.0.1:9312/healthz
curl -s http://127.0.0.1:8188/system_stats
journalctl --user -u mcp-vn-worker -n 60 --no-pager
\`\`\`

Для обновления UI используйте новый инструмент
\`open_game_v5(game_id="...")\` и ресурс
\`ui://mcp-vn/visual-novel-v5.html\`; если кэш ChatGPT не обновился,
обновите подключение MCP-плагина.

## v5.1 — desired/rendered state and adaptive stage

Character narration and the accepted PNG are tracked separately in
\`src/visual-state.mjs\`. A character keeps \`desired_variant_key\` for
the requested costume, pose, emotion and style, and
\`rendered_variant_key\` plus \`rendered_background_asset\` for the
actually displayed asset. If these differ, \`visual_dirty=true\`;
the UI retains the previous PNG until the next one passes QA.

The scheduler avoids duplicate jobs and refuses to apply a late
result that no longer matches the requested character state. Cached
variants are reused only with the matching background. CG cannot
be queued or shown while characters are stale, and is invalidated
by subsequent changes to the artwork or background.

The artwork pipeline uses a separate non-erotic fine-art wardrobe
description for unclothed adult characters. The canonical identity
description no longer injects a conflicting old costume. The local
VLM verifies that the resulting image actually meets the requested
wardrobe state before accepting it, or reports a QA failure.

Desktop scene sizing fills the usable vertical area; character
scale and CG composition use more of the frame. On narrow layouts,
the stage retains the 16:9 aspect ratio.

New UI: \`ui://mcp-vn/visual-novel-v51.html\` via
\`open_game_v51\`. Legacy resources remain available.
Pre-release backup: /opt/mcp-vn-backups/pre-visual-state-v51-20261026T184040Z.tgz.

### Validation findings from the October 27 smoke tests

- Previously accepted art could describe an outfit in metadata while visibly
  showing older clothing. A legacy PNG does not become valid merely because its
  filename exists; v5.1 treats unknown background provenance as stale.
- The SmolVLM judge must recognise factual negative-wardrobe captions including
  \`no visible garments\` and \`no clothes visible\`, not only the word \`nude\`.
  Clearly detected clothing is rejected, while a failure leaves the old
  sprite in place with a visible stale indicator.
- Large wardrobe changes cannot reliably use low-denoise img2img against
  an old clothed base: it copies the old fabric. For the art-study
  \`unclothed\` variant, the GPU worker uses a fresh latent and
  keeps identity conditioning through the canonical IP-Adapter face.
- The manual **Characters** control first targets only visually outdated
  characters. When all are already current, it can regenerate everyone.

## v5.2 (October 2026) — one style per playthrough, previews and traceable latency

**Styling contract:** new games accept `art_style` in `start_game` (realistic,
semireal, anime, poster). It is immutable for that save. Every queue_art call
inherits the game style; an incompatible explicitly supplied style is rejected.
The in-game selector has been removed. Older saves are migrated once at server
boot: the earliest accepted image in the game establishes the original style.
Only if no historical artwork exists do identity anchor and active sprite styles
serve as a fallback, protecting the style in which a game originally started.
A background from a mismatched past style remains visible while a new
matching background is generated; meanwhile its CG is invalidated. Only a
brand-new save can select another style. There are no style-dependent identity
similarity thresholds.

**Queue and time accounting:** every attempt is an independent record containing
claim and finish timestamps, stage timings, retry outcome, and queue wait.
`timings` provides cumulative initial `queue_wait_ms`, `retry_wait_ms`,
`prepare_ms`, `generation_ms` (ComfyUI wall time), `compose_ms` (CG CPU),
`cpu_wait_ms`, `postprocess_ms`, `qa_ms`, `publish_ms`, and `other_ms`.
The sum of reported stages, including other (signed if clocks overlap), matches
`total_ms`. `attempt_history` explains repeated retries and is visible in the
job's tooltip. Historic jobs may not have the new breakdown; the UI labels
unaccounted time as `прочее`, rather than implying it is GPU work.

Duplicate requests are folded into an existing queued/working job. A different
request for the same target supersedes waiting jobs; an already-running GPU
render may finish, but a superseded result is not attached. Queued jobs are
checked against current game style, location, background and requested visual
state before being handed to workers. CG waits for a stable, current background
and completed sprites. The client debounces automatic image requests to avoid
repeated jobs while the narrator changes several attributes in one turn.

**Preview:** `queue_art(preview_only=true,quality='fast')` supports backgrounds
and sprites at reduced resolutions (896x512 / 640x960). The accepted output is
stored as a preview job and can be opened separately, but never replaces the
canonical scene image, character anchor or CG. The game view has an `Эскиз`
button. Production final renders continue to use standard/cinematic quality.

**Quality/throughput:** the worker distinguishes prompt+reference preparation
from the ComfyUI wall time. CPU deterministic anchored CG does not repeat a
long VLM description by default: the already-approved sprites and background
are unchanged, so rapid CLIP environment validation is sufficient unless
`quality=cinematic`. First-time character identity generation and substantial
outfit changes still receive stricter visual checking. Keep GPU concurrency=1,
CPU workers=2, and maintain the vision daemon hot in RAM.

**Upstream design inspiration:** Ren'Py's layered image attributes and per-layer
scene operations (`renpy.org/doc/html/layeredimage.html`), Dialogic's named
character portraits and timelines (`dialogic.pro` / `dialogic-godot`), and
Monogatari's separation of game variables, script, assets and preloaders
(`monogatari.io/v2`). These ideas are incorporated selectively, without
replacing the existing MCP and ComfyUI system.

New UI key: `ui://mcp-vn/visual-novel-v52.html`, tool `open_game_v52`.

## v5.3 Living-world story memory

- `src/story-memory.mjs` keeps bounded, file-backed world/character facts,
  NPC notes, active/completed quest states, event ledger, and 20-message chapter
  drafts. Completed groups of chapters form larger story arcs. All records are
  saved inside the existing game's JSON; no external vector database required.
- The narrator can include a `memory_updates` object in `gm_continue`
  to explicitly persist verified facts, player commitments, quests, and notes.
  The server rejects malformed entries and caps collection lengths.
- `get_game_context` includes relevant facts/notes/quests and recent
  events based on the current speaker, location, and player action. The original
  transcript remains the source of truth; automatically generated chapter
  summaries remain labelled drafts until explicitly confirmed.
- `update_story_memory` and `get_story_memory` expose narrative memory
  as MCP tools. The UI has a 'Память' search window for facts, quests and
  chapter summaries.
- `get_game_updates` returns an empty delta when the scene/version has not
  changed. This reduces retransmission and redraw of the complete dialogue log
  during idle polling, while preserving the established authenticated MCP API.
- Old saves get a one-time, idempotent backfill of transcript-derived actions,
  events and chapter drafts. No historic facts or relationship changes are
  invented. The backfill never changes player actions, artwork or story flags.
- Character art, fixed game style, ComfyUI generation/QA and the legacy game
  tools remain compatible. UI tool: `open_game_v53` (new resource key).

Upstream inspiration: source-indexed lore/quest memory and AI agent separation
used by openovel/SillyTavern; stream-friendly event-oriented UI patterns
from Storyloom; character/costume variant caching as in VNCCS. External source
files have **not** been copied into this project; implementation is original.

### Optional game rules and scene revisit cache

The default narrative mode keeps open-ended player agency and no dice. New games
can opt into `adventure` mode; the GM may call `resolve_skill_check` on a pending
player action. The backend rolls a cryptographically sourced d20 (with optional
advantage/disadvantage), applies the character stat, enforces a difficulty range
and saves the result to `rules.history`. The narrator must not invent the roll.
`set_rules_mode` can switch a save without removing history. No skill roll is
allowed unless a player action is pending, and narrative mode rejects them.

`src/scene-cache.mjs` indexes accepted backgrounds by locked style + normalized
location + time_of_day + weather. A revisit can restore the original background
without ComfyUI; different weather or lighting gets its own asset. Existing
sprites are still checked against that background before publication. The
cache is bounded to 65 entries per game, and storyboard/CG renderers keep their
existing verified composition contract.

Potential follow-up graphics upgrade: benchmark VNCCS/CharacterPose in a
separate isolated ComfyUI workflow before attempting any deployment. Never copy
third-party code without reviewing its license and compatibility with our
existing IP-Adapter plus face anchors. No external generators are installed by
this release.

## v5.3 — Living world, actor packs and location prefetch (October 2026)

- Durable story memory in the game JSON: transcript-grounded events, bounded
  20-message chapter summaries, multi-chapter arcs, facts with provenance and
  revision history, live quests, character/place notes, relevance-triggered recall.
  GM uses get_game_context / update_story_memory / memory_updates in gm_continue.
  Existing saves receive strictly transcript-based backfill at startup.
- Optional adventure mode records cryptographic d20 skill checks and validated
  outcomes. Narrative freeplay stays the default for old and new games.
- Background cache keyed by game style, location, time and weather. A return visit
  can reuse accepted scenery. warm_next_locations optionally prepares two known
  future areas at low GPU priority without moving the player.
- warm_character_variants creates low-priority expression alternatives using the
  canonical identity pack; accepted variants are stored without changing the
  currently visible sprite. The scene can reuse matching cached images instantly.
- Pose presets use geometric language and avoid contradictory standing prompts;
  canonical IPAdapter facial conditioning remains active through changed poses.
- get_live_updates returns only changed game state and changed media-job status,
  while the UI appends new transcript messages instead of recreating all rows.
- Upstream concepts reviewed: Storyloom (MIT), openovel (Apache-2.0), Gamentic
  (MIT), SillyTavern World Info (AGPL), VNCCS and CharacterPose (MIT).
  TaleWeaver is not approved for unrestricted commercial code reuse.
  No third-party implementation was pasted into this codebase.
  VNCCS and CharacterPose repositories were cloned to an isolated research
  directory on the gaming PC, without installing extra models or nodes into
  the production ComfyUI workflow.

The existing SSH-MCP, user saves, identity anchors and game-wide locked art
styles remain supported.

## v5.4 — low-latency MCP events and validated pose control (October 2026)

### Live UI event delivery

An in-memory, per-game event bus in `src/live-events.mjs` produces tiny `game`
and `job` events after an atomic JSON save. The new authenticated MCP tool
`wait_for_game_events(game_id,boot_id,after_seq,wait_ms)` waits up to 12 seconds
rather than continuously transmitting the entire game. Cursors include a
server boot UUID and reset cleanly on reconnect. The v5.4 app subscribes with
one outstanding call per active game and uses fallback polling every 15 seconds
only if the host cannot keep the wait call active. In direct concurrent MCP
integration testing a game-action event was delivered after ~136 ms including
network/RPC overhead versus the previous fixed 2.2-second poll. This does NOT
stream individual language-model tokens; it streams state and art progress.
No event endpoint is publicly exposed without MCP authorization.

### ControlNet / CharacterPose A/B and safety boundaries

- Upstream experimental sources fetched under `~/.local/share/mcp-vn-lab/`:
  `Spit8/_ComfyUI_CharacterPose` commit `cfb735e` (MIT), and
  `AHEKOT/ComfyUI_VNCCS` commit `4414e3d` (MIT). No upstream package is
  installed as a production ComfyUI custom node; existing workflows remain
  untouched. CharacterPose CPU smoke tests passed in a disposable Podman
  container. Four sample Mixamo FBX clips were converted into 52 COCO-18 pose
  guides in ~0.14s in the disposable container, with zero failed imports.
- Apache-2.0 model `xinsir/controlnet-openpose-sdxl-1.0` downloaded to
  `~/.local/share/mcp-vn-comfy/models/controlnet/xinsir-openpose-sdxl-1.0.safetensors`
  on `xavok-pc` (2,502,139,104 bytes, verified SHA256
  `b8524e557a7df60d081f5d4a0eb109967d107df217943bf88c2d99b9ebcc06c5`).
- With identical seed and reference face, running full-body prompt: baseline
  DreamShaperXL Turbo ~7.0s vs ControlNet ~7.0s, with face CLIP similarity
  0.9007 vs 0.9057. The base model largely ignored movement and cropped feet;
  OpenPose constrained the posture and included the full body. A second
  kneeling benchmark showed clearer body framing, without establishing
  reliable literal crawling. A hand-drawn leaning-forward guide did *not*
  reliably produce the desired waist bend, so this pose is explicitly NOT
  included in ControlNet rules.
- Production `worker/pose_presets.py` maps only *verified* action keys:
  `running`, `running_fast` to `running.png`, and `kneeling` to `kneeling.png`.
  Curated local guides are in `~/.local/share/mcp-vn/pose-guides/` on the PC.
  They are privately generated pose-guide data, not an upstream code vendoring.
  `worker.py` loads these as ControlNet images only when the sprite requests
  an exact supported pose. It continues to use IPAdapter for the canonical
  face. Missing guide, missing model, or known ControlNet/OOM failure follows
  an existing fallback path; other poses retain prompt-only generation.
  Set `VN_POSE_CONTROL=0` in worker service environment to disable the new
  guidance immediately (restart only worker, not ComfyUI).
- Production integration smoke: `running` preview ~8.86s, face similarity
  0.8932; `kneeling` preview ~9.25s, face similarity 0.9124. Both passed QA,
  and `preview_only=true` prevented either result from changing the game.
- `VNCCS` latest 3.3 workflows were examined separately. All main custom-node
  classes are absent from the existing ComfyUI instance, and its preferred
  generative paths introduce different heavyweight Qwen/Flux models. Since the
  existing identity/reference and pre-warmed outfit/emotion library already
  supports our core requirements, full VNCCS installation was deliberately
  deferred. Do not claim its complete workflow was tested or deployed.

### Pre-warmed expressions

`warm_character_variants` provides reusable, low-priority emotion variants
without replacing active sprites. On the existing Tirren save, canonical
Max Crow `smile` and `concerned` variants passed QA and were stored in the
sprite cache; the visible expression remained neutral. Runtime totals were
9.85s and 17.39s (the latter included GPU queue wait). These cached variants
can be selected later without fresh generation when background and style match.

The `open_game_v54` tool uses `ui://mcp-vn/visual-novel-v54.html` as a new
cache key. Existing saves, memory and the base v5.3 tools remain compatible.
Development/lab reports and temporary previews have been archived in
`/opt/mcp-vn-backups/v54-integration-lab-20261026T212406Z/` rather than
cluttering the live game's job list. The pre-upgrade source/data backup is
`/opt/mcp-vn-backups/pre-v54-20261026T211732Z.tgz`.

## v5.5 — compact narrator context and measurable story latency

The game stores its full canonical JSON and narration history as before, but
no longer transmits art-pipeline debug history to the AI narrator by default.
Earlier, `get_game_context` on a mature save returned ~287 KB, ~242 KB of
which was unrelated image job metadata. `src/narration-packet.mjs` builds a
bounded, authoritative `mcp-vn/narrator-packet-v1` with the *current user
submission*, story premise, consistent hero/NPC traits, location and visual
state, inventory, flags, relationship state, active quests, pertinent canon
facts, recent chapter abstracts and the last dialogue. It omits image URLs,
QA diagnostics, old prompts, jobs, and undo snapshots. The narrator can still
request `get_game_context(detail="full")` if a genuinely complex continuity
question needs it.

For the v5.5 UI:

1. `submit_action_fast` validates and atomically persists the player's free
   text, then returns the acknowledged message and the same compact narration
   packet. The front-end adds the acknowledged message optimistically; it
   does **not** send the action twice.
2. The ChatGPT host receives a single user message embedding the compact
   packet, with instructions to use existing canon facts, write 2–4
   meaningful narrative segments and commit them with one `gm_continue_fast`
   tool call. A second `get_game_context` tool call is normally unnecessary.
   The narrator does not call `queue_art` during ordinary scene transitions:
   client-side visual jobs start from accepted state changes asynchronously.
3. `gm_continue_fast` uses the same validated input as legacy `gm_continue`
   but responds with a small commit acknowledgement instead of the complete
   game history. Older plugins/tools retain compatibility.
4. `get_live_delta` supplies only new messages and current mutable scene
   fields, plus compact image job updates. Unknown or outdated message
   cursors trigger a full game refresh (undo is safe). The full game is only
   needed for initial opening and cursor recovery.
5. `get_turn_performance` exposes the actual wall time measured between
   accepted player actions and saved narrator messages, plus the v5.5
   per-turn telemetry. The UI shows an elapsed waiting timer and the previous
   round trip / server commit duration. It does **not** claim to measure pure
   ChatGPT neural inference time, which the MCP server cannot observe.

Real-save pre-deployment measurements (47 messages, v5.4): `game` ~318 KB;
`get_game_context` ~287 KB; job list ~242 KB. In the v5.5 test build the
narration packet was ~13.1 KB, normal game delta ~9.5 KB, and compact job
summaries ~23 KB. The size reductions do not directly predict LLM token
throughput; ChatGPT latency can also depend on the selected model, thinking
effort, current chat history and host orchestration. Game/UI code cannot
change the ChatGPT model selection itself. A fresh ChatGPT conversation may
help if an extremely long prior chat is contributing to latency; the game
save remains server-side and can be reopened by its immutable game ID.

The HTTP status and MPL/App plugin resource are versioned as v5.5;
`open_game_v55` is the new cache-busting entry point. No user save is reset,
no new TTS/voice components are installed, and ComfyUI/generation workers are
left unchanged.

## v5.6 — diagnose narrative delay by stage (2026-10-27)

The AI host / model inference process is opaque to the VN server.
Previous live-save round trips were about 48s, 74s, and 78s,
while the server game commit took 5–13ms. We cannot attribute all
remaining time to pure model inference without platform telemetry.

v5.6 writes a privacy-minimal, per-game sidecar with action IDs, phase names,
absolute timestamps and numeric elapsed times to the private directory
data/turn-traces/<game_uuid>.jsonl (no text, image data, tokens or secrets).
This telemetry does not change game state, version or dialogue.

Stage boundaries:
1. Browser measures submit_action_fast RPC duration using performance.now.
2. Browser calls ui/message (App.sendMessage) and measures the host ACK.
   According to MCP Apps, ACK is for message acceptance; it is not the end
   of language-model generation.
3. gm_continue_fast (and legacy gm_continue) logs entry at the server and
   successful commit; both timestamps use the same server clock.
4. The browser logs when the completed continuation is rendered. Delivery
   is best effort and can be unreported if the tab or host session closes.
5. get_turn_trace provides the last stages. The visual novel's
   «Задержка» button presents 9 recent turn traces.

action_to_gm_call_ms = action saved to beginning of GM tool invocation.
This includes host scheduling, model reasoning/generation, tool selection
and remote transport. It is NOT pure model inference time.
gm_tool_processing_ms = actual MCP tool execution and save on the server.
host_ack_ms is a client monotonic elapsed time, not a raw host wall clock.
UI delivery is measured from saved continuation to client telemetry arrival.

Real authenticated MCP smoke (no LLM involved):
- submit_action_fast ~10ms
- diagnostic report ~39ms
- gm_continue_fast with supplied text ~14ms
- post-render telemetry ~11ms
- full action-to-GM-save ~57ms.
These are protocol baselines only, not expected ChatGPT speed.

After refreshing the connector and opening open_game_v56, play 3 turns and
inspect «Задержка». If host ACK is quick but GM invocation arrives after
60–90 sec, the dominant wait is upstream of the server, usually ChatGPT/
platform work. Compare Instant versus higher thinking efforts where
available, and/or a new chat with the same saved game. ComfyUI rendering
runs separately and is unrelated to this narrative delay.

## v5.8 Local scene improvements

The optional on-device narrator uses role-separated compact local history,
scoped memory retrieval, a stricter agency/grammar validator, and complete
non-graphic replies (660-token cap instead of the previous 320 cap).
Local CG is no longer a repeated deterministic collage or unanchored
multi-person diffusion that can swap identities. Its source material is now
two independent accepted character preview sprites generated by ComfyUI
under locked facial identity and VLM QA; the CPU compositor produces a
private, noncanonical combined image after both jobs finish. The UI has shot
and costume presets and a working hide/show CG control. Neither the
preview sprites nor CG ever modify main-story wardrobe, scene CG, lore,
inventory or the saved ChatGPT transcript. See docs/local-romance-lane-v57.md.

## v5.9 AI-directed local scenes

The v5.9 private-episode dialogue commits first and triggers a separate
asynchronous local JSON-based visual director that uses the actual accepted
NPC outcome to select pose, mood and safe wardrobe without requiring a
manual shot selection. Only meaningful changed frames are queued. Preview
CGs are constructed from separately identity-validated transparent sprite
variants; the client's left stage displays them during the local episode,
while a secondary chat image is collapsible and manual shot overrides are
optional. Main scene sprites/background/CG, story messages and facts remain
unchanged. Explicit sexual CG requests return an honest unsupported notice.
See docs/local-romance-lane-v57.md.

## v6.0 Dynamic private visual scene

The new local visual-state contract uses independent freeform text
for wardrobe, equipment, pose, expression, action, setting and camera.
Local CG is GPU diffusion, not CPU sprite assembly. Optional local
video uses an accepted local still as the Wan2.2 start frame and
does not modify the canonical story. See docs/local-romance-lane-v57.md.

## v6.1 visual grounding

A complete neural CG is not automatically a correct scene. Independent CLIP
verification checks expected principal-person count and known scene location.
The small VLM's generic captions are not trusted as count evidence. Wrong
frames cannot silently seed subsequent CGs or opt-in videos. Technical QA is
kept separate from story narration and model content. New cache-key tool:
open_game_v61. See docs/scene-grounding-v61.md.

## v6.2 — stronger private CG and visual consistency

- The private local-CG lane uses the author's CyberRealistic Pony v18 F16
  SDXL checkpoint only through the GPU-worker systemd override:
  VN_LOCAL_CG_CHECKPOINT=CyberRealisticPony_V18.0_F16.safetensors.
  Canonical sprites/backgrounds and other checkpoints remain unchanged.
  Upstream: https://huggingface.co/cyberdelia/CyberRealisticPony
  Model SHA256: 1d580c1c3f3612fa4db88af65372255582d5509ca0b28f85387273368301941b.
- The specialist CG model uses DPM++ 2M / Karras, 32 steps, CFG 5,
  CLIP skip 2. Existing image models and style lock are preserved.
- The local Qwen visual director now reconciles confirmed narrative events,
  clothing, posture and action. Obvious mismatches cause a second plan
  request. Unresolved mismatches show a warning and do not silently queue
  an incompatible image.
- Local_scene_replan and the "Пересогласовать сцену" UI button rebuild
  the final visual beat WITHOUT submitting a new player turn, changing
  the transcript or altering canonical game memory.
- An independent CLIP image/text contrast score distinguishes the requested
  action from a generic static portrait as an ADVISORY signal. It is
  not proof of precise anatomy, body contact or garment arrangement.
  Individual count and location QA remain mandatory for image reuse.
- Neutral two-person benchmark (a map hand-off, different body poses):
  model generated 1024x768 in 14.5 seconds with QA confirming two people
  and location. Advisory action-vs-static contrast score was 0.89.
  This does not guarantee correct depictions of every possible interaction.
- Rollback on PC: remove only
  ~/.config/systemd/user/mcp-vn-worker.service.d/30-local-cg-model.conf
  then run systemctl --user daemon-reload and
  systemctl --user restart mcp-vn-worker.service.
  Checkpoint files and timestamped code backups are retained.


## Historical: early 2026-10-28 canonical art checkpoint migration

The user removed six older image models. Canonical novel art styles now map
to installed, tested checkpoint files:

- anime = Animagine XL 4.0 (unchanged)
- semireal = CyberRealistic Pony v18 (formerly DreamShaperXL)
- realistic = Lustify SDXL v2.0 (formerly RealVisXL)
- poster = Lustify SDXL v2.0 (formerly Juggernaut XL v9)

Private local CG retains its separate CyberRealistic Pony override.
Existing approved PNGs, saved-game art style names, character identity
anchors, scenes and story memory are unchanged. New assets may be visually
different from earlier checkpoint outputs; do not claim that new checkpoint
outputs exactly reproduce the prior visual look.

Model Lab's model list now includes only CyberRealistic Pony, Anima BAS:NSFW,
CyberRealistic Z-Image Q8, Lustify SDXL and WAI-Illustrious v17. A separate
text dialogue panel exposes Qwen3.5 9B and Cydonia 24B for comparison.
Qwen remains the canonical local narrator until changed explicitly.
After two kernel-level AMD Vulkan compute queue resets, KoboldCpp uses
CPU-only as a safe fallback for both language models. It does not affect
the existing ROCm ComfyUI worker's GPU image-generation path.


## v6.3 — separate realistic, anime and animation engines (2026-10-28)

The current visual novel has five locked art-style values and three distinct
model families. The exact mapping is shared by the game image job queue and
the real on-device ComfyUI worker:

| New/saved game style | Renderer |
| --- | --- |
| realistic | CyberRealistic Pony v18 (SDXL/Pony) |
| semireal | CyberRealistic Pony v18 (SDXL/Pony) |
| anime | WAI-Illustrious XL v17 (SDXL/Illustrious) |
| animation | Anima BAS:NSFW v1.0 (UNET + Qwen3 0.6B + Qwen Image VAE) |
| poster | CyberRealistic Pony v18 (SDXL/Pony) |

The new animation style is a distinct selectable art style, NOT an alias for
anime. The separate private CG engine now applies the CyberRealistic Pony
override ONLY to realistic / semireal / poster games. Japanese anime games
render native WAI CG, while animation games render native Anima CG with their
own model, text encoder and VAE, following the eight-step Anima sampling
configuration.

Native neutral render tests passed for all three engines (768x768), including
two-character local CG tests for WAI and Anima. WAI can use SDXL CLIP skip 2,
regional IPAdapter and SDXL OpenPose ControlNet. The SDXL-only IPAdapter,
ControlNet and scene inpainting nodes MUST NOT be used with Anima; it renders
whole-scene composition using the Anima pipeline. That difference means
fine-grained character identity can drift more with new animation frames.

The latest CyberRealistic Pony mainline is v18.0 CoreShift according to the
creator index and Hugging Face repository as of 2026-10-28. CyberRealistic
Pony Semi-Realistic v6 is a separate branch, not a newer v18 successor.
No speculative replacement checkpoint was downloaded.

Lustify SDXL v2.0 was deleted after all game and Model Lab references were
migrated and all GPU queues were idle. CyberRealistic Z-Image Turbo v4 Q8 is
NOT a default renderer; it remains optional in Model Lab for comparison.
Existing saved game art-style values and all published visual assets remain
unchanged; newly rendered backgrounds and sprites may differ from old
checkpoint results. To choose the new animation style, START A NEW GAME:
existing story styles are intentionally locked.

The v6.3 tool/UI cache key is visual-novel-v63.html / open_game_v63;
previous resource keys remain available for older cached clients.

## Local LLM acceleration (2026-10-28)

The on-demand KoboldCpp gateway now prefers a verified ROCm/HIP build
rather than the crash-prone AMD Vulkan backend. Qwen3.5 9B and optional
Cydonia 24B passed GPU inference, with a CPU fallback for each model.
Qwen remains the default local story model; the main story is not
switched to Cydonia. Model Lab reports the actual backend and speed.
Detailed GPU settings, tests and CPU rollback: docs/LOCAL-LLM-ROCM.md


## v6.4 selective rendering and Cydonia private narrator (2026-10-28)

The local VN now has deterministic explainable visual routing: reuse an
unchanged frame, render only the changed dialogue sprite(s), or generate a
full-frame CG when scene pose, wardrobe, action or location materially
changes. New CG does not require independent duplicate sprite preview
renders. Approved preview sprites and CG frames have persisted signature
caches in the local scene sidecar. The existing character anchors,
scene/location cache and game save are unchanged.

New private CG defaults to portrait 896x1152 (verified on RX 9070 XT);
the UI uses fit/contain with an optional crop/fill toggle. Small left/right
sprite moves are implemented as DOM repositioning without GPU work.
The image worker has a capped 128 MiB immutable byte-reference RAM cache.
Cydonia 24B is the PRIVATE local narrator; Qwen3.5 9B remains the visual
director and text fallback. The main story still runs through ChatGPT.

Source code, timing measurements, QA limitations, the v6.3→v6.4
sidecar migration and safe rollback are documented in
docs/RENDER-POLICY-v64.md.
