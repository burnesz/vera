"""
Orquestração do experimento de recuperação do TCC VERA (Seção 2.1 da nota de avaliação).

Este módulo separa três responsabilidades:
1. Coleta: recuperadores (E5 denso, E5 + reranker, BM25) produzem rankings de chunks.
2. Persistência: cada rodada é salva em JSONL, para recalcular métricas sem consultar o Pinecone.
3. Análise: métricas por query, médias com IC por bootstrap e comparações pareadas.

Os scripts de linha de comando ficam em `scripts/run_retrieval_eval.py` e
`scripts/run_rewriting_eval.py`.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from evaluation import quantitative as q
from evaluation.bm25 import BM25Index

logger = logging.getLogger(__name__)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLD_PATH = os.path.join(ROOT, "evaluation", "data", "retrieval_gold.json")
DIALOGS_PATH = os.path.join(ROOT, "evaluation", "data", "rewriting_dialogs.json")
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
CACHE_DIR = os.path.join(RESULTS_DIR, "cache")

# Profundidade dos rankings salvos. Igual ao pool de candidatos do reranker em produção
# (PineconeVectorStore.search com rerank=True busca 25 candidatos).
CANDIDATE_DEPTH = 25
OPERATIONAL_K = 3  # top_k_context padrão do Chat e top_k do Feedback
PRIMARY_METRICS = ("hit@3", "mrr@10", "ndcg@10", "cp@3")
ALL_METRICS = ("hit@1", "hit@3", "hit@5", "hit@10", "mrr@10", "ndcg@10", "cp@3")

RetrieveFn = Callable[[str], List[Dict[str, Any]]]


# ---------------------------------------------------------------------------
# Gabarito
# ---------------------------------------------------------------------------

def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def chunk_counts(gold: Dict[str, Any]) -> Dict[str, int]:
    """Chunks no índice por unidade de relevância: documento ENEM_MAT_* ou segmento de apostila (gabarito 2.0)."""
    counts = {d["document_name"]: int(d["chunks_indexados"]) for d in gold["documentos"]}
    counts.update({s["id"]: int(s["chunks_indexados"]) for s in gold.get("segmentos", [])})
    return counts


# Página de origem do chunk, lida do id gerado na ingestão (ex.: mat_2024_p39_c163_74f8e3 -> 39).
_PAGE_IN_ID = re.compile(r"_p(\d+)_c\d+_")


def segment_index(gold: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Segmentos página-assunto das apostilas, agrupados por documento."""
    index: Dict[str, List[Dict[str, Any]]] = {}
    for s in gold.get("segmentos", []):
        index.setdefault(s["document_name"], []).append(s)
    return index


def expand_with_segments(relevantes: Dict[str, int], gold: Dict[str, Any]) -> Dict[str, int]:
    """
    Acrescenta aos julgamentos de uma query os segmentos de apostila: o grau de um segmento é o maior grau
    que a query dá aos tópicos (PDFs ENEM_MAT_*) que ele ensina. Segmentos de grau 0 ficam de fora.
    """
    expanded = dict(relevantes)
    for s in gold.get("segmentos", []):
        grade = max((int(relevantes.get(t, 0)) for t in s["topicos"]), default=0)
        if grade > 0:
            expanded[s["id"]] = grade
    return expanded


def without_segments(items: Sequence[Dict[str, Any]],
                     segments: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Itens só com os julgamentos por documento. Usado no cenário fechado (filtro nos ENEM_MAT_*): as apostilas
    não podem ser recuperadas ali e não devem entrar no ranking ideal do nDCG.
    """
    seg_ids = {s["id"] for ss in segments.values() for s in ss}
    return [{**it, "relevantes": {k: v for k, v in it["relevantes"].items() if k not in seg_ids}} for it in items]


def relevance_unit(hit: Dict[str, Any], segments: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> str:
    """
    Unidade de relevância de um chunk ranqueado: o segmento de páginas, se o documento for uma apostila
    segmentada; senão, o próprio documento. Página sem segmento vira uma unidade não julgada (grau 0).
    """
    doc = hit["document_name"]
    if not segments or doc not in segments:
        return doc
    page = hit.get("page_number")
    if page is None:
        m = _PAGE_IN_ID.search(hit.get("id", ""))
        page = int(m.group(1)) if m else None
    if page is not None:
        for s in segments[doc]:
            if s["pagina_inicial"] <= int(page) <= s["pagina_final"]:
                return s["id"]
    return f"{doc}#p{page}"


def gold_document_names(gold: Dict[str, Any]) -> List[str]:
    return [d["document_name"] for d in gold["documentos"]]


def size_bucket(n_chunks: int) -> str:
    if n_chunks <= 7:
        return "pequeno (<=7 chunks)"
    if n_chunks <= 20:
        return "medio (8-20 chunks)"
    return "grande (>20 chunks)"


def gold_items(gold: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Queries do gabarito com os atributos usados nos recortes."""
    docs = {d["document_name"]: d for d in gold["documentos"]}
    items = []
    for item in gold["queries"]:
        target = docs[item["topico_alvo"]]
        items.append({
            "id": item["id"],
            "query": item["query"],
            "relevantes": expand_with_segments(item["relevantes"], gold),
            "tipo": item["tipo"],
            "eixo": target["eixo_tematico"],
            "tamanho": size_bucket(int(target["chunks_indexados"])),
            "topico_alvo": item["topico_alvo"],
        })
    return items


# ---------------------------------------------------------------------------
# Corpus (para o BM25)
# ---------------------------------------------------------------------------

def _meta(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj.get("metadata") or {}
    return getattr(obj, "metadata", None) or {}


def fetch_namespace_chunks(index: Any, namespace: str, page_size: int = 100) -> List[Dict[str, Any]]:
    """Lê todos os chunks de um namespace (ids via list_paginated + fetch em lotes)."""
    ids: List[str] = []
    token: Optional[str] = None
    while True:
        kwargs = {"namespace": namespace, "limit": page_size}
        if token:
            kwargs["pagination_token"] = token
        page = index.list_paginated(**kwargs)
        ids.extend(v.id for v in page.vectors)
        pagination = getattr(page, "pagination", None)
        token = getattr(pagination, "next", None) if pagination else None
        if not token:
            break

    chunks: List[Dict[str, Any]] = []
    for start in range(0, len(ids), page_size):
        batch = ids[start:start + page_size]
        resp = index.fetch(ids=batch, namespace=namespace)
        vectors = resp.vectors if hasattr(resp, "vectors") else resp["vectors"]
        for vid in batch:
            vec = vectors.get(vid) if hasattr(vectors, "get") else vectors[vid]
            if vec is None:
                continue
            meta = _meta(vec)
            chunks.append({
                "id": vid,
                "document_name": meta.get("document_name", ""),
                "text": meta.get("text", ""),
            })
    chunks.sort(key=lambda c: c["id"])
    return chunks


def load_or_fetch_corpus(index: Any, namespace: str, refresh: bool = False) -> List[Dict[str, Any]]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"corpus_{namespace}.json")
    if os.path.exists(path) and not refresh:
        return load_json(path)["chunks"]
    logger.info(f"Baixando todos os chunks do namespace '{namespace}' para o BM25...")
    chunks = fetch_namespace_chunks(index, namespace)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"namespace": namespace, "baixado_em": datetime.now().isoformat(), "chunks": chunks},
                  fh, ensure_ascii=False)
    return chunks


# ---------------------------------------------------------------------------
# Recuperadores
# ---------------------------------------------------------------------------

def _hit(r: Dict[str, Any]) -> Dict[str, Any]:
    meta = r.get("metadata", {}) or {}
    return {"id": r["id"], "document_name": meta.get("document_name", ""), "score": float(r.get("score", 0.0)),
            "text": r.get("text", "")}


def make_dense_retriever(vector_store: Any, namespace: str, filter_dict: Optional[Dict[str, Any]]) -> RetrieveFn:
    """E5 denso, igual à produção (PineconeVectorStore.search sem rerank)."""
    def retrieve(query: str) -> List[Dict[str, Any]]:
        res = vector_store.search(query=query, namespace=namespace, top_k=CANDIDATE_DEPTH, filter_dict=filter_dict)
        return [_hit(r) for r in res]
    return retrieve


def make_rerank_retriever(vector_store: Any, namespace: str, filter_dict: Optional[Dict[str, Any]]) -> RetrieveFn:
    """
    E5 + CrossEncoder bge-reranker-v2-m3, mesmo procedimento de PineconeVectorStore.search(rerank=True):
    25 candidatos densos reordenados pelo CrossEncoder. Aqui o ranking completo é mantido
    (produção corta em 4) para permitir métricas até K = 10.
    """
    from app.services.vectorstore import get_cross_encoder

    def retrieve(query: str) -> List[Dict[str, Any]]:
        cands = [_hit(r) for r in vector_store.search(
            query=query, namespace=namespace, top_k=CANDIDATE_DEPTH, filter_dict=filter_dict)]
        if not cands:
            return cands
        scores = get_cross_encoder().predict([[query, c["text"]] for c in cands])
        for c, s in zip(cands, scores):
            c["dense_score"] = c["score"]
            c["score"] = float(s)
        return sorted(cands, key=lambda c: c["score"], reverse=True)
    return retrieve


def make_bm25_retriever(chunks: Sequence[Dict[str, Any]]) -> RetrieveFn:
    bm25 = BM25Index([c["text"] for c in chunks])

    def retrieve(query: str) -> List[Dict[str, Any]]:
        return [{"id": chunks[i]["id"], "document_name": chunks[i]["document_name"], "score": s}
                for i, s in bm25.top_k(query, CANDIDATE_DEPTH)]
    return retrieve


# ---------------------------------------------------------------------------
# Execução e persistência
# ---------------------------------------------------------------------------

def run_system(retrieve: RetrieveFn, items: Sequence[Dict[str, Any]], warmup: bool = True) -> List[Dict[str, Any]]:
    """Executa todas as queries, mede a latência e devolve os registros da rodada."""
    if warmup and items:
        retrieve(items[0]["query"])  # carrega modelos fora da medição de latência
    records = []
    for n, item in enumerate(items, start=1):
        t0 = time.perf_counter()
        hits = retrieve(item["query"])
        latency_ms = (time.perf_counter() - t0) * 1000
        records.append({
            "id": item["id"],
            "query": item["query"],
            "latency_ms": round(latency_ms, 2),
            "ranking": [{"rank": i, "id": h["id"], "document_name": h["document_name"],
                         "score": round(float(h["score"]), 6)} for i, h in enumerate(hits[:CANDIDATE_DEPTH], 1)],
        })
        if n % 20 == 0:
            logger.info(f"  {n}/{len(items)} queries")
    return records


def save_jsonl(path: str, records: Iterable[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "desconhecido"


def environment_info() -> Dict[str, Any]:
    """Condições da máquina, necessárias para interpretar a latência medida."""
    info: Dict[str, Any] = {"cpus": os.cpu_count()}
    try:
        info["carga_media_1_5_15min"] = [round(x, 2) for x in os.getloadavg()]
    except OSError:
        pass
    try:
        import torch
        info["torch_threads"] = torch.get_num_threads()
        info["cuda_disponivel"] = torch.cuda.is_available()
    except Exception:
        pass
    return info


def new_run_dir(prefix: str, frozen: bool) -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{prefix}-{stamp}" if frozen else f"piloto-{prefix}-{stamp}"
    path = os.path.join(RESULTS_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------

def per_query_metrics(
    records: Sequence[Dict[str, Any]], items: Sequence[Dict[str, Any]], counts: Dict[str, int],
    segments: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    by_id = {it["id"]: it for it in items}
    rows = []
    for rec in records:
        item = by_id[rec["id"]]
        units = [relevance_unit(h, segments) for h in rec["ranking"]]
        m = q.evaluate_ranking(units, item["relevantes"], counts)
        row = {k: v for k, v in item.items() if k not in ("relevantes", "query")}
        row.update(m)
        row["latency_ms"] = rec["latency_ms"]
        row["top1_document"] = units[0] if units else ""
        rows.append(row)
    return rows


def summarize(rows: Sequence[Dict[str, Any]], metrics: Sequence[str] = ALL_METRICS,
              n_resamples: int = 10_000, seed: int = 42) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n": len(rows)}
    for m in metrics:
        vals = [r[m] for r in rows]
        lo, hi = q.bootstrap_ci(vals, n_resamples=n_resamples, seed=seed)
        out[m] = {"media": q.mean(vals), "ic95": [lo, hi]}
    lat = [r["latency_ms"] for r in rows]
    out["latencia_ms"] = {"p50": q.percentile(lat, 50), "p95": q.percentile(lat, 95), "media": q.mean(lat)}
    return out


def summarize_by(rows: Sequence[Dict[str, Any]], key: str, metrics: Sequence[str] = PRIMARY_METRICS) -> Dict[str, Any]:
    """Recorte descritivo (sem teste de hipótese): média por grupo."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(str(r[key]), []).append(r)
    return {g: {"n": len(rs), **{m: q.mean([r[m] for r in rs]) for m in metrics}}
            for g, rs in sorted(groups.items())}


def compare_systems(
    rows_by_system: Dict[str, Sequence[Dict[str, Any]]],
    metrics: Sequence[str] = PRIMARY_METRICS,
    pairs: Optional[Sequence[tuple[str, str]]] = None,
    n_resamples: int = 10_000,
    seed: int = 42,
) -> List[Dict[str, Any]]:
    """
    Comparações pareadas por query: diferença média, IC por bootstrap da diferença,
    teste de aleatorização pareado, d_z e p ajustado por Holm na família inteira.
    """
    systems = list(rows_by_system)
    pairs = list(pairs) if pairs else list(combinations(systems, 2))
    results = []
    raw_p: Dict[str, float] = {}
    for a, b in pairs:
        ra = {r["id"]: r for r in rows_by_system[a]}
        rb = {r["id"]: r for r in rows_by_system[b]}
        ids = sorted(set(ra) & set(rb))
        for m in metrics:
            va = [ra[i][m] for i in ids]
            vb = [rb[i][m] for i in ids]
            diffs = [x - y for x, y in zip(va, vb)]
            lo, hi = q.bootstrap_ci(diffs, n_resamples=n_resamples, seed=seed)
            p = q.paired_permutation_test(va, vb, n_resamples=n_resamples, seed=seed)
            key = f"{a}|{b}|{m}"
            raw_p[key] = p
            results.append({
                "sistema_a": a, "sistema_b": b, "metrica": m, "n": len(ids),
                "media_a": q.mean(va), "media_b": q.mean(vb), "diferenca": q.mean(diffs),
                "ic95_diferenca": [lo, hi], "p_permutacao": p, "d_z": q.cohens_dz(va, vb),
                "_key": key,
            })
    adjusted = q.holm_bonferroni(raw_p)
    for r in results:
        r["p_holm"] = adjusted[r.pop("_key")]
    return results


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

def write_csv(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        return
    fields: List[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})


def _fmt(x: float, pct: bool = True) -> str:
    return f"{100 * x:.1f}" if pct else f"{x:.3f}"


def markdown_summary(summaries: Dict[str, Dict[str, Any]], metrics: Sequence[str] = ALL_METRICS) -> str:
    lines = ["| Sistema | n | " + " | ".join(metrics) + " | lat. p50 (ms) | lat. p95 (ms) |",
             "|---" * (len(metrics) + 4) + "|"]
    for name, s in summaries.items():
        cells = []
        for m in metrics:
            mm = s[m]
            cells.append(f"{_fmt(mm['media'])} [{_fmt(mm['ic95'][0])}; {_fmt(mm['ic95'][1])}]")
        lat = s["latencia_ms"]
        lines.append(f"| {name} | {s['n']} | " + " | ".join(cells) + f" | {lat['p50']:.0f} | {lat['p95']:.0f} |")
    return "\n".join(lines)


def markdown_breakdown(breakdowns: Dict[str, Dict[str, Any]], metrics: Sequence[str] = PRIMARY_METRICS) -> str:
    lines = ["| Sistema | Grupo | n | " + " | ".join(metrics) + " |", "|---" * (len(metrics) + 3) + "|"]
    for name, groups in breakdowns.items():
        for g, vals in groups.items():
            lines.append(f"| {name} | {g} | {vals['n']} | " + " | ".join(_fmt(vals[m]) for m in metrics) + " |")
    return "\n".join(lines)


def markdown_comparisons(comps: Sequence[Dict[str, Any]]) -> str:
    lines = ["| A | B | Métrica | A | B | Δ (A−B) | IC95% Δ | p perm. | p Holm | d_z |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for c in comps:
        lo, hi = c["ic95_diferenca"]
        lines.append(
            f"| {c['sistema_a']} | {c['sistema_b']} | {c['metrica']} | {_fmt(c['media_a'])} | {_fmt(c['media_b'])} | "
            f"{_fmt(c['diferenca'])} | [{_fmt(lo)}; {_fmt(hi)}] | {c['p_permutacao']:.4f} | {c['p_holm']:.4f} | "
            f"{c['d_z']:.2f} |")
    return "\n".join(lines)


@dataclass
class ExperimentReport:
    title: str
    manifest: Dict[str, Any]
    summaries: Dict[str, Dict[str, Any]]
    breakdowns: Dict[str, Dict[str, Dict[str, Any]]]  # recorte -> sistema -> grupo -> valores
    comparisons: Dict[str, List[Dict[str, Any]]]  # família -> comparações

    def to_markdown(self) -> str:
        parts = [f"# {self.title}", "",
                 f"- Gerado em: {self.manifest.get('gerado_em')}",
                 f"- Gabarito: versão {self.manifest.get('gabarito_versao')} "
                 f"(congelado: {self.manifest.get('gabarito_congelado')}, sha256 `{self.manifest.get('gabarito_sha256', '')[:12]}`)",
                 f"- Commit: `{self.manifest.get('git_commit', '')[:12]}`",
                 "", "Valores em %, com IC 95% por bootstrap entre colchetes. Unidade ranqueada: chunk.", "",
                 "## Resultados gerais", "", markdown_summary(self.summaries), ""]
        for recorte, data in self.breakdowns.items():
            parts += [f"## Recorte por {recorte} (descritivo)", "", markdown_breakdown(data), ""]
        for familia, comps in self.comparisons.items():
            parts += [f"## Comparações pareadas — {familia}", "",
                      "Teste de aleatorização pareado (10.000 permutações), p ajustado por Holm na família.", "",
                      markdown_comparisons(comps), ""]
        return "\n".join(parts)
