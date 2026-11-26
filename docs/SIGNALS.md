# intent signals

the factor taxonomy says *what kind* of allegation is there (insider sales, CWs, GAAP). intent signals look for the *patterns courts point to when they infer state of mind*: ostrich behavior, ignored red flags, suspicious timing, concealment, and so on. each one comes back with the exact sentences that triggered it.

## architecture

```
text
 ├─ sentence split (exact offsets, case names like "v." and "Inc." kept together)
 │
 ├─ perception (neural slot)      app/encoder.py
 │    every sentence → vector, compared to 2–6 example phrasings per signal
 │    → best sentence + similarity per signal
 │
 ├─ reasoning (symbolic)          app/signals.py + data/scienter_signals.json
 │    roles   each signal has named roles, e.g. conscious_avoidance = red_flag + avoidance
 │    rule    all roles have to show up within N sentences, not negated, not pleading boilerplate
 │    time    dates and "two weeks before" are pulled into a timeline; trade → disclosure
 │            gaps, plan change → trade gaps, departure ↔ disclosure gaps are computed in days
 │    counter pre-planned trading, consistent prior sales, kept shares, self-reporting,
 │            disclosed risk, innocent explanation
 │
 └─ fusion                        app/fusion.py
      status      rules decide: supported (all roles) / partial (core roles) / semantic_only
      semantic    the encoder can only propose a signal when no rule fired, the sentence is
                  not already explained by a rule or a counter-signal, and that signal is the
                  sentence's best match. always marked needs review
      confidence  .65 × rule coverage + .35 × similarity. ranking only, not a probability
      statute     the selected claim reorders signals (e.g. criminal weights conscious
                  avoidance up) and flags claims where scienter isn't an element
      opposing    counter-signals are listed next to the signal, not subtracted, since the
                  court weighs competing inferences together (Tellabs)
```

why split it this way: rules are auditable and give exact quotes, but they miss paraphrases. similarity catches paraphrases but can't tell "he ignored the warning" from "there's no allegation he ignored the warning". so rules own the yes/no and the encoder only ranks or raises a hand.

### the encoder

default is `local-concepts`: stems, a small legal concept lexicon (avoid, warn, sell, disclose, hide, leave...) and bigrams as exact sparse features. it runs offline with no dependencies, and it is **not a neural network**. it fills the neural slot. to use a real sentence model:

```bash
pip install sentence-transformers
```

```bash
DOLUS_ENCODER=sbert:all-MiniLM-L6-v2 python3 -m app.server
```

the model downloads once. if it can't load, dolus falls back to the local encoder. the semantic-only cutoff is per encoder (`threshold`), so recheck it with `scripts/evaluate_signals.py` after switching.

## signals

| id | what it looks for | needs |
| --- | --- | --- |
| `conscious_avoidance` | ostrich / willful blindness / deliberate ignorance | warning + avoidance act within 2 sentences |
| `red_flags_disregarded` | warnings with no follow-up (recklessness) | warning + disregard |
| `contrary_internal_information` | internal reports said the opposite of public statements | internal source + public statement |
| `statements_despite_warnings` | reassurance after being warned | "even after", "despite being told"... |
| `suspicious_trading_timing` | insider sales before bad news | trade + disclosure + proximity, or dated gap ≤ 120 days |
| `trading_plan_timing` | 10b5-1 plan adopted or changed near bad news | plan + change + proximity |
| `departure_timing` | officer leaves around the disclosure | departure + officer + disclosure + proximity |
| `gatekeeper_exit` | auditor resigns, withdraws opinion, material weakness | gatekeeper + exit |
| `concealment` | deleted records, side letters, "don't put it in writing" | one act |
| `concrete_personal_motive` | personal benefit tied to the fraud | incentive + link; generic "keep the stock price high" is flagged |
| `quarter_end_manipulation` | channel stuffing, pull-ins, bill-and-hold | act + period |
| `certification_with_red_flags` | SOX 302/906 signed with warnings around | certification + warning |

## claims

`10b`, `10b5_insider`, `11`, `12a2`, `14a`, `17a`, `20a`, `9`, `16b`, `sox304`, `criminal`. each has the mental-state standard, a circuit note where there is one, and authorities. for §§ 11, 12(a)(2), 14(a), 16(b) and SOX 304 every signal carries a note that scienter isn't an element.

## editing rules

everything lives in `data/scienter_signals.json`. patterns are regex fragments wrapped in word boundaries. `validate_rules` rejects unknown roles, bad regex, and statutes that emphasize signals that don't exist. after changing rules run:

```bash
python3 scripts/evaluate_signals.py
```

```bash
python3 -m unittest tests.test_signals
```

## API

`POST /api/signals {text, statute?, circuit?}` returns `{signals, timeline, counter_signals, statute, encoder, threshold, method, warnings}`. `/api/analyze` and `/api/compare` include the same thing under `intent`. passages carry `structure.intent_signals` (rules only) and a `semantic_score`.

CLI, rules only:

```bash
python3 scripts/signals.py facts.txt --statute 10b --circuit 2
```

## evaluation

```bash
python3 scripts/evaluate_signals.py
```

`data/signal_eval_real.json` holds 190 real sentences from 9 of the CourtListener opinions in `data/flp_opinions.json` (the eval has not yet been extended to the 85 harvested ones). every item stores its offsets and the source sha256, and the evaluator refuses to run if the text doesn't match the checksummed opinion. sentences were picked by keyword/detector hits, so they over-sample hard negatives: legal standards, other cases, "the SAC does not plead...".

label rule: positive only when the sentence asserts an alleged or found fact about these parties. split by opinion: dev = Zucco, Daou, Novak (rules may be tuned here); test = Nguyen, Prodanova, South Ferry, Silicon Graphics, Metzler, Kalnit (never tuned on).

| stage | held-out test | dev |
| --- | --- | --- |
| before any real-data tuning (test = Nguyen, Prodanova) | F1 0.43, false alarms 22% | F1 0.33 |
| after tuning on dev | F1 0.83, false alarms 4% | F1 0.91 |
| + 4 opinions from the CourtListener API in test (n=109, 17 pos) | P 0.38 R 0.44 F1 0.41, false alarms 14% | F1 0.91 |
| exact-feature encoder + semantic cutoff retuned on dev (0.45 → 0.55) | **P 0.55 R 0.33 F1 0.41, false alarms 5%** | F1 0.95 |

what it shows: the old synthetic set scored near-perfect, while real opinions came in around 0.3–0.5. tuning on dev fixed legal-standard false alarms. but new opinions phrase insider sales differently ("sold a vast quantity", "sold large blocks", case parentheticals), so held-out F1 fell back to 0.41. that is the real generalization number. CI holds it as a regression floor (F1 ≥ 0.40, false alarms ≤ 15%). to improve it, move opinions into dev and keep a fresh test split.

## limits

- one labeler (not an attorney review), and only 6 held-out positives, so one sentence moves recall by ~17 points. read the counts, not just the ratios
- the test sentences were seen while labeling, though no rule was changed based on them
- sentence level only, so patterns spread across sentences are undercounted
- more filings would help most. CourtListener's API needs a free token (`COURTLISTENER_TOKEN`, see `scripts/acquire.py`); with one, new opinions can be added to `data/flp_opinions.json` and labeled into the test split
- patterns are english and US-style dates only
- timing windows (120 days for trades and departures, 90 for plan changes) are research defaults, not legal thresholds
- authorities are framework pointers, check current treatment before citing
- nothing here says scienter is or isn't adequately pleaded
