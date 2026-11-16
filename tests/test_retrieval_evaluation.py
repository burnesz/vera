"""Testes das métricas, da estatística e do BM25 do experimento de recuperação (sem rede)."""

import math

import pytest

from evaluation import quantitative as q
from evaluation import retrieval_experiment as rx
from evaluation.bm25 import BM25Index, tokenize


# --- Métricas -----------------------------------------------------------------

def test_hit_and_reciprocal_rank():
    grades = [0, 1, 2, 0]
    assert q.hit_at_k(grades, 2) == 0.0
    assert q.hit_at_k(grades, 3) == 1.0
    assert q.reciprocal_rank(grades, 10) == pytest.approx(1 / 3)
    assert q.reciprocal_rank([0, 0, 0], 10) == 0.0
    assert q.reciprocal_rank([0, 0, 2], 2) == 0.0  # acerto além do corte


def test_context_precision_counts_related_and_fixed_denominator():
    assert q.context_precision_at_k([2, 1, 0], 3) == pytest.approx(2 / 3)
    assert q.context_precision_at_k([2], 3) == pytest.approx(1 / 3)  # ranking curto


def test_ndcg_perfect_and_ideal_from_chunk_counts():
    rel = {"a.pdf": 2, "b.pdf": 1}
    ideal = q.ideal_grades(rel, {"a.pdf": 2, "b.pdf": 3})
    assert ideal == [2, 2, 1, 1, 1]
    assert q.ndcg_at_k(ideal, 10, ideal) == pytest.approx(1.0)
    worse = [1, 2, 2, 1, 1]
    assert 0 < q.ndcg_at_k(worse, 10, ideal) < 1
    assert q.ndcg_at_k([0, 0], 10, []) == 0.0


def test_evaluate_ranking_keys():
    m = q.evaluate_ranking(["x.pdf", "a.pdf"], {"a.pdf": 2}, {"a.pdf": 1})
    assert set(m) == {"hit@1", "hit@3", "hit@5", "hit@10", "mrr@10", "ndcg@10", "cp@3"}
    assert m["hit@1"] == 0.0 and m["hit@3"] == 1.0
    assert m["mrr@10"] == pytest.approx(0.5)
    assert m["ndcg@10"] == pytest.approx(1 / math.log2(3))


# --- Estatística --------------------------------------------------------------

def test_bootstrap_ci_contains_mean_and_is_deterministic():
    vals = [0, 1, 1, 0, 1, 1, 1, 0, 1, 1]
    lo, hi = q.bootstrap_ci(vals, n_resamples=2000, seed=1)
    assert lo <= q.mean(vals) <= hi
    assert (lo, hi) == q.bootstrap_ci(vals, n_resamples=2000, seed=1)


def test_permutation_test_identical_and_clear_difference():
    a = [1.0] * 30
    assert q.paired_permutation_test(a, a, n_resamples=500) == 1.0
    b = [0.0] * 30
    assert q.paired_permutation_test(a, b, n_resamples=2000) < 0.01


def test_cohens_dz_and_holm():
    assert q.cohens_dz([1, 2, 3], [0, 0, 0]) == pytest.approx(2.0)
    adj = q.holm_bonferroni({"x": 0.01, "y": 0.04, "z": 0.03})
    assert adj["x"] == pytest.approx(0.03)
    assert adj["z"] == pytest.approx(0.06)
    assert adj["y"] == pytest.approx(0.06)  # monotonicidade


def test_cohen_kappa_known_values():
    assert q.cohen_kappa([0, 1, 2, 2], [0, 1, 2, 2]) == pytest.approx(1.0)
    # 2x2: po = 0.7, pe = 0.7*0.6 + 0.3*0.4 = 0.54 -> kappa = 0.16 / 0.46
    r1 = [1] * 5 + [1] * 2 + [0] * 1 + [0] * 2
    r2 = [1] * 5 + [0] * 2 + [1] * 1 + [0] * 2
    assert q.cohen_kappa(r1, r2) == pytest.approx(0.16 / 0.46, abs=1e-9)
    assert q.cohen_kappa([0, 2], [1, 2], weights="linear") > q.cohen_kappa([0, 2], [1, 2])


# --- BM25 ---------------------------------------------------------------------

def test_tokenize_strips_accents_and_stopwords():
    assert tokenize("A Função Exponencial é crescente") == ["funcao", "exponencial", "crescente"]


def test_bm25_ranks_matching_document_first():
    idx = BM25Index(["o volume do cilindro", "a área do triângulo", "juros compostos e montante"])
    assert idx.top_k("como calcular o volume de um cilindro", 1)[0][0] == 0
    assert idx.top_k("montante com juros", 1)[0][0] == 2


# --- Integridade dos dados ----------------------------------------------------

def test_gold_integrity():
    gold = rx.load_json(rx.GOLD_PATH)
    names = set(rx.gold_document_names(gold))
    assert len(names) == len(gold["documentos"]) == 63
    ids = [qq["id"] for qq in gold["queries"]]
    assert len(ids) == len(set(ids)) == 126
    for qq in gold["queries"]:
        assert qq["relevantes"][qq["topico_alvo"]] == 2
        assert set(qq["relevantes"]) <= names
        assert set(qq["relevantes"].values()) <= {1, 2}
    assert {qq["tipo"] for qq in gold["queries"]} == {"direta", "contextual"}


def test_gold_segments_integrity():
    """Segmentos das apostilas: tópicos válidos, sem páginas repetidas e só fora dos ENEM_MAT_*."""
    gold = rx.load_json(rx.GOLD_PATH)
    names = set(rx.gold_document_names(gold))
    segs = gold["segmentos"]
    assert len({s["id"] for s in segs}) == len(segs)
    paginas = set()
    for s in segs:
        assert s["document_name"] not in names
        assert s["topicos"] and set(s["topicos"]) <= names
        assert s["pagina_inicial"] <= s["pagina_final"]
        for p in range(s["pagina_inicial"], s["pagina_final"] + 1):
            assert (s["document_name"], p) not in paginas
            paginas.add((s["document_name"], p))
    assert set(rx.chunk_counts(gold)) == names | {s["id"] for s in segs}


# --- Segmentos página-assunto (gabarito 2.0) ----------------------------------

GOLD_SEG = {
    "documentos": [{"document_name": "alvo.pdf", "chunks_indexados": 2},
                   {"document_name": "correlato.pdf", "chunks_indexados": 1}],
    "segmentos": [
        {"id": "apostila.pdf#p10-12", "document_name": "apostila.pdf", "pagina_inicial": 10, "pagina_final": 12,
         "topicos": ["alvo.pdf"], "chunks_indexados": 4},
        {"id": "apostila.pdf#p13-15", "document_name": "apostila.pdf", "pagina_inicial": 13, "pagina_final": 15,
         "topicos": ["correlato.pdf"], "chunks_indexados": 3},
        {"id": "apostila.pdf#p16-20", "document_name": "apostila.pdf", "pagina_inicial": 16, "pagina_final": 20,
         "topicos": ["outro.pdf"], "chunks_indexados": 5},
    ],
}


def test_expand_with_segments_takes_highest_topic_grade():
    rel = rx.expand_with_segments({"alvo.pdf": 2, "correlato.pdf": 1}, GOLD_SEG)
    assert rel["apostila.pdf#p10-12"] == 2
    assert rel["apostila.pdf#p13-15"] == 1
    assert "apostila.pdf#p16-20" not in rel  # segmento sobre outro tópico
    assert rx.chunk_counts(GOLD_SEG)["apostila.pdf#p10-12"] == 4


def test_relevance_unit_maps_page_to_segment():
    segs = rx.segment_index(GOLD_SEG)
    assert rx.relevance_unit({"id": "mat_2024_p11_c40_ab12cd", "document_name": "apostila.pdf"}, segs) \
        == "apostila.pdf#p10-12"
    assert rx.relevance_unit({"id": "x", "document_name": "apostila.pdf", "page_number": 14}, segs) \
        == "apostila.pdf#p13-15"
    assert rx.relevance_unit({"id": "mat_2024_p3_c1_ff", "document_name": "apostila.pdf"}, segs) == "apostila.pdf#p3"
    assert rx.relevance_unit({"id": "mat_x_p11_c1_ff", "document_name": "alvo.pdf"}, segs) == "alvo.pdf"
    assert rx.relevance_unit({"id": "mat_x_p11_c1_ff", "document_name": "apostila.pdf"}) == "apostila.pdf"


def test_metrics_credit_relevant_segment():
    """Um chunk da apostila na página do tópico-alvo conta como acerto; o de outra página, não."""
    item = {"id": "Q1", "query": "q", "relevantes": rx.expand_with_segments({"alvo.pdf": 2}, GOLD_SEG)}
    records = [{"id": "Q1", "latency_ms": 1.0, "ranking": [
        {"rank": 1, "id": "mat_2024_p17_c1_aa", "document_name": "apostila.pdf", "score": 0.9},
        {"rank": 2, "id": "mat_2024_p11_c2_bb", "document_name": "apostila.pdf", "score": 0.8}]}]
    row = rx.per_query_metrics(records, [item], rx.chunk_counts(GOLD_SEG), rx.segment_index(GOLD_SEG))[0]
    assert row["hit@1"] == 0.0 and row["hit@3"] == 1.0
    assert row["mrr@10"] == pytest.approx(0.5)
    assert row["top1_document"] == "apostila.pdf#p16-20"


def test_without_segments_keeps_only_document_judgments():
    """Cenário fechado: o ranking ideal não pode contar chunks de apostilas que nem podem ser recuperados."""
    item = {"id": "Q1", "relevantes": rx.expand_with_segments({"alvo.pdf": 2}, GOLD_SEG)}
    (fechado,) = rx.without_segments([item], rx.segment_index(GOLD_SEG))
    assert fechado["relevantes"] == {"alvo.pdf": 2}
    assert "apostila.pdf#p10-12" in item["relevantes"]  # o item original não é alterado


def test_dialogs_integrity():
    gold = rx.load_json(rx.GOLD_PATH)
    names = set(rx.gold_document_names(gold))
    data = rx.load_json(rx.DIALOGS_PATH)
    assert len(data["dialogos"]) >= 25
    for d in data["dialogos"]:
        assert d["topico_alvo"] in names
        assert d["relevantes"][d["topico_alvo"]] == 2
        assert [m["role"] for m in d["historico"]] == ["user", "assistant"]


# --- Pipeline de análise com recuperador falso --------------------------------

def test_pipeline_with_fake_retrievers():
    items = [
        {"id": "Q1", "query": "a", "relevantes": {"a.pdf": 2}, "tipo": "direta", "eixo": "E", "tamanho": "p"},
        {"id": "Q2", "query": "b", "relevantes": {"b.pdf": 2}, "tipo": "contextual", "eixo": "E", "tamanho": "p"},
    ]
    counts = {"a.pdf": 1, "b.pdf": 1}

    def perfect(query):
        return [{"id": f"{query}1", "document_name": f"{query}.pdf", "score": 1.0}]

    def wrong(query):
        return [{"id": "z1", "document_name": "z.pdf", "score": 1.0}]

    rows = {name: rx.per_query_metrics(rx.run_system(fn, items, warmup=False), items, counts)
            for name, fn in (("perfeito", perfect), ("errado", wrong))}
    s = rx.summarize(rows["perfeito"], n_resamples=200)
    assert s["hit@3"]["media"] == 1.0 and s["n"] == 2
    assert rx.summarize(rows["errado"], n_resamples=200)["mrr@10"]["media"] == 0.0
    comps = rx.compare_systems(rows, n_resamples=200)
    assert all(c["diferenca"] >= 0 for c in comps if c["metrica"] != "cp@3")
    assert "p_holm" in comps[0]
    by_tipo = rx.summarize_by(rows["perfeito"], "tipo")
    assert set(by_tipo) == {"direta", "contextual"}
