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
- JSON and Markdown research exports, responsive interface, text/Markdown uploads, and source inspection.
- Intent signals: 12 scienter patterns, 6 counter-signals, 11 claim profiles (§ 10(b), insider trading / 10b5-1, §§ 11, 12(a)(2), 14(a), 17(a), 20(a), 9, 16(b), SOX 304, criminal). See [docs/SIGNALS.md](docs/SIGNALS.md).

## Data and present limits

The corpus contains **6 public opinion excerpt records** and **94 full CourtListener opinions**. There are no fictional cases. Review requires checking the original opinion, posture, defendant coverage, ruling, quotation context, and treatment on top.

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
| `app/encoder.py` | Sentence encoder (local concept-lexicon default, optional sentence-transformers) |
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

## CourtListener cases

All fictional cases, examples and the demo mode are gone. Every record is a real opinion, and the validator rejects `synthetic: true`.

The database holds **94 distinct published opinions** (33 Second Circuit, 61 Ninth Circuit, 1999 to 2026) with 6,930 searchable passages. Nine were picked by hand (Zucco v. Digimarc, In re Daou Systems, Novak v. Kasaks, Nguyen v. Endologix, Prodanova v. H.C. Wainwright, South Ferry v. Killinger, In re Silicon Graphics, Metzler v. Corinthian Colleges, Kalnit v. Eichler). The other 85 came from `scripts/harvest.py`, which searches CourtListener for published Second and Ninth Circuit opinions on scienter and keeps only ones that discuss it.

Each opinion stores its source URL, retrieval date and a sha256 of the text, and the app refuses to load an opinion whose text no longer matches. The harvester skips an opinion if the same text or the same case (same name, filed within a day) is already held. Original and amended versions of a case are kept as separate opinions. The passage index is cached in `var/`, so the first start after the corpus changes takes up to a minute and later starts are instant.

CourtListener's API allows 5 requests a minute and 125 a day. The harvester waits about 13 seconds between requests and saves progress after each one, so you can stop and restart it:

```bash
python3 scripts/harvest.py run --target 100
```

```bash
python3 scripts/harvest.py merge
```

The target of 100 was not reached in the first session: the daily cap was hit at 94, and the last six can be added once it resets. Outside this environment, set `COURTLISTENER_TOKEN` first.

## Neuro-symbolic intent signals

The similarity harness used to compare wording. It now looks for the patterns courts cite when they infer state of mind, and it ties each one to exact sentences.

```
sentence ──► encoder ──► "sounds like" score per signal ─┐
         └─► rule engine: roles, negation, dates ────────┴─► fusion ──► signal + quotes + gaps + counter-evidence
```

- **Encoder (neural slot).** `app/encoder.py` turns each sentence into a vector and compares it with example phrasings of every signal. The default runs offline with no dependencies: word stems plus a legal concept lexicon, so "unloaded" sits near "sold" and "overlooked" near "ignored". It is a stand-in, not a trained network. Set `DOLUS_ENCODER=sbert:all-MiniLM-L6-v2` to use a real sentence-transformers model. If that model can't load, Dolus falls back to the local encoder.
- **Rules (symbolic).** `data/scienter_signals.json` defines 12 signals as named roles. Ostrich behavior, for example, needs a *warning* and an *act of avoidance* within two sentences. Each role is checked for negation, and sentences that state law, describe other cases or reject a theory are filtered out. Timing signals get a dated timeline and a gap in days.
- **Fusion.** Rules decide whether a signal is present. The encoder only ranks, or flags a "semantic match" for a sentence no rule explains, and those always need review. Counter-evidence (a pre-existing 10b5-1 plan, sales consistent with prior trading, kept shares, self-reporting) is listed next to the signal rather than subtracted, since courts weigh competing inferences together.
- **By claim.** 11 claim profiles adjust the read. Criminal and insider-trading claims rank avoidance, concealment and timing higher. For §§ 11, 12(a)(2), 14(a), 16(b) and SOX 304, each signal is marked "scienter is not an element".

### Example

Fact pattern:

> In January 2021 the controller warned the CFO that reserve releases were inflating earnings. The CFO told her he did not want to know and stopped attending the monthly close meetings. On March 3, 2021 the CFO sold 70% of his holdings. The company announced the restatement on April 1, 2021 and the stock fell 40%. Some of the sales were made pursuant to a pre-existing 10b5-1 plan.

What Dolus returns under § 10(b), Ninth Circuit:

| Signal | Status | Why | Score |
| --- | --- | --- | --- |
| Deliberate ignorance (ostrich) | rule satisfied | *warning*: "the controller warned the CFO..." + *avoidance*: "he did not want to know and stopped attending..." within 2 sentences | 88 (rule 100, encoder 66) |
| Suspicious trading timing | rule satisfied | *trade*: "sold 70% of his holdings" on 2021-03-03 → *disclosure*: restatement on 2021-04-01, a **29 day** gap from the parsed dates | 79 (rule 100, encoder 41) |

The trading signal also shows **cuts the other way: pre-planned trading**, quoting the 10b5-1 sentence. Switching the claim to criminal doubles the ostrich signal's rank, matching the conscious-avoidance (Global-Tech) standard. Switching to § 11 keeps both signals but marks scienter as not an element. Rewriting the second sentence as "there is no allegation the CFO declined to review anything" removes the ostrich signal. The warning sentence then only shows up as a low-confidence semantic match (SOX certification), marked for review.

Run it yourself:

```bash
python3 scripts/signals.py facts.txt --statute 10b --circuit 9
```

## Eval set

`data/signal_eval_real.json` holds 190 real sentences from 9 of the CourtListener opinions, labeled by signal. A sentence counts as positive only when it states a fact about the parties. Legal standards, other cases and "the complaint does not plead..." count as negative, and those make up most of the hard cases. Each item stores its offsets and the opinion's sha256, so the eval won't run if the source text changes.

It is split by opinion. Zucco, Daou and Novak are **dev**, which the rules may be tuned on. The other six opinions are the **held-out test**, never used for tuning.

| | n / positives | Precision | Recall | F1 | False alarms on negatives |
| --- | --- | --- | --- | --- | --- |
| dev | 81 / 9 | 0.91 | 1.00 | 0.95 | 1% |
| held-out test | 109 / 17 | 0.55 | 0.33 | 0.41 | 5% |

**Why this matters:** the hand-written synthetic set used to score near-perfect. Real opinions showed what it hid. Tuning on dev lifted the first two held-out opinions from F1 0.43 to 0.83. The four opinions added from the API then dropped held-out F1 to 0.41, with recall the weak spot (it misses a third of the real instances). Silicon Graphics and Metzler describe sales as "sold a vast quantity" or "sold large blocks", and cite other cases in parentheticals. The dev-tuned rules hadn't seen either. The eval measures how well the rules generalize, and right now they don't generalize well. CI keeps this baseline as a regression floor, and the next round of rule work should move opinions into dev rather than tune on the test set.

```bash
python3 scripts/evaluate_signals.py
```

Limits: one labeler, not an attorney review. Labels are per sentence, so patterns spread across sentences are undercounted. 17 held-out positives is still small, so read the counts and not just the ratios.

**66 tests pass**, covering quote integrity, source checksums, retrieval, signal rules and separation from outcome statistics. None of this establishes that scienter is or isn't adequately pleaded.

## Bug fixes

Things that would have broken later (retired default LLM model, stale seeded DB, `.js` served as text/plain on some Windows setups, port-80 host check, SQLite lock errors, fenced LLM JSON, and more) are fixed and labeled in [docs/BUGS.md](docs/BUGS.md), with regression tests in `tests/test_fixes.py`.
