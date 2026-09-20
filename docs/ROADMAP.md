# From local research workbench to production evidence platform

The delivered application is a local, IDE-editable implementation of decomposition review, comparison, matter persistence, corpus ingestion/review and descriptive cohort calibration. It ships with fictional demonstrations and a small, unreviewed real excerpt corpus. It is not a completed empirical database or a legally validated analysis service.

## 1. Establish the legal codebook

Have securities litigators review each factor, missing-data rule and circuit doctrine card. Add examples of present, absent, unknown, adverse and mixed treatment. Define the unit of analysis as a defendant/claim/complaint-version ruling, with stable links to its case, district motion and appeal. Opinion-level summaries cannot represent all of those distinctions. Add explicit per-factor dimensions (CW tenure, duties, firsthand source, defendant link; trade amount, holdings, baseline, plan dates; agency investigation versus adjudication) as validated structured fields rather than relying on free-text questions alone. Version every schema and migration.

Publish a review protocol and double-code a sample independently. Resolve disagreements with an adjudicator. Track agreement per dimension, not a single overall label. Counsel should review current statutes, later precedent and negative treatment; this seed's historical sources are not a live citator.

## 2. Build the public corpus with provenance

Obtain CourtListener credentials and appropriate access for the planned volume. The supplied CLI stages authenticated API responses but has not been run against a user's account. Define reproducible search and inclusion criteria across district courts in the Second and Ninth Circuits. Retrieve complete opinions, attachments and complaint versions; keep immutable originals, content hashes, acquisition timestamps, normalization maps and pinpoint offsets. Do not rely on search snippets or the bundled excerpts as complete source material.

Secure authorized Stanford SCAC data and a confirmed docket crosswalk. Store its case-level outcomes separately from scienter and MTD rulings. Track unsuccessful matches and ambiguous joins. Deduplicate amended opinions and related litigation without silently losing separate defendants or motions. Review retracted/changed opinions and subsequent treatment through a documented update process.

## 3. Validate extraction and retrieval

The default extractor is a conservative keyword draft. Its sentence-level ambiguity handling is not legal understanding. The optional LLM integration, if configured, also needs an evaluated tagging contract, model/version logging, bounded retries, cost controls and reviewed examples. Quote containment prevents invented strings but cannot establish a quote's correct speaker, issue, context or holding.

Run `python3 scripts/evaluate.py --out work/evaluation.json` after changes. `data/evaluation.json` records a development snapshot keyed to the engine's SHA-256. The authored fixtures repeat a small vocabulary and use generation-recipe labels; some paragraphs imply additional factors not explicit in the recipe. This makes the report useful for detecting rough edges, not a real-world accuracy estimate. Build an independently labeled, case-disjoint and time-separated holdout with explicit absence, contradictory sources, negation scope, OCR errors, multiple defendants and missing dates.

Evaluate factor precision/recall, abstention, evidence spans and attribution separately. Establish a litigator-rated analogous-case set and measure retrieval coverage and top-k relevance, including adverse comparators and circuit-specific exceptions. The current narrative component is lexical TF-IDF similarity. An embedding index or dedicated graph database is optional: compare it with this baseline before adding complexity. A graph-shaped relational store is not an installed graph/vector service. Neither embeddings nor larger models establish legal validity.

## 4. Make the statistical unit defensible

Do not interpret fictional labels or the six selected appellate precedents as population outcomes. Assemble a sufficiently large reviewed corpus under predeclared inclusion criteria, and display coverage, missingness and selection effects. Current suppression at twenty binary outcomes is a product safeguard, not a claim that twenty observations validate every combination. Wilson intervals describe binomial sampling uncertainty; they do not correct publication, selection, coding or dependence bias.

Keep grants/denials on scienter distinct from dismissals on materiality, loss causation, standing, safe harbor or other grounds. Show mixed, unresolved and leave-to-amend outcomes separately. Preserve chronology and appeal linkage. Examine whether case-level deduplication obscures defendant-specific decisions. Do not fit a predictive “scienter likelihood” output; report empirical comparisons with the numerator, denominator and cohort definition visible.

## 5. Harden for firm use

The current local server is a development workbench. Before storing client matters or deploying to a shared network, add authentication, firm/workspace authorization, durable reviewer identity, audit logs, backup/restore procedures, retention/deletion controls, encryption at rest and tested secrets handling. Apply firm policy before sending matter text to an external model. Review document uploads, input limits, dependency policies, hosting and data licensing with the intended operator.

Add reproducible database migrations, monitored ingestion jobs, job checkpoints, operational tests, concurrency/load testing and deployment configuration. Add complete document/PDF ingestion and citation exports only with source-offset preservation. Pin dependency and runtime versions when external providers or parsers are introduced.

## Acceptance milestone

A useful pilot is a reviewed, versioned codebook; a representative district-motion corpus with defensible outcome units; independently assessed extraction/retrieval quality; transparent cohort statistics; and a firm-approved deployment. Until those are in place, the implemented comparison workflow is a prototype for research and evaluation, with human review required throughout.
