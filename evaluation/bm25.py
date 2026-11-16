"""
Baseline lexical Okapi BM25 (Robertson & Zaragoza, 2009) sobre os mesmos chunks do Pinecone.

Implementação própria e sem dependências, para não acrescentar bibliotecas ao projeto.
Parâmetros padrão k1 = 1.2 e b = 0.75 (os mesmos do Elasticsearch usado no BEIR).
Tokenização: minúsculas, remoção de acentos e de stopwords do português, sem stemming.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import Dict, List, Sequence

STOPWORDS_PT = set("""
a à ao aos as às até com como da das de dela dele deles do dos e é ela elas ele eles em entre
era essa esse esta este eu foi há isso isto já lhe mais mas me mesmo meu minha muito na nas
nem no nos nós num numa o os ou para pela pelas pelo pelos por qual quando que quem se sem
seu sua são também te tem ter um uma umas uns você vou ser está estão sobre cada pode podem
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


STOPWORDS_NORM = {strip_accents(w) for w in STOPWORDS_PT}


def tokenize(text: str) -> List[str]:
    norm = strip_accents(text.lower())
    return [t for t in _TOKEN_RE.findall(norm) if t not in STOPWORDS_NORM and len(t) > 1]


class BM25Index:
    def __init__(self, documents: Sequence[str], k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tfs: List[Counter] = [Counter(tokenize(d)) for d in documents]
        self.doc_lens = [sum(tf.values()) for tf in self.doc_tfs]
        self.n_docs = len(documents)
        self.avgdl = (sum(self.doc_lens) / self.n_docs) if self.n_docs else 0.0
        df: Counter = Counter()
        for tf in self.doc_tfs:
            df.update(tf.keys())
        # IDF com +1 dentro do log (variante Lucene), sempre não negativo.
        self.idf: Dict[str, float] = {
            t: math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5)) for t, n in df.items()
        }

    def scores(self, query: str) -> List[float]:
        q_terms = tokenize(query)
        out = [0.0] * self.n_docs
        for i, tf in enumerate(self.doc_tfs):
            norm = self.k1 * (1 - self.b + self.b * self.doc_lens[i] / self.avgdl) if self.avgdl else self.k1
            s = 0.0
            for t in q_terms:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            out[i] = s
        return out

    def top_k(self, query: str, k: int) -> List[tuple[int, float]]:
        """Índices e scores dos K melhores documentos (empate desfeito pela ordem do corpus)."""
        sc = self.scores(query)
        order = sorted(range(self.n_docs), key=lambda i: (-sc[i], i))
        return [(i, sc[i]) for i in order[:k]]
