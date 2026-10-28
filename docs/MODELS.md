# Модели и совместимость — mcp-vn 0.6.4

> Актуальный стек, подтверждённый на RX 9070 XT 16 ГБ. Здесь указаны **необязательные внешние веса**, которые пользователь получает и лицензирует самостоятельно. GitHub содержит только код пайплайна.

## Основные изображения

| Стиль игры | Файл (ComfyUI) | Архитектура | Использование |
| --- | --- | --- | --- |
| `realistic` | `CyberRealisticPony_V18.0_F16.safetensors` | SDXL/Pony | Основной реализм |
| `semireal` | тот же Pony v18 | SDXL/Pony | Полуреализм |
| `poster` | тот же Pony v18 | SDXL/Pony | Постер/кинокадр |
| `anime` | `waiIllustriousSDXL_v170.safetensors` | SDXL/Illustrious | Японское аниме |
| `animation` | `BASNSFWBetterAnimeStyleForNSFWHentai_baseV10.safetensors` | Anima UNET | Отдельная анимационная рисовка |

Для Anima требуются также `qwen_3_06b_base.safetensors` (text encoder) и `qwen_image_vae.safetensors` (VAE). Её workflow использует `UNETLoader` / `CLIPLoader` / `VAELoader`, 8 шагов и CFG 1. Она **не совместима** с обычной цепью SDXL `CheckpointLoaderSimple` и SDXL IPAdapter/ControlNet.

Pony и WAI используют SDXL-граф с соответствующими сэмплерами, лицевыми референсами и механизмами QA. Сами по себе хорошие лица не гарантируют точность сложного положения тел.

## Экспериментальные графические модели

В отдельном **Model Lab**, который не входит в исходники mcp-vn, оставлена CyberRealistic Z-Image Turbo v4 Q8: `CyberRealistic_zit_v4.0-Q8_0.gguf` через ComfyUI-GGUF, с собственными CLIP/VAE. Она не вызывается автоматическим игровым маршрутизатором. По пользовательскому сравнению Pony v18 даёт более устойчивые результаты, поэтому Z-Image оставлена только для ручных A/B-тестов.

Из рабочего набора были **удалены** Lustify XL v2, Illustrious XL 2.0, Z-Image Turbo NSFW v2, FLUX.2 Klein 9B, DreamShaperXL Turbo, RealVisXL v5 и Juggernaut XL v9. Старые инструкции, где они рекомендуются, перенесены в [исторический архив](history/README-v3-to-v64.md) и не отражают текущую конфигурацию.

## Локальные языковые модели

| Роль | Модель | Файл | Контекст | Размещение |
| --- | --- | --- | ---: | --- |
| Рассказчик отдельного локального эпизода | Cydonia 24B v4.3 IQ4_XS | `TheDrummer_Cydonia-24B-v4.3-IQ4_XS.gguf` | 4096 | ROCm 30 GPU layers + RAM |
| Визуальный режиссёр + резерв рассказчика | Qwen3.5 9B Q4_K_M | `Qwen3.5-9B-Q4_K_M.gguf` | 8192 | ROCm, GPU |
| Главный рассказчик канонической игры | ChatGPT | не локальный файл | — | MCP Apps с авторизованным подключением |

Ключевые настройки в `compose.yaml`:

```yaml
VN_LOCAL_MODEL_ID: "qwen3.5:9b-q4_K_M"
VN_LOCAL_NARRATOR_MODEL: "cydonia:24b-v4.3-iq4_xs"
VN_LOCAL_NARRATOR_FALLBACK: "qwen3.5:9b-q4_K_M"
```

В `deploy/kobold-gateway.py` модели запускаются по отдельным запросам, с выгрузкой после ответа. Отдельные ROCm/CPU-флаги описаны в [LOCAL-LLM-ROCM.md](LOCAL-LLM-ROCM.md).

В тестах без нагрузки Cydonia показала примерно 12–13 ток/с, Qwen — около 54 ток/с. Это не результат многоминутных диалогов с заполненным KV-кешем, а **контрольные короткие ответы**. На одной GPU одновременно разгонять тяжёлую LLM и SDXL не следует.

## Видео

Экспериментальный `Wan 2.2 TI2V 5B`. Видео запускается только по запросу пользователя из **принятого** локального CG и не перезаписывает канон. Его граф отличается от image pipeline; для его работы нужны собственные UNET / encoder / VAE и видео-ноды. Веса не включены в репозиторий.

## Лицензии и источники

Перед установкой, публикацией изображений и коммерческим использованием проверьте лицензии соответствующего checkpoint, LoRA, исходной модели и вспомогательных узлов. Производные community-модели могут иметь ограничения, отличные от базовой архитектуры.

Внешние источники для самостоятельной проверки:

- CyberRealistic Pony: https://huggingface.co/cyberdelia
- WAI-Illustrious: https://huggingface.co/yufusoft/WAI-illustrious-SDXL
- Anima: https://huggingface.co/circlestone-labs/Anima
- Cydonia GGUF: https://huggingface.co/bartowski/TheDrummer_Cydonia-24B-v4.3-GGUF
- ComfyUI: https://github.com/comfyanonymous/ComfyUI
- KoboldCpp ROCm: https://github.com/LostRuins/koboldcpp

Выпуск community-весов и их SHA-256 могут меняться. Используйте контрольные суммы именно скачиваемых файлов, а не цифры из старого сравнительного теста.

## Точность и качество

- Схемы генерации выбираются по **стилю сохранения**, который нельзя незаметно переключить посреди игры.
- Изменения персонажей включаются в структурированный visual state; локальный CG использует этот state и имеющиеся канонические лица.
- Техническая QA отсеивает грубые ошибки персонажей/локации, **но не гарантирует** точное направление взглядов, контакт рук, кожу, анатомию или фактически изображённое действие.
- Для сравнения моделей используйте одинаковое нейтральное описание, seed, разрешение и независимую оценку нескольких кадров. Не ранжируйте их по единственному CLIP score.
