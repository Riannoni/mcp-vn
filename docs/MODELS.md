# Модели и совместимость — mcp-vn 0.7.x

> Актуальный стек на RX 9070 XT 16 ГБ. Qwen удалён. Локальный рассказчик — только Cydonia как запасной вариант. Основной рассказчик — внешний (Grok через CLIProxyAPI), который ведёт историю, поддерживает мир и отдаёт полные английские image_prompts (включая NSFW).

## Основные изображения

| Стиль игры | Файл (ComfyUI) | Архитектура | Использование |
| --- | --- | --- | --- |
| `realistic` | `CyberRealisticPony_V18.0_F16.safetensors` | SDXL/Pony | Основной реализм |
| `semireal` | тот же Pony v18 | SDXL/Pony | Полуреализм |
| `poster` | тот же Pony v18 | SDXL/Pony | Постер/кинокадр |
| `anime` | `waiIllustriousSDXL_v170.safetensors` | SDXL/Illustrious | Японское аниме |
| `animation` | `BASNSFWBetterAnimeStyleForNSFWHentai_baseV10.safetensors` | Anima UNET | Отдельная анимационная рисовка |

Для Anima требуются также `qwen_3_06b_base.safetensors` (текстовый энкодер) и `qwen_image_vae.safetensors` (VAE).

## Локальные языковые модели

| Роль | Модель | Файл | Контекст | Размещение |
| --- | --- | --- | ---: | --- |
| Запасной рассказчик (если внешний недоступен) + визуальный план для локальных эпизодов | Cydonia 24B v4.3 IQ4_XS | `TheDrummer_Cydonia-24B-v4.3-IQ4_XS.gguf` | 4096 | ROCm 30 GPU layers + RAM |
| Главный рассказчик канонической игры + полные image_prompts (включая NSFW) | Grok (или другой внешний через CLIProxyAPI) | — | — | Облако / CLIProxyAPI |

Ключевые настройки в `compose.yaml`:

```yaml
VN_LOCAL_MODEL_ID: "cydonia:24b-v4.3-iq4_xs"
VN_LOCAL_NARRATOR_MODEL: "cydonia:24b-v4.3-iq4_xs"
VN_LOCAL_NARRATOR_FALLBACK: "cydonia:24b-v4.3-iq4_xs"
```

Qwen полностью удалён. Cydonia используется только когда выбран локальный режим или внешний рассказчик недоступен. Основной путь — Grok, который ведёт историю, поддерживает память мира и отдаёт полноценные английские промпты для локальных моделей генерации (обычные и NSFW).

## Промпты для генерации

Финальная адаптация промптов выполняется **один раз** в `worker/worker.py:prompt_builder`: там учитываются выбранный checkpoint, негативные признаки, число персонажей и эталоны лиц. Не дублируйте теги через второй JS-enhancer: это создаёт конфликтующие указания, смещает внимание модели и увеличивает число неудачных CG.

Основной рассказчик (Grok) должен возвращать в `scene.image_prompts` полные английские positive-промпты для background / sprites / cg. Локальные модели получают уже усиленные версии.

## Видео

Экспериментальный `Wan 2.2 TI2V 5B`. Видео запускается только по запросу из принятого CG.

## Лицензии и источники

Проверяйте лицензии чекпоинтов самостоятельно.

- CyberRealistic Pony: https://huggingface.co/cyberdelia
- WAI-Illustrious: https://huggingface.co/yufusoft/WAI-illustrious-SDXL
- Anima: https://huggingface.co/circlestone-labs/Anima
- Cydonia GGUF: https://huggingface.co/bartowski/TheDrummer_Cydonia-24B-v4.3-GGUF
