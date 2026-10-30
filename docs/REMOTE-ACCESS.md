# SSH-MCP → home → игровой ПК (Bazzite)

> ВАЖНО: это проверенный **транспорт**, не доказательство готовности рендера. Перед любой работой читать [../AGENTS.md](../AGENTS.md) и [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md). Состояние очередей/версий/сервисов обязательно проверять заново.

## Надёжный маршрут, проверен 2026-10-30

1. Через установленное SSH-MCP вызвать `infra_exec` с **`host="home"`**, **`as_root=true`**. SSH-MCP сам маршрутизирует запрос через VPS/OpenVPN на Ubuntu `xavoks-server`; не нужно пытаться вызвать `host="pc"` в SSH-MCP.
2. На home доступен SSH-ключ **`/opt/homeassistant/config/id_ed25519`** (не коммитить содержимое, не выводить его в отчёты). Он позволяет входить на Bazzite `192.168.50.27:22` как **`Xavok`**, регистр **строго** `Xavok`.
3. Проверенный read-only пример:

   ```bash
   ssh -i /opt/homeassistant/config/id_ed25519 \
     -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes \
     Xavok@192.168.50.27 \
     'hostname; id -un; date -Is; systemctl --user is-active mcp-vn-comfy mcp-vn-worker mcp-vn-vision; curl -sf http://127.0.0.1:8188/queue'
   ```

4. Ожидаемая идентичность — `xavok-pc` и `Xavok`. Критически важно: все три VN-службы — **пользовательские**; выполнять `systemctl --user status ...` внутри SSH-сеанса `Xavok`. Обычный `systemctl is-active` обращается к **system** и ошибочно показывает `inactive`. Проверять реальные unit ExecStart и runtime PID, а не статус по старому handoff.
5. На ПК `ComfyUI` слушает **127.0.0.1:8188**. Проверка `/queue`: оба массива `queue_running` и `queue_pending` должны быть пустыми перед запуском своего единственного GPU job. Очередь без задач сама по себе не исключает другого активного агента: проверять процессы, незавершённые systemd jobs и владельца очереди.
6. Локальная исследовательская директория владельца: `/var/home/Xavok/.local/share/mcp-vn/render-fix-20261030/`; здесь приватный `private-handoff-20261030.json` с исходниками, hash/paths и render evidence. **Никогда не коммитить этот manifest, изображения, prompts, save, токены и face refs.** Не делать `git clean`, reset, перезапись production или повторный GPU submit без проверки состояния.

### Пример вызова инструмента (псевдокод, без ключей)

```text
ssh-mcp.infra_exec(host="home", as_root=true,
  script="ssh -i /opt/homeassistant/config/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes Xavok@192.168.50.27 'systemctl --user is-active mcp-vn-comfy mcp-vn-worker mcp-vn-vision; curl -sf http://127.0.0.1:8188/queue'")
```

Если SSH отказывает, **не** использовать небезопасный `StrictHostKeyChecking=no` и не публиковать ключи. Проверить доступность ПК, SSH/known_hosts с home и обоснование расхождения. IP и путь к файлу являются деталями текущей установки, не универсальными настройками для чужого клона.
