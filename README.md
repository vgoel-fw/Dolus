# Scienter Atlas: Precedent-analysis indexed for securities scienter

**Scienter Atlas** is a research tool for securities litigators. It intakes a fact pattern, decomposes it into a fixed group of scienter factors (insider trading  timing, CW specificity, GAAP magnitude, executive departures), and retrieves similar motion-to-dismiss opinions for side-by-side comparison with citations and outcome statistics based on scienter. It's intended for litigators to reason by analogy across precedent rather than receive an automatic verdict. Corpus comes from CourtListener opinions with Stanford Securities Class Action Clearinghouse's outcome data.

## Run

No third-party packages, Node installation, build step, or API key required for the local demo.

```sh
python3 -m app.server --port 8765
```

Open http://127.0.0.1:8765. Choose an example, decompose, review the factors, and compare. 

```sh
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
```

## Implemented

- Corpus with Second/Ninth Circuit framework references and review questions.
- Draft extraction, editable factor statuses/specificity, and exact supporting passages.
- Optional Anthropic extraction, selected in UI.
- Same-circuit-first retrieval with procedural posture and defendant-scope filtering,TF-IDF scoring.
- Comparison grid with source passages, ruling evidence, distinctions, and links for high-fidelity.
- SQLite case/evidence graph, narrative vectors, saved matters, and reviewer audit records.
- CourtListener CLI, and SCAC CSV cross-reference queue.
- JSON and Markdown research exports, responsive interface, text/Markdown uploads, and source inspection.

## Data and present limits

The initial corpus contains **6 public opinion excerpt records** plus **18 fictional fixtures** and 4 synthetic inputs. Review requires checking the original opinion, posture, defendant coverage, ruling, quotation context, and treatment on top.

Real comparisons are initially empty by design for lawyer approval, and the synthetic outcomes don't contribute to real rates. Appellate opinions are separate from trial-court motion rulings, and cases with settlement/dismissal metadata don't substitutes for a distinct scienter ruling from the backend.

## Optional LLM

Set `ANTHROPIC_API_KEY` and an available `ANTHROPIC_MODEL` in the process environment, then restart. `.env.example` lists settings; the server does not automatically load `.env`. The UI explicitly identifies that LLM extraction sends the fact pattern to Anthropic. The default method performs no external transfer. Credentials are never included in browser responses.

## Project map

| Path | Purpose |
| --- | --- |
| `app/server.py` | Local HTTP API and static frontend |
| `app/engine.py` | Extraction, retrieval, evidence validation, cohorts |
| `app/storage.py` | SQLite persistence, graph, imports, reviews |
| `app/llm.py` | Optional validated LLM extraction |
| `web/` | Complete HTML, CSS, JavaScript, favicon |
| `data/` | Taxonomy, opinion excerpts, synthetic examples and evaluation |
| `scripts/` | Acquisition, import, evaluation commands |
| `tests/` | Analytical integrity, security, and data tests |
| `docs/` | Doctrine, data provenance, architecture, production roadmap |
| `CONTRACT.md` | API and schema contract |
| `var/` | Generated local database; ignored by Git |


See [data acquisition](docs/DATA.md), [doctrinal notes](docs/DOCTRINE.md), and [production roadmap](docs/ROADMAP.md). 
