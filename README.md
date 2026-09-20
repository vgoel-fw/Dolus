# Precedent-analysis for securities scienter

**Scienter Atlas** is a local research application for securities litigators. It decomposes allegations into a fixed taxonomy, compares reviewed opinions, and reports descriptive cohort outcomes without rendering a scienter conclusion.

## Run

Python 3.11 or newer; no third-party packages, Node installation, build step, or API key required for the local demo.

```sh
python3 -m app.server --port 8765
```

Open http://127.0.0.1:8765. Choose a fictional example, decompose, review the factors, and compare. Run from this directory, not its parent. Open this directory in VS Code, PyCharm, Cursor, or another IDE.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
```

## Implemented

- Twelve-factor, versioned taxonomy with Second/Ninth Circuit framework references and review questions.
- Local draft extraction, editable factor statuses/specificity, and exact supporting passages.
- Optional server-side Anthropic extraction, selected explicitly in the UI.
- Same-circuit-first retrieval; exact procedural posture and defendant-scope filtering; transparent factor/TF-IDF scoring.
- Side-by-side comparison grid with source passages, ruling evidence, known distinctions, and source links.
- SQLite case/evidence graph, narrative term vectors, saved matters, and reviewer audit records.
- Case-deduplicated conjunctive cohorts, separate synthetic/real modes, Wilson intervals, and suppression below 20 binary scienter outcomes.
- Corpus import, human review admission, CourtListener staging CLI, and authorized SCAC CSV cross-reference queue.
- JSON and Markdown research exports, responsive interface, text/Markdown uploads, and source inspection.

## Data and present limits

The initial corpus contains **6 public opinion excerpt records**, all awaiting attorney review, plus **18 explicitly fictional fixtures** and 4 synthetic inputs. These are not a comprehensive research corpus. Source excerpt matching verifies internal consistency, not external authenticity. Review requires checking the original opinion, posture, defendant coverage, ruling, quotation context, and subsequent treatment.

The local extractor is a conservative keyword baseline. It can miss negation scope and overlapping concepts. It is not a validated production tagger; the included synthetic evaluation exposes those limitations. Narrative retrieval uses TF-IDF, not learned semantic embeddings. The optional LLM call has not been live-tested without credentials. Authentication, multi-user authorization, encrypted backups, a citator, full-text ingestion normalization, and large-corpus performance are not implemented. This server binds to localhost and is not an internet deployment.

Real comparisons are initially empty by design: the public seed cases have not been approved by a securities litigator. Synthetic outcomes never contribute to real rates. Appellate opinions are separate from trial-court motion rulings. Eventual settlement/dismissal metadata never substitutes for a scienter ruling.

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

## Data needed to expand

1. An authorized CourtListener API token / appropriate access tier.
2. An authorized Stanford SCAC export and a confirmed court/docket crosswalk.
3. Securities-litigator validation of taxonomy and opinion annotations.

See [data acquisition](docs/DATA.md), [doctrinal notes](docs/DOCTRINE.md), and [production roadmap](docs/ROADMAP.md). Do not put credentials, client fact patterns, runtime databases, or licensed exports into Git. No license granting redistribution of third-party data is implied.
