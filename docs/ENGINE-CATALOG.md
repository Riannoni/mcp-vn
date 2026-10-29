# Shared engine and multi-game catalog

One engine contract is stored in engine/contract.json. It is versioned and applied to every story and playthrough: rendering profile, pose library revision, strict QA and available region budget are never overridden by a story.

Catalog templates are data/stories/<id>.json; playthroughs are data/games/<uuid>.json. Their messages, player character, memories, artwork and locked visual style remain isolated.

The authenticated standalone endpoints GET /worker/standalone/catalog and GET /worker/standalone/engine expose catalog metadata and the current engine contract. No unauthenticated import API exists.

## Offline story import

A versioned mcp-vn.story.v1 JSON package contains id, title, author, source, rights_confirmed, summary, lore, opening, initial scene, characters and choices. External sources also require source_url. The importer is data-only: no external fetch, program execution, remote assets or engine-policy overrides. Confirmation of rights is required; public visibility of a third-party story does not grant copying rights.

Sample JSON:

```json
{ "schema":"mcp-vn.story.v1", "id":"my-world", "title":"My World", "author":"Creator", "source":"user-provided", "rights_confirmed":true, "summary":"New adventure", "lore":"History and world rules", "opening":"The hero arrives in town.", "scene":{"location":"Town square"}, "characters":[{"id":"guide", "name":"Guide", "age":30, "description":"Adult guide"}], "choices":["Explore","Talk"] }
```

To validate or import from an explicitly mounted file, on the home server:

```bash
cd /opt/mcp-vn
docker compose run --rm --no-deps -v /path/to/story.json:/imports/story.json:ro game node scripts/import-story.mjs --dry-run /imports/story.json
docker compose run --rm --no-deps -v /path/to/story.json:/imports/story.json:ro game node scripts/import-story.mjs /imports/story.json
```

The import never overwrites an existing story ID or modifies an active save. No direct site scraping has been implemented. A future KageSekai adapter requires an authorized export or another permitted source.

## Roadmap

Next: catalog UI to start and resume independent sessions; structured narrator shot plan shared by every game; explicit named cast versus background extras; real multi-person ControlNet regions and staged rendering beyond four principals; stronger visual grounding QA benchmark; per-source import adapters with attribution and provenance.
