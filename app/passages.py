"""Explainable passage comparison, not a legal inference or citation generator.

Tags are keyword heuristics, not verified legal annotations. Character offsets refer
only to the exact stored source text, never to numbered judicial paragraphs.
"""
import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+", re.I)
_STOP = set("a an the and or of to in for on at by with from as is are was were be been that this it its they their not no but which who has have had would could should may must can we our court plaintiffs defendants plaintiff defendant".split())
_RULES = {
    "legal_roles": {
        "pleading_rule": (r"must (?:plead|allege|state)", r"pleading standard", r"strong inference", r"with particularity", r"reasonable person"),
        "factual_allegation": (r"alleg(?:es|ed|ation|ations)", r"complaint", r"according to", r"confidential witness"),
        "court_assessment": (r"we (?:conclude|hold|find|agree|reject)", r"(?:court|district court) (?:found|concluded|held)", r"insufficient", r"sufficient", r"fails? to"),
        "competing_inference": (r"competing inference", r"nonfraudulent", r"non-fraudulent", r"innocent explanation", r"opposing inference", r"plausible alternative"),
    },
    "actor_roles": {
        "CFO": (r"cfo", r"chief financial officer"),
        "CEO": (r"ceo", r"chief executive officer"),
        "board": (r"board", r"directors?"),
        "auditor": (r"auditors?",),
        "confidential_witness": (r"confidential witnesses?", r"confidential witness", r"cw\d*", r"former employees?"),
        "corporation": (r"corporation", r"company", r"corporate"),
    },
    "evidence_bases": {
        "firsthand": (r"firsthand", r"first-hand", r"personal knowledge", r"personally (?:observed|attended|heard|saw)"),
        "hearsay": (r"hearsay", r"secondhand", r"second-hand", r"was told", r"heard from"),
        "documents": (r"documents?", r"reports?", r"emails?", r"memorand(?:a|um)", r"internal records?"),
    },
}
_NEGATION = re.compile(r"\b(?:not|no|never|without|insufficient|fails?|failed|cannot|unable|lack(?:s|ed|ing)?)\b", re.I)


def _tokens(text):
    return [t.lower() for t in _TOKEN.findall(text) if t.lower() not in _STOP and len(t) > 1]


def _has(text, pattern):
    return bool(re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", text, re.I))


def _structure(text, taxonomy):
    # Normalize PDF line wrapping for matching only; stored quotations stay verbatim.
    text = re.sub(r'(?<=\w)-\s*\n\s*(?=\w)', '', text)
    text = re.sub(r'\s+', ' ', text)
    factors = taxonomy.get("factors", []) if isinstance(taxonomy, dict) else taxonomy
    result = {"factor_ids": [f["id"] for f in factors if any(_has(text, re.escape(k)) for k in f.get("keywords", []) if k)]}
    for dimension, labels in _RULES.items():
        result[dimension] = [label for label, patterns in labels.items() if any(_has(text, p) for p in patterns)]
    result["polarity"] = "negation_present" if _NEGATION.search(text) else "no_negation_detected"
    return result


def _spans(text, max_chars=1800):
    """Split on blank lines and sentence boundaries; every span is verbatim."""
    for paragraph in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", text, re.S):
        start, end = paragraph.span()
        while end - start > max_chars:
            window = text[start:start + max_chars]
            boundaries = list(re.finditer(r"[.!?][\"'’”)]*\s+", window))
            cut = start + boundaries[-1].end() if boundaries and boundaries[-1].end() > max_chars // 3 else start + max_chars
            # Prefer whitespace when a long sentence has no punctuation.
            if cut == start + max_chars:
                space = window.rfind(" ")
                if space > max_chars // 3:
                    cut = start + space
            span_end = cut
            while span_end > start and text[span_end - 1].isspace():
                span_end -= 1
            yield start, span_end
            start = cut
            while start < end and text[start].isspace():
                start += 1
        if start < end:
            yield start, end


def build_passages(documents, taxonomy):
    """Return JSON-safe passage records with heuristic structure and exact offsets.

    Each document requires id, name, circuit, source_url, text. Optional
    review_status and data_kind are copied unchanged; missing review status is
    'needs_review'. Full source authenticity remains the importer/reviewer's job.
    Taxonomy can be {'factors': [...]} or a factor list with id and keywords.
    """
    records = []
    for doc in documents:
        text = doc["text"]
        if not isinstance(text, str):
            raise ValueError("Document text must be a string")
        for start, end in _spans(text):
            excerpt = text[start:end]
            if len(_tokens(excerpt)) < 12:
                continue
            structure = _structure(excerpt, taxonomy)
            records.append({
                "id": f"{doc['id']}:{start}:{end}", "document_id": doc["id"],
                "name": doc["name"], "circuit": doc["circuit"],
                "source_url": doc["source_url"], "text": excerpt,
                "citation": doc.get("citation", ""), "date": doc.get("date", ""),
                "posture": doc.get("posture", "unknown"), "ocr_warning": doc.get("ocr_warning", False),
                "start": start, "end": end, "pinpoint": f"Stored text characters {start}–{end} (zero-based, end exclusive)",
                "review_status": doc.get("review_status", "needs_review"),
                "data_kind": doc.get("data_kind", "unknown"),
                "structure": structure,
                # Search can derive query factor tags without hidden global state.
                "factor_keywords": {f["id"]: f.get("keywords", []) for f in (taxonomy.get("factors", []) if isinstance(taxonomy, dict) else taxonomy)},
            })
    return records


def search_passages(query, passages, circuit=None, limit=12):
    """Rank exact passages by 70% structural overlap + 30% lexical cosine.

    Circuit is an exact optional filter. Results include scores, matching reasons,
    and explicit structural distinctions. Scores measure text similarity only;
    negation presence never determines what proposition a court accepted.
    """
    if not isinstance(query, str) or not query.strip():
        return []
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")
    candidates = [p for p in passages if circuit is None or p["circuit"] == circuit]
    if not candidates:
        return []
    keyword_map = {}
    for p in candidates:
        keyword_map.update(p.get("factor_keywords", {}))
    query_structure = _structure(query, [{"id": key, "keywords": value} for key, value in keyword_map.items()])
    qcounts = Counter(_tokens(query))
    dimensions = {"factor_ids": 4, "legal_roles": 2, "actor_roles": 1.5, "evidence_bases": 2}
    results = []
    for p in candidates:
        structure = p["structure"]
        numerator = denominator = 0.0
        reasons, distinctions = [], []
        for dimension, weight in dimensions.items():
            qset, pset = set(query_structure[dimension]), set(structure[dimension])
            if qset or pset:
                denominator += weight
                numerator += weight * len(qset & pset) / len(qset | pset)
            if qset & pset:
                reasons.append(f"Shared {dimension.replace('_', ' ')}: {', '.join(sorted(qset & pset))}")
            if qset - pset:
                distinctions.append(f"Query-only {dimension.replace('_', ' ')}: {', '.join(sorted(qset - pset))}")
            if pset - qset:
                distinctions.append(f"Passage-only {dimension.replace('_', ' ')}: {', '.join(sorted(pset - qset))}")
        structural = numerator / denominator if denominator else 0.0
        counts = Counter(_tokens(p["text"]))
        divisor = math.sqrt(sum(v*v for v in qcounts.values()) * sum(v*v for v in counts.values()))
        lexical = sum(v * counts[k] for k, v in qcounts.items()) / divisor if divisor else 0.0
        if not numerator and not lexical:
            continue
        if query_structure["polarity"] != structure["polarity"]:
            distinctions.append("Negation language differs; check which proposition is negated in context.")
        if lexical:
            reasons.append("Shared wording: " + ", ".join(sorted(set(qcounts) & set(counts))[:12]))
        result = {k: v for k, v in p.items() if k != "factor_keywords"}
        result.update(score=round(.7 * structural + .3 * lexical, 4), structural_score=round(structural, 4), lexical_score=round(lexical, 4), reasons=reasons, distinctions=distinctions, query_structure=query_structure,
                      method="Deterministic keyword tags and token cosine; similarity is not legal equivalence.")
        results.append(result)
    return sorted(results, key=lambda p: (-p["score"], str(p["document_id"]), p["start"]))[:limit]
