# bugs fixed

each one is labeled with what kind of problem it was.

| label | where | what was wrong | fix |
| --- | --- | --- | --- |
| **future break** | `app/llm.py`, `.env.example` | default model was a dated sonnet-4 snapshot. once it's retired every llm extraction fails | default is now `claude-opus-5-5` with server side fallback, still overridable with `ANTHROPIC_MODEL` |
| **silent failure** | `app/llm.py` | model output wrapped in ```json fences failed `json.loads`, so good drafts got thrown away | strip fences before parsing |
| **confusing error** | `app/llm.py` | refusals and `max_tokens` cutoffs showed up as a generic parse failure | check `stop_reason` first, raise max_tokens to 16000, timeout 180s |
| **stale data** | `app/storage.py` | seeds were only inserted if missing, so after pulling new `data/cases.json` the local db kept serving old text | refresh changed seeds unless the record has a local review attestation |
| **intermittent 500** | `app/storage.py` | threaded server + sqlite default 5s lock timeout gave random `database is locked` | 15s busy timeout |
| **wrong status** | `app/storage.py` | deleting a matter that doesn't exist returned success | 404 |
| **blank page** | `app/server.py` | static types came from `mimetypes`, which reads the os registry. some windows boxes map `.js` to `text/plain` and with `nosniff` the module never runs | explicit content types for js/css/html/svg/json |
| **403 everything** | `app/server.py` | on port 80 browsers send `Host: localhost` with no port and the host check rejected it | accept bare host when port is 80 |
| **unclear 400** | `app/server.py` | bad `Content-Length` fell through to the generic error | explicit message |
| **crash** | `app/engine.py` | `wilson(0,0)` divides by zero if anything calls it outside `calibrate` | returns `None` |
| **traceback** | `scripts/tag_opinion.py` | metadata json that isn't an object threw an uncaught `AttributeError` | validation error |
| **can't attach evidence** | `web/app.js` | uploaded files with windows line endings kept `\r\n` in state while the textarea shows `\n`, so pasted multi-line quotes never matched | normalize newlines on upload |
| **dead button** | `web/app.js` | editing facts cleared the analysis but save stayed clickable and did nothing | tells you to rerun first |

regression tests for these are in `tests/test_fixes.py`.

## still open / watch for

- **perf**: `/api/analyze` returns full `opinion_text` for every result. fine at 24 cases, gets heavy with a real corpus
- **perf**: `Store.cases()` reads and parses every case on every request. needs caching once the corpus grows
- **ci**: workflow pins `actions/checkout@v4` / `setup-python@v5`, bump when github deprecates the node runtime
- **legal**: signal citations in `data/scienter_signals.json` are framework pointers, check them before they go in a brief
