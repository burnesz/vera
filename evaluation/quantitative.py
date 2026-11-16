"""
Métricas quantitativas de recuperação e testes estatísticos do TCC VERA (RN-AVAL01).

Funções puras, sem acesso a rede, para que o cálculo seja testável e reprodutível
a partir das rodadas salvas em `evaluation/results/`.

Convenções (ver docs/03-avaliacao-cientifica/baseline-e-metricas-tcc.md, Seção 2.1):
- A unidade ranqueada é o *chunk*, porque é o que chega ao prompt do LLM.
- Cada chunk herda o grau de relevância da sua unidade: o PDF de origem (`metadata.document_name`) ou, nas
  apostilas, o segmento de páginas com o mesmo assunto (gabarito 2.0, ver retrieval_experiment.relevance_unit):
  2 = documento-alvo, 1 = correlato, 0 = não relevante ou não julgado.
- Hit Rate, MRR e o numerador do nDCG consideram "acerto" o grau 2.
- nDCG usa ganho linear (rel / log2(i + 1)), como o trec_eval e o BEIR.
"""

from __future__ import annotations

import math
import random
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

TARGET_GRADE = 2
RELATED_GRADE = 1


# ---------------------------------------------------------------------------
# Relevância
# ---------------------------------------------------------------------------

def grades_for_ranking(document_names: Sequence[str], relevantes: Mapping[str, int]) -> List[int]:
    """Converte a lista ranqueada de chunks (por nome do PDF) em graus de relevância."""
    return [int(relevantes.get(name, 0)) for name in document_names]


def ideal_grades(relevantes: Mapping[str, int], chunk_counts: Mapping[str, int]) -> List[int]:
    """
    Ranking ideal da query: todos os chunks julgados, ordenados por grau.
    Cada PDF contribui com tantos chunks quantos existem no índice.
    """
    grades: List[int] = []
    for name, grade in relevantes.items():
        if grade > 0:
            grades.extend([int(grade)] * int(chunk_counts.get(name, 1)))
    return sorted(grades, reverse=True)


# ---------------------------------------------------------------------------
# Métricas por query
# ---------------------------------------------------------------------------

def hit_at_k(grades: Sequence[int], k: int, min_grade: int = TARGET_GRADE) -> float:
    """Success@K: 1 se algum dos K primeiros chunks vem de um documento com grau >= min_grade."""
    return 1.0 if any(g >= min_grade for g in grades[:k]) else 0.0


def reciprocal_rank(grades: Sequence[int], k: int = 10, min_grade: int = TARGET_GRADE) -> float:
    """1 / posição do primeiro acerto até K; 0 se não houver acerto."""
    for i, g in enumerate(grades[:k], start=1):
        if g >= min_grade:
            return 1.0 / i
    return 0.0


def context_precision_at_k(grades: Sequence[int], k: int, min_grade: int = RELATED_GRADE) -> float:
    """
    Fração dos K chunks entregues ao LLM vindos de documento com grau >= min_grade.
    Posições não preenchidas contam como não relevantes (denominador fixo em K).
    """
    if k <= 0:
        return 0.0
    return sum(1 for g in grades[:k] if g >= min_grade) / k


def precision_at_k(grades: Sequence[int], k: int, min_grade: int = TARGET_GRADE) -> float:
    """
    Precisão@K: fração dos K primeiros chunks vindos de uma unidade com grau >= min_grade (padrão: grau 2, alvo).
    Difere do CP@K, que aceita também os correlatos (grau 1). Denominador fixo em K.
    """
    if k <= 0:
        return 0.0
    return sum(1 for g in grades[:k] if g >= min_grade) / k


def recall_at_k(units: Sequence[str], relevantes: Mapping[str, int], k: int, min_grade: int = TARGET_GRADE) -> float:
    """
    Revocação@K: fração das unidades relevantes da query (documentos ou segmentos de apostila com grau >= min_grade)
    que aparecem entre os K primeiros chunks. Vários chunks da mesma unidade contam uma vez.
    """
    alvo = {u for u, g in relevantes.items() if g >= min_grade}
    if not alvo:
        return 0.0
    return len(alvo & set(units[:k])) / len(alvo)


def dcg_at_k(grades: Sequence[int], k: int) -> float:
    return sum(g / math.log2(i + 1) for i, g in enumerate(grades[:k], start=1))


def ndcg_at_k(grades: Sequence[int], k: int, ideal: Sequence[int]) -> float:
    idcg = dcg_at_k(ideal, k)
    return dcg_at_k(grades, k) / idcg if idcg > 0 else 0.0


def evaluate_ranking(
    document_names: Sequence[str],
    relevantes: Mapping[str, int],
    chunk_counts: Mapping[str, int],
    hit_ks: Iterable[int] = (1, 3, 5, 10),
    mrr_k: int = 10,
    ndcg_k: int = 10,
    cp_k: int = 3,
    pr_ks: Iterable[int] = (3, 10),
) -> Dict[str, float]:
    """Calcula todas as métricas de uma query a partir do ranking de chunks."""
    grades = grades_for_ranking(document_names, relevantes)
    metrics = {f"hit@{k}": hit_at_k(grades, k) for k in hit_ks}
    metrics[f"mrr@{mrr_k}"] = reciprocal_rank(grades, mrr_k)
    metrics[f"ndcg@{ndcg_k}"] = ndcg_at_k(grades, ndcg_k, ideal_grades(relevantes, chunk_counts))
    metrics[f"cp@{cp_k}"] = context_precision_at_k(grades, cp_k)
    for k in pr_ks:  # Precisão@K e Revocação@K, prometidas na metodologia da monografia
        metrics[f"p@{k}"] = precision_at_k(grades, k)
        metrics[f"r@{k}"] = recall_at_k(document_names, relevantes, k)
    return metrics


# ---------------------------------------------------------------------------
# Estatística descritiva e inferencial
# ---------------------------------------------------------------------------

def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def percentile(values: Sequence[float], q: float) -> float:
    """Percentil com interpolação linear (q em [0, 100])."""
    if not values:
        return float("nan")
    s = sorted(values)
    pos = (len(s) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def bootstrap_ci(
    values: Sequence[float], n_resamples: int = 10_000, alpha: float = 0.05, seed: int = 42
) -> tuple[float, float]:
    """IC percentil por bootstrap das queries (reamostragem com reposição)."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(n_resamples))
    return (percentile(means, 100 * alpha / 2), percentile(means, 100 * (1 - alpha / 2)))


def paired_permutation_test(
    a: Sequence[float], b: Sequence[float], n_resamples: int = 10_000, seed: int = 42
) -> float:
    """
    Teste de aleatorização pareado bilateral (troca aleatória de sinal das diferenças).
    Recomendado por Smucker, Allan & Carterette (2007) para avaliação em RI.
    Retorna o p-valor com correção +1 (Phipson & Smyth, 2010).
    """
    if len(a) != len(b):
        raise ValueError("As amostras pareadas devem ter o mesmo tamanho.")
    diffs = [x - y for x, y in zip(a, b)]
    if not diffs or all(d == 0 for d in diffs):
        return 1.0
    observed = abs(sum(diffs))
    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_resamples):
        s = sum(d if rng.random() < 0.5 else -d for d in diffs)
        if abs(s) >= observed - 1e-12:
            extreme += 1
    return (extreme + 1) / (n_resamples + 1)


def cohens_dz(a: Sequence[float], b: Sequence[float]) -> float:
    """Tamanho de efeito pareado: média das diferenças / desvio padrão das diferenças."""
    diffs = [x - y for x, y in zip(a, b)]
    n = len(diffs)
    if n < 2:
        return float("nan")
    m = sum(diffs) / n
    var = sum((d - m) ** 2 for d in diffs) / (n - 1)
    if var <= 1e-12:  # diferenças constantes: efeito indefinido (resíduo de ponto flutuante)
        return 0.0 if abs(m) <= 1e-12 else math.copysign(float("inf"), m)
    return m / math.sqrt(var)


def holm_bonferroni(pvalues: Mapping[str, float]) -> Dict[str, float]:
    """Ajuste de Holm-Bonferroni para comparações múltiplas (p-valores ajustados)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted: Dict[str, float] = {}
    running = 0.0
    for i, (key, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[key] = running
    return adjusted


def cohen_kappa(r1: Sequence[int], r2: Sequence[int], weights: Optional[str] = None) -> float:
    """
    Kappa de Cohen entre dois anotadores. `weights="linear"` dá o kappa ponderado
    linear, apropriado para a escala ordinal 0/1/2.
    """
    if len(r1) != len(r2) or not r1:
        raise ValueError("As anotações devem ter o mesmo tamanho e não podem ser vazias.")
    cats = sorted(set(r1) | set(r2))
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    if k == 1:
        return 1.0
    n = len(r1)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(r1, r2):
        obs[idx[x]][idx[y]] += 1 / n
    row = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i: int, j: int) -> float:
        if weights == "linear":
            return abs(cats[i] - cats[j]) / (max(cats) - min(cats))
        return 0.0 if i == j else 1.0

    observed = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    expected = sum(w(i, j) * row[i] * col[j] for i in range(k) for j in range(k))
    return 1.0 - observed / expected if expected > 0 else 1.0
