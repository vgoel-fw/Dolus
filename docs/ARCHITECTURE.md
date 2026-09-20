# Architecture

The dependency-free local application uses Python's HTTP server and SQLite, with a vanilla JavaScript ES module frontend. Start with `python3 -m app.server`. This is a local single-user application, not a production multi-tenant service.

## Flow

1. Input text and explicit circuit, posture, defendant scope, and corpus mode.
2. Deterministic draft or explicit opt-in LLM extraction into the fixed taxonomy.
3. Attorney reviews unknown/present/absent statuses, specificity, and anchored passages.
4. Eligible reviewed cases are filtered by mode, posture and defendant scope. Other-circuit retrieval is optional; same-circuit results come first.
5. Ranking combines 80% weighted factor agreement and 20% TF-IDF narrative cosine similarity. Unknowns earn no agreement credit.
6. A separate whole-corpus cohort requires every present factor in the same circuit/posture/scope. Repeated opinions share case_id; contradictory outcomes collapse to mixed. Only scienter-basis records enter counts; rates require 20 binary outcomes.

## Storage and provenance

SQLite tables store case documents, evidence edges, narrative term vectors, saved matters, and review audit records. `/api/graph` exposes case→factor→outcome relationships with evidence. Vectors are a transparent lexical baseline; there is no external graph/vector service. Source records retain opinion text, locators, source URLs and excerpt coverage. Case-level SCAC linkage remains a separate review queue.

Imports are atomic, reject duplicate identities, validate source quotes, and reset review. Human review must attest to external source verification. This is an attestation, not independent authentication or automatic legal validation. Source text can contain false statements; substring checks cannot prove source authenticity.

## Security boundaries

The HTTP server binds to 127.0.0.1, restricts Host headers and cross-origin writes, requires JSON mutations, caps request bodies, prevents static-file path traversal, and sends CSP/nosniff/frame-denial headers. UI text is escaped and external links restricted to HTTP(S). API keys are server-side and matter text is not logged. Files/database are not encrypted by this application. Anyone with local machine/database access can access them. No authorization system, user accounts, TLS termination, hosted deployment, or production hardening is claimed.

## API

See CONTRACT.md. Additional `GET /api/graph` returns nodes/edges. Real review needs `{reviewer, note, source_verified: true}`. Known user factors require a supporting exact source quote. Errors use `{error}`. Matters are local snapshots; saving again creates another record. JSON/Markdown exports contain the submitted input and should be handled as matter material when using real client inputs.
