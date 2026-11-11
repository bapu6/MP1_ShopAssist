# ShopAssist — Mini-Project 1

Order support for Northwind Store (a fictional online store): a FastAPI service with per-session memory, three
validated tools, a defended system prompt and streamed answers. The model is reached only through a LiteLLM
gateway, and both run together with Docker Compose.

**Author:** bapup (bapup)
**Model tested:** `shopassist` → `groq/openai/gpt-oss-20b` (fallback: `groq/openai/gpt-oss-120b`)

## Architecture

```
browser / client ──► app (FastAPI, :8000) ──► litellm gateway (:4000) ──► Groq
                     memory · prompt · tools    master key · fallback · cost      API_KEY lives only here
```

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Liveness, plus the running model, gateway, memory strategy and tools |
| POST | `/chat` | `{"session_id", "message"}` → `{"answer", "tool_steps", "turns"}` |
| POST | `/chat/stream` | The same, streamed as Server-Sent Events: `tool`, `token`…, `done` |
| DELETE | `/sessions/{id}` | Forget one conversation |

## Run with Docker Compose (Path A)

```powershell
docker compose up --build        # gateway + app; Ctrl+C to stop, docker compose down to remove
```
Then open http://localhost:8000/docs in your browser to inspect the interactive Swagger UI and test any endpoint directly.

## Run without Docker (Path B)

```powershell
uv sync
# terminal 1 - the gateway
uv run --with "litellm[proxy]==1.80.0" litellm --config gateway/config.yaml --port 4000
# terminal 2 - the app
uv run uvicorn app.main:app --port 8000
```

## Evidence

```powershell
uv run python eval/run_eval.py      # needs the gateway running; writes experiments/mp1_results.md
```
Results: Golden 10/10, Memory probe pass, Attacks resisted 4/4. Detailed discussion in `experiments/mp1_report.md`.

## Design

ShopAssist adopts a sliding window memory strategy with `KEEP_TURNS = 4` to bound per-turn token costs while comfortably retaining multi-turn context (such as customer names and order numbers) required for order lookups and returns. The service exposes three deterministic read-only tools (`get_order_status`, `get_delivery_estimate`, `check_return_eligibility`) that rigorously validate argument formats (raising `ValueError` for malformed IDs or unsupported reasons), allowing the agent loop to feed an `INVALID` message back to the LLM rather than crashing. The system prompt is defended via an explicit instruction hierarchy that outranks all user overrides, denies unauthorized administrative authority, rejects prompt exfiltration attempts, and treats injected formatting tags as plain text. The LiteLLM gateway decouples the application from cloud vendor keys, automatically handles model aliasing under the `shopassist` group, and provides automated fallback to `gpt-oss-120b` if the primary model encounters rate limits or outages.
