# Connecting mcp-vn to ChatGPT on the web

The game MCP server is a **remote Streamable HTTP** service, not a local stdio server.

## Important

Saving a portable ZIP using Plugin Creator does not automatically register its `mcp.json` endpoint as a connected **cloud App** in ChatGPT. If a plugin detail page says **Open in desktop app** and the ChatGPT chat reports **tools unavailable**, do not repeatedly reconnect that ZIP-only plugin. First create an actual custom MCP-server connection in ChatGPT on the web. This is the official workflow for cloud Apps.

## Registration

1. Open [ChatGPT](https://chatgpt.com) in the browser and enable **Developer mode** under **Settings → Security and login**, if required by your account.
2. Open the [Plugins directory](https://chatgpt.com/plugins), click **+**, then choose **Add custom MCP server**.
3. Name: **mcp-vn Cloud**. Server URL: `https://xavoks.jo3.org/vn/mcp`.
4. Transport: Streamable HTTP (auto-discovery); authentication: **OAuth** (CIMD / Client ID Metadata Documents, if offered). Do **not** select no authentication.
5. Complete the Auth0 login for the personal account authorized to use this server.
6. Choose **Create as a plugin** and install it if prompted. The newly created plugin may initially coexist with the older ZIP-only package.
7. Open a **new ChatGPT Work conversation in the web app** (Chat → Work selector where available). Select the cloud plugin by typing `@` and choose it.
8. Ask **“Use mcp-vn Cloud.open_game to open my visual novel and load Max Crow.”**

The new server-backed App gets a platform ID beginning with `plugin_asdk_app_`. Copy that ID from its plugin/App URL. Then update the existing portable plugin to depend on the registered App by adding `.app.json` and `extensions.com.openai.apps`, preserving the original plugin identity and deployment.

## Deployment diagnostics

- `GET https://xavoks.jo3.org/vn/healthz` → 200
- Anonymous `https://xavoks.jo3.org/vn/mcp` → 401 (expected)
- OAuth resource metadata `/.well-known/oauth-protected-resource/vn/mcp` → 200
- Authenticated MCP `initialize` → `mcp-vn`
- Authenticated MCP `tools/list` → 12 tools
- `open_game` → saved game; UI resource `ui://mcp-vn/visual-novel.html` with MIME `text/html;profile=mcp-app`

The server works independently of the ZIP package. The existing plugin having a skill and `mcp.json` does not prove that the ChatGPT host authenticated or registered its remote App.

## If Work or custom MCP is unavailable

Account, workspace, plan and app surface affect support. If **Developer mode**, **Add custom MCP server** or **Work** is missing, do not weaken authentication or switch the remote server to unauthenticated access. The missing control must be resolved on the ChatGPT account/workspace side.

## Notes

- Never put `VN_MCP_TOKEN`, `VN_WORKER_TOKEN`, `VN_ASSET_SECRET`, Auth0 tokens or credentials in a GitHub repository or plugin ZIP.
- The direct unauthenticated 401 is not a service outage.
- A connected App still needs an end-to-end test of `App.sendMessage` and the in-chat view.
