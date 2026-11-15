"""sentence encoders for the semantic half of the signal detector.

default is a local hashed concept encoder: stems + legal concept clusters + bigrams
hashed into a fixed space. no network, no deps, deterministic. it's a stand-in for a
neural encoder, not one. set DOLUS_ENCODER=sbert:<model name> to use a real
sentence-transformers model if that package is installed.
"""
import math
import os
import re
import zlib

DIM = 4096
_WORD = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
_STOP = set('a an the and or of to in for on at by with from as is are was were be been being that this these those it its he she they them his her their him not no but which who whom has have had would could should may might must can will shall do does did so than then there here into about over under such any each all some very also only'.split())
_SUFFIX = ('ingly', 'edly', 'ation', 'ments', 'ment', 'ings', 'ing', 'ied', 'ies', 'ed', 'es', 'ly', 's')

# concept clusters, keyed by stem prefix. lets "unloaded" and "sold" or "overlooked" and
# "ignored" land near each other, which plain tf-idf can't do
CONCEPTS = {
    'AVOID': ['avoid', 'ignor', 'disregard', 'overlook', 'blind', 'deniab', 'refus', 'declin', 'evad', 'dodg', 'shield', 'insulat'],
    'WARN': ['warn', 'flag', 'alert', 'concern', 'complained', 'whistleblow', 'escalat', 'caution', 'objection'],
    'KNOW': ['knew', 'know', 'aware', 'understood', 'realiz', 'recogniz', 'learn', 'inform', 'told', 'notif', 'suspect', 'belie'],
    'SELL': ['sold', 'sell', 'sale', 'unload', 'dump', 'liquidat', 'divest', 'cash', 'exercis', 'trade', 'trading'],
    'DISCLOSE': ['disclos', 'announc', 'reveal', 'restat', 'correct', 'admit', 'releas'],
    'DROP': ['fell', 'drop', 'declin', 'plung', 'plummet', 'collaps', 'tumbl', 'crash'],
    'HIDE': ['conceal', 'hid', 'hide', 'delet', 'destroy', 'shred', 'wipe', 'backdat', 'falsif', 'alter', 'mislead', 'misled', 'secret'],
    'NEAR': ['before', 'eve', 'shortly', 'prior', 'ahead', 'immediat', 'days', 'weeks', 'just'],
    'LEAVE': ['resign', 'depart', 'fire', 'fired', 'terminat', 'oust', 'quit', 'left', 'step', 'replac'],
    'DOC': ['report', 'memo', 'dashboard', 'data', 'email', 'minute', 'present', 'spreadsheet', 'forecast', 'record'],
    'SAY': ['stat', 'assur', 'represent', 'reaffirm', 'reiterat', 'tout', 'guidanc', 'call', 'press', 'say', 'said', 'claim', 'promis'],
    'PAY': ['bonus', 'compens', 'incentiv', 'option', 'payout', 'award', 'equity', 'grant'],
    'PLAN': ['plan', '10b5'],
    'AUDIT': ['audit', 'accountant', 'controller', 'gatekeep'],
    'PERIOD': ['quarter', 'period', 'year-end', 'fiscal', 'month-end'],
    'INTENT': ['intent', 'deliberat', 'conscious', 'knowing', 'reckless', 'willful', 'scienter', 'purpos'],
    'EXEC': ['cfo', 'ceo', 'coo', 'officer', 'executiv', 'director', 'president', 'founder', 'management'],
    'INACT': ['fail', 'nothing', 'never', 'inaction', 'neglect'],
}
_CONCEPT_OF = sorted(((p, c) for c, ps in CONCEPTS.items() for p in ps), key=lambda x: -len(x[0]))


def stem(word):
    for suf in _SUFFIX:
        if len(word) > len(suf) + 2 and word.endswith(suf):
            return word[:-len(suf)]
    return word


def concepts(word):
    return [c for p, c in _CONCEPT_OF if word.startswith(p)][:2]


def _bucket(feature):
    h = zlib.crc32(feature.encode())
    return h % DIM, (1.0 if (h >> 31) & 1 else -1.0)


class HashingEncoder:
    name = 'local-hashed-concepts'
    threshold = 0.45  # semantic_only cutoff. 98th pct of real opinion sentences sits ~0.2

    def encode_one(self, text):
        words = [w for w in _WORD.findall(text.lower()) if w not in _STOP]
        stems = [stem(w) for w in words]
        feats = {}
        def add(f, w):
            i, sign = _bucket(f)
            feats[i] = feats.get(i, 0.0) + sign * w
        for w, s in zip(words, stems):
            add('w:' + s, 1.0)
            for c in concepts(w):
                add('c:' + c, 1.6)
        for a, b in zip(stems, stems[1:]):
            add('b:' + a + '_' + b, 0.6)
        norm = math.sqrt(sum(v * v for v in feats.values()))
        return {k: v / norm for k, v in feats.items()} if norm else {}

    def encode(self, texts):
        return [self.encode_one(t) for t in texts]

    @staticmethod
    def cosine(a, b):
        if len(a) > len(b):
            a, b = b, a
        return max(0.0, sum(v * b.get(k, 0.0) for k, v in a.items()))


class SentenceTransformerEncoder:
    threshold = 0.50

    def __init__(self, model):
        from sentence_transformers import SentenceTransformer  # optional dependency
        self.model = SentenceTransformer(model)
        self.name = 'sbert:' + model

    def encode(self, texts):
        return [list(map(float, v)) for v in self.model.encode(list(texts), normalize_embeddings=True)]

    def encode_one(self, text):
        return self.encode([text])[0]

    @staticmethod
    def cosine(a, b):
        return max(0.0, sum(x * y for x, y in zip(a, b)))


_cached = None


def get_encoder():
    global _cached
    if _cached is None:
        spec = os.getenv('DOLUS_ENCODER', '')
        if spec.startswith('sbert:'):
            try:
                _cached = SentenceTransformerEncoder(spec[6:])
            except Exception:
                _cached = HashingEncoder()  # package or model missing, stay local
        else:
            _cached = HashingEncoder()
    return _cached
