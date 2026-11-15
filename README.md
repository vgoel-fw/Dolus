# Dolus — Precedent-analysis indexed for securities fraud

**Dolus** is a research tool for securities litigators. It intakes a fact pattern, decomposes it into a fixed group of scienter factors (insider trading  timing, CW specificity, GAAP magnitude, executive departures), and retrieves similar court-issued opinions for comparisons with citations and outcome statistics based on scienter. It also flags **intent signals**, the patterns courts cite when inferring state of mind (ostrich behavior, ignored red flags, suspicious trading timing, 10b5-1 plan timing, concealment and more), using a neuro-symbolic layer that ties every flag to exact sentences. It's intended for litigators to reason by analogy across precedent rather than receive an automatic verdict from an LLM. Data from CourtListener opinions & Stanford Securities Class Action Clearinghouse.

## Run

No third-party packages, Node installation, build step, or API key required for the local demo.

```sh
python3 -m app.server --port 8765
```

Open http://127.0.0.1:8765. Choose an example, decompose, review the factors, and compare. 

```sh
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py
python3 scripts/evaluate_signals.py
python3 scripts/signals.py some_facts.txt --statute 10b
```

## Implemented

- Corpus with Second/Ninth Circuit framework references and review questions.
- Draft extraction, editable factor statuses/specificity, and exact supporting passages.
- Optional Anthropic extraction, selected in UI.
- Same-circuit-first retrieval with procedural posture and defendant-scope filtering,TF-IDF scoring.
- Comparison grid with source passages, ruling evidence, distinctions, and links for high-fidelity.
- Posture filtering and case-deduplicated outcome metrics.
- SQLite case/evidence graph, narrative vectors, saved matters, and reviewer audit records.
- CourtListener CLI, and Stanford Clearinghouse CSV cross-reference queue.
- JSON and Markdown research exports, responsive interface with dark mode, text/Markdown uploads, and source inspection.
- Intent signals: 12 scienter patterns, 6 counter-signals, 11 claim profiles (§ 10(b), insider trading / 10b5-1, §§ 11, 12(a)(2), 14(a), 17(a), 20(a), 9, 16(b), SOX 304, criminal). See [docs/SIGNALS.md](docs/SIGNALS.md).

## Data and present limits

The corpus contains **6 public opinion excerpt records** and **9 full CourtListener opinions**. There are no fictional cases. Review requires checking the original opinion, posture, defendant coverage, ruling, quotation context, and treatment on top.

Reviewed comparisons are empty until a lawyer approves records; the default view shows real cases pending review, which never count toward rates. Appellate opinions are separate from trial-court motion rulings, and cases with settlement/dismissal metadata don't substitutes for a distinct scienter ruling from the backend.

## Optional LLM

Set `ANTHROPIC_API_KEY` and an available `ANTHROPIC_MODEL` in the process environment, then restart. `.env.example` lists settings; the server does not automatically load `.env`. The UI explicitly identifies that LLM extraction sends the fact pattern to Anthropic. The default method performs no external transfer. Credentials are never included in browser responses.

## Project map

| Path | Purpose |
| --- | --- |
| `app/server.py` | Local HTTP API and static frontend |
| `app/engine.py` | Extraction, retrieval, evidence validation, cohorts |
| `app/storage.py` | SQLite persistence, graph, imports, reviews |
| `app/llm.py` | Optional validated LLM extraction |
| `app/signals.py` | Symbolic signal rules, negation, timeline and day gaps |
| `app/encoder.py` | Sentence encoder (local hashed-concept default, optional sentence-transformers) |
| `app/fusion.py` | Neuro-symbolic fusion, statute weighting, counter-signals |
| `web/` | Complete HTML, CSS, JavaScript, favicon |
| `data/` | Taxonomy, real opinion excerpts and full CourtListener opinions, signal rules, eval sets |
| `scripts/` | Acquisition, import, evaluation commands |
| `tests/` | Analytical integrity, security, and data tests |
| `docs/` | Doctrine, data provenance, architecture, production roadmap |
| `CONTRACT.md` | API and schema contract |
| `var/` | Generated local database; ignored by Git |

## Next steps

More lawyer review, full Stanford Clearinghouse & CourtListener data

See [data acquisition](docs/DATA.md), [doctrinal notes](docs/DOCTRINE.md), and [production roadmap](docs/ROADMAP.md). 

## CourtListener passage update

Dolus now includes **9 CourtListener opinions** and their source-linked passages for litigators to search and compare. The Similar passages workspace shows exact quotations, surrounding source text, shared scienter factors and intent signals, and structural differences. **67 tests pass**, covering quote integrity, source links, retrieval behavior, and separation from outcome statistics. These checks do not establish legal citation accuracy or subsequent treatment; structural tags remain pending attorney review.

## Intent signals (neuro-symbolic)

The semantic similarity harness now does more than compare wording. It looks for signs of intent that show up in case law and explains each one.

- **Perception.** Each sentence is encoded and compared to example phrasings of every signal. The default encoder is local and dependency-free (hashed stems + a legal concept lexicon). It fills the neural slot but isn't a neural net. Set `DOLUS_ENCODER=sbert:<model>` to plug in a real sentence-transformers model.
- **Reasoning.** A rule engine checks that the required pieces are present and close together. For example, conscious avoidance needs a warning *and* an act of avoidance. It also checks that they are not negated and are not pleading boilerplate ("plaintiffs fail to allege..."). For timing signals it builds a dated timeline and computes the gap in days (trade → disclosure, plan change → trade, departure ↔ disclosure).
- **Fusion.** Rules decide the status (`supported`, `partial`). The encoder ranks results and can only propose a `semantic_only` signal for sentences no rule explains, always marked for review. Counter-signals (pre-planned 10b5-1 sales, consistent prior trading, kept shares, self-reporting, disclosed risk) sit next to the signal instead of being netted out, since courts weigh competing inferences holistically.
- **Claim-specific.** Picking a claim changes the read: criminal and insider trading weight avoidance, concealment and timing up; for §§ 11, 12(a)(2), 14(a), 16(b) and SOX 304 every signal is marked "scienter not an element".

- **Evaluated on real opinions.** 110 checksummed sentences from CourtListener opinions, split by opinion into dev and held-out test. On the held-out opinions F1 went from 0.43 to 0.83 and false alarms from 22% to 4%. The hand-written synthetic set had scored near-perfect throughout, which is why it's no longer the headline number.

Details, the rule table and limits are in [docs/SIGNALS.md](docs/SIGNALS.md). Signals are research prompts, not findings.

## Bug fixes

Things that would have broken later (retired default LLM model, stale seeded DB, `.js` served as text/plain on some Windows setups, port-80 host check, SQLite lock errors, fenced LLM JSON, and more) are fixed and labeled in [docs/BUGS.md](docs/BUGS.md), with regression tests in `tests/test_fixes.py`.
