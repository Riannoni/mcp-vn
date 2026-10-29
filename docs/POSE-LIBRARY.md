# OpenPose v2 — catalogue of 33 editable poses

The canonical pose coordinates and renderer live in `worker/pose_library.py`.
Run `python3 worker/pose_library.py --output ~/.local/share/mcp-vn/pose-guides-v2`
on the gaming PC (Pillow required). This generates:

- `cg/<pose>.png` at 1216×704 for story CGs, with a black background and standard coloured COCO-18 OpenPose limbs.
- `sprite/<pose>.png` at 832×1216 for full-height sprites.
- Matching `.json` editor files with `people[0].pose_keypoints_2d` for all 18 joints and confidence values.
- `manifest.json` (names, view directions and draft validation status), `pose-contact-sheet.png` for visual inspection.

The catalogue covers standing (including rear/side/three-quarter), gestures, walking, running, kneeling, crouching, chair/floor sitting, contact with a wall, bending forward, looking over the shoulder, and two floor poses. The templates use anatomical joint coordinates rather than filename-only stick figures. The generated images are *draft* ControlNet hints, not validated photographs or guaranteed pose matches.

**Safety gate:** old approved `running.png` and `kneeling.png` in `pose-guides` are untouched. The v2 catalogue lives in a separate directory and is **off by default**. To opt in after A/B evaluation, set `VN_POSE_LIBRARY_V2=1` on the GPU worker only. The runtime selector matches strictly: explicit rear or side camera **and** forward lean **and** both palms braced on a stone/brick wall. All other prompts keep using the previous approved guide selection or text-only direction. Do not automatically map the full catalogue to arbitrary narrator prose.

Each new pose should be A/B-tested against a text-only generation with the same neutral reference identity, camera, and surroundings; validate physical action, identity, and scene consistency with QA. Mark accepted entries in a future reviewed allowlist rather than enabling all 33 simply because PNGs exist. OpenPose controls skeleton geometry; it does **not** control garments, facial identity, anatomy or exact contact with environmental surfaces.

**Debugging:** a `POSE_CONTROL_ACTIVE` entry in the worker logs is evidence that the guide was actually applied to ComfyUI. Its absence means ControlNet had no effect even if the PNG is present on disk. Generated PNGs are reproducible from source; binary output is intentionally not committed to Git.

References: [COCO-18 pose editor](https://github.com/hisashi-ito/bonepose) and [ControlNet OpenPose palette reference](https://github.com/lllyasviel/ControlNet/discussions/266).

## Верификация на игровом ПК (29 октября 2026)

Библиотека развёрнута на ПК в `~/.local/share/mcp-vn/pose-guides-v2`: по 33 PNG и 33 JSON для `cg` и `sprite`, плюс manifest и обзорный лист. Исходники и сервисы сверены с GitHub `main` (коммит `8a39383`). Старые подтверждённые `running.png` и `kneeling.png` не менялись.

Сделаны два **изолированных ComfyUI A/B-теста** шаблона `brace_wall_rear`, на нейтральном персонаже в одежде. В каждом сравнении использовались одинаковые seed, описание, модель CyberRealistic Pony, 20 шагов и разрешение 1216×704. Первый вариант применял ControlNet strength 0.78 / end 0.86; второй — скорректированные координаты рук, strength 1.05 / end 0.92. Оба успешно завершились технически, но **не воспроизвели опору обеих ладоней на стену**. Визуальная корректность по исходному действию не улучшилась достаточно для автоматического применения.

Результаты сохранены на игровом ПК в `~/.local/share/mcp-vn/pose-guides-v2/reviews/2026-10-29-wall-brace` (3 PNG и `evaluation.json`). Оценка: `not_approved`. **`VN_POSE_LIBRARY_V2` по-прежнему выключен**. Запись в каталоге не равна подтверждению пригодности отдельной позы. Дальнейший шаг — более надёжный референс позы (например, из реального изображения с детекцией ключевых точек), после чего повторный A/B и независимая QA действия.


## DWPose — фото-референсы, проверка и допуск (2026-10-29)

На игровом ПК ComfyUI содержит `comfyui_controlnet_aux` (`DWPreprocessor`, `SavePoseKpsAsJsonFile`) и отдельные ONNXRuntime/OpenCV-зависимости в `/data/vendor-python`. Используется существующий ROCm PyTorch, который не переустанавливался. Исходники вспомогательного расширения находятся в `~/.local/share/mcp-vn-comfy/custom_nodes/comfyui_controlnet_aux`.

**Полностью воспроизводимый процесс:**

```bash
python3 worker/pose_reference_pipeline.py download
python3 worker/pose_reference_pipeline.py extract
python3 worker/pose_reference_pipeline.py validate
```

Референсы, карты поз и JSON-координаты хранятся только на ПК в `~/.local/share/mcp-vn/pose-references-v1` (не коммитятся). Manifest сохраняет URL/автора/лицензию, SHA-256 источника и карты, число уверенно найденных суставов, результаты A/B и отметку ревьюера. `choose_approved_reference()` не применяет карту, если не совпадают действие и ракурс, нет явного одобрения, изменился файл, детектор нашёл недостаточно суставов или нет протокола A/B/QA. `VN_POSE_REFERENCE_ENABLED=0` отключает выбор фотографических поз; значение по умолчанию 1, но без approved-записей система возвращается к прежнему методу без подмены ракурса.

**Фактическая оценка пяти референсов:** два фото из общественного достояния, хотя их описание было связано с отжиманиями от стены, оказались упражнениями у бассейна — отклонены из-за неверного физического контакта. Фотография наклона дала 0 точек — отклонена. Два дополнительных фотореференса реальной опоры ладонями на стену прошли DWPose с 18/18 и 16/18 точками соответственно; второй не одобрен из-за частично обрезанных ног. Источники дополнительных фотографий (BodySpec и Jackson Health) имеют **непроверенную лицензию**, поэтому оригиналы используются только локально для проверки геометрии и не публикуются в Git.

**Одобрено только `wall_push_correct_side_a` для бокового ракурса**, после двух нейтральных A/B-тестов в ComfyUI с неизменными seed/промптом/моделью и подтверждения, что две ладони действительно опираются на стену в кадрах с DWPose. Рендеры остаются локальными. При этом базовая VLM QA пропустила и неточное изображение без ControlNet — сравнительный визуальный осмотр необходим, и QA нельзя считать доказательством физического контакта. Задний ракурс этого сюжета **не одобрен**, поскольку нет подходящего проверенного фотографического референса. Никакой свободной замены rear на side не предусмотрено.

Ранее созданная библиотека из 33 ручных скелетов остаётся **draft/off**. Это отдельная библиотека, не путать её с DWPose-референсами. Изображения текущей игры и сохранения не менялись.

### Second verified pose: rear three-quarter hip hinge (2026-10-29)

Reference `hip_hinge_rear_oblique_02` was extracted by DWPose with 18/18 confident joints. Two seed-paired neutral ComfyUI A/B renders (`202610290856` and `202610290858`) were visually reviewed: the no-ControlNet baseline did not achieve wall contact, while the DWPose-guided version bent from the hips and placed both palms against the wall in both tests. Its local manifest entry was set to `approved` with hashes and review details. Test images remain only on the gaming PC under `~/.local/share/mcp-vn/pose-references-v1/reviews/2026-10-29-hip-hinge-rear-oblique-02/`. Source photo permission is **not verified**; the photo is kept locally and not included in Git. The original text, current wardrobe and identity requirements still determine the rest of the final CG; approval is for pose geometry alone. No save has been modified. All other unreviewed entries remain drafts.
