# Corpus provenance and acquisition

## What ships

`data/taxonomy.json` is a versioned draft schema with twelve factors. `data/cases.json` contains six real opinion **excerpt** records and eighteen wholly fictional training records. `data/examples.json` has fictional input examples. `data/synthetic_ground_truth.json` records stipulated factor statuses for deterministic evaluation; it is not ground truth for real legal outcomes.

Real seed opinions: Zucco (2009), Daou (amended 2005), NVIDIA (2014), Novak (2000), ATSI (2007), and Dynex (2008). All real records are `needs_review`. All retain source URLs and locators. `opinion_text` contains selected passages only, **not the full opinion**; `source_provenance.coverage` says `excerpts_only`. Judicial text was inspected through the linked sources and whitespace normalized. Mirror OCR can drop apostrophes or insert line numbers: before approval, check the linked opinion PDF, exact text, reporter/slip pinpoint, amended version, defendant/claim coverage and later history. Automated substring validation is only one check.

Fictional records carry “FICTIONAL” in the name, “SYNTHETIC — no legal citation” in the citation, empty external source URLs and explicit stipulated-disposition text. Their outcomes were assigned for interface tests, not generated as predictions from factors. They must never enter real empirical statistics. `reviewed` on a synthetic record means internally consistent fixture, not attorney review. Examples never contain client information.

`outcome` records the encoded ruling at this opinion stage, with `outcome_basis` identifying whether it concerns scienter, another ground, mixed grounds or unknown grounds. `case_outcome` remains unknown; a settlement, final dismissal, or SCAC status is a separate fact. Novak passed scienter while other pleading particularity was remanded; Daou is mixed across defendants; ATSI includes additional grounds; Dynex is an interlocutory appeal with leave to replead. No population survival rate follows from this hand-selected seed.

## CourtListener staging

From the project root, use Python 3.11+ and an authorized CourtListener account token in the environment. Never paste tokens into Git or matter text.

```sh
export COURTLISTENER_TOKEN='your-token'
python3 scripts/acquire.py search --query 'scienter AND ("10b-5" OR "10(b)")' --out work/courtlistener-search --pages 1
python3 scripts/acquire.py opinion 12345 --out work/selected-opinion
```

`12345` is an illustrative ID, not a curated precedent. Select actual IDs from returned search results. Search retrieves candidates, not an automatically validated Second/Ninth MTD corpus. Review courts, posture, claim, opinion type and duplicate appellate/district decisions. Search results are not full opinion text. The opinion endpoint returns the available source fields; retain original data and normalize a copy with documented transformations before extracting tags.

The CLI uses v4 APIs, token authentication, bounded pagination via the server's `next` field, 13-second minimum inter-page spacing, refused redirects, same-origin pagination checks and an on-disk manifest. It stops on throttling/errors without hammering the service. Resume the manifest's `next` URL with `--resume-url` into a **new** directory. Do not run concurrent jobs to circumvent account limits. Bulk access and endpoint entitlements may require an arrangement with Free Law Project. See the [official API documentation](https://www.courtlistener.com/help/api/rest/) for current access and rate limits. No authenticated acquisition has been run in this project; no token has been supplied.

## Stanford cross-reference

The [Stanford Securities Class Action Clearinghouse](https://securities.stanford.edu/) is a useful case-level source, but a public website is not a promise of free bulk export, API access, or permission for commercial redistribution. Review its terms and obtain a lawful export or permission. The platform does **not** scrape SCAC or assert access to its entire dataset.

Supply a CSV you are authorized to use, with:

```csv
case_id,scac_id,case_outcome,source_url
local-reviewed-case-id,provider-record-id,settled,https://securities.stanford.edu/example-record
```

The example row is a format illustration, not a real SCAC match. A researcher must establish `case_id` from court, docket, issuer and dates; do not fuzzy-join on similar party names alone.

```sh
python3 scripts/acquire.py crossref --csv work/authorized-scac.csv --cases data/cases.json --out work/scac-links.json
```

This writes a separate review queue with exact ID joins and unmatched rows. It refuses a link to synthetic cases. It never overwrites a motion or scienter outcome with a case-level settlement/dismissal label. Keep licensed metadata out of Git unless redistribution is authorized.

## Structured import and review

Use the schema in `CONTRACT.md`. All twelve factor IDs must exist; unsupported factors remain unknown. Every known factor and outcome needs a nonempty quote anchored in the supplied source text, a locator and characterization; real evidence also needs HTTPS provenance.

```sh
python3 scripts/import_cases.py data/cases.json
python3 scripts/import_cases.py work/reviewed-extraction.json --server http://127.0.0.1:8765
```

The first command validates without writes. The second imports into the local server. Imports reset real records to `needs_review`, even if the file claimed reviewed. Review must encompass full source, quote attribution and outcome, not merely matching text. An approved reviewer can then use the server's corpus-review endpoint. Do not treat this starter corpus as already legally reviewed.

To evaluate decomposition, compare extraction to synthetic statuses in `synthetic_ground_truth.json`, report precision/recall per factor and distinguish omission from negation. The examples include vague CWs and opposing explanations; matching keywords does not establish legal sufficiency. Manual adjudication remains essential for real opinions.

## Data still needed

1. CourtListener token and, if necessary, expanded access agreement for a complete public corpus.
2. Authorized SCAC export or permission and human-confirmed docket crosswalk.
3. Securities-litigator taxonomy and source review; sufficiently large, consistently defined corpus before empirical inference.

Source staging and the SQLite database are local. Synthetic/public seed JSON may be committed; credentials, live matters, licensed exports and runtime databases must stay out of version control.

## Source-check pass and extraction evaluation

A second source check inspected the linked judicial text for all six records and the linked opinion PDFs for Zucco, Dynex and NVIDIA. Zucco/Dynex quotes were corrected for punctuation dropped by their HTML mirrors, and their evidence links now point to PDFs. Daou's direct-involvement passage is at 1023; where reporter pagination was not independently confirmed, locators use the exact section and paragraph opening instead of a guessed page. These checks do not change `needs_review` status and are not a later-treatment/citator check.

Run `python3 scripts/evaluate.py` to assess the current deterministic extractor against the eighteen authored fixtures. The committed `data/evaluation.json` includes the engine hash and errors; it is a development snapshot. Its labels are generation-recipe labels, not independently adjudicated legal annotations, and it contains no explicit absent-factor ground truth. Do not report its precision as real-world reliability. In particular, a broad sentence-level negation rule can abstain on a present investigation merely because the sentence states there was no charge.

## Opinion tagging CLI

After obtaining source text lawfully, normalize it to a UTF-8 text file. Prepare case metadata using the complete record shape in CONTRACT.md, including a manually identified ruling, exact outcome quote/locator, source URL, and provenance. The tagger overwrites factors, opinion_text, and review status; it never infers a ruling from case disposition.

```sh
python3 scripts/tag_opinion.py --text work/opinion.txt --metadata work/metadata.json --out work/tagged-opinion.json
# Optional --llm explicitly sends opinion text to Anthropic.
python3 scripts/import_cases.py work/tagged-opinion.json --server http://127.0.0.1:8765
python3 scripts/generate_synthetic.py --count 6 --seed 42 --out work/patterns.json
```

Tagging produces local character offsets, not invented paragraph numbers or legal pinpoints. Replace/verify locators in source review. The synthetic generator samples authored templates with their stipulated profiles; it is reproducible but not an independent benchmark or a model of legal outcomes.


## Provider acquisition status — 2026-09-20

One public Stanford Clearinghouse record (104095, NVIDIA) is linked in the seed corpus with its case-level dismissed status and filing date. The entity match remains pending attorney review. The public page has differing dismissal dates; no date has been used to infer the appeal outcome. Source: https://securities.stanford.edu/filings-case.html?id=104095. Restricted filings were not accessed.

CourtListener / Free Law Project live acquisition was blocked by human verification. No CourtListener records are represented as downloaded. Use the included `scripts/acquire.py` API importer with your own `COURTLISTENER_TOKEN`, then tag, validate, and review the staged opinions. The six real seed records are excerpts from separately linked public judicial sources, not a Free Law Project corpus import.
