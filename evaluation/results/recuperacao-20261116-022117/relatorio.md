# Experimento 1 — Recuperação em materiais_didaticos

- Gerado em: 2026-11-16T02:21:17
- Gabarito: versão 1.0 (congelado: True, sha256 `e67bb96b3f47`)
- Commit: `f6a427631ee3`

Valores em %, com IC 95% por bootstrap entre colchetes. Unidade ranqueada: chunk.

## Resultados gerais

| Sistema | n | hit@1 | hit@3 | hit@5 | hit@10 | mrr@10 | ndcg@10 | cp@3 | lat. p50 (ms) | lat. p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| fechado/e5_denso | 126 | 69.8 [61.9; 77.8] | 81.0 [73.8; 87.3] | 84.9 [78.6; 91.3] | 89.7 [84.1; 94.4] | 76.3 [69.5; 82.8] | 62.6 [57.3; 67.8] | 73.8 [67.5; 79.9] | 273 | 557 |
| fechado/e5_rerank | 126 | 77.0 [69.0; 84.1] | 84.9 [78.6; 91.3] | 87.3 [81.0; 92.9] | 90.5 [84.9; 95.2] | 81.4 [74.9; 87.4] | 65.3 [60.0; 70.3] | 77.5 [71.7; 83.1] | 1721 | 2471 |
| fechado/bm25 | 126 | 60.3 [51.6; 69.0] | 78.6 [71.4; 85.7] | 81.0 [73.8; 87.3] | 86.5 [80.2; 92.1] | 70.1 [63.1; 76.9] | 55.3 [50.0; 60.4] | 68.0 [61.9; 74.1] | 1 | 1 |
| completo/e5_denso | 126 | 51.6 [42.9; 60.3] | 61.1 [52.4; 69.8] | 68.3 [59.5; 76.2] | 72.2 [64.3; 80.2] | 58.2 [50.2; 66.1] | 40.7 [34.9; 46.4] | 48.7 [41.5; 55.8] | 274 | 318 |
| completo/e5_rerank | 126 | 53.2 [44.4; 61.9] | 66.7 [58.7; 74.6] | 70.6 [62.7; 78.6] | 73.8 [65.9; 81.0] | 60.5 [52.7; 68.2] | 41.9 [36.2; 47.6] | 50.5 [43.4; 57.4] | 2239 | 2924 |
| completo/bm25 | 126 | 37.3 [28.6; 46.0] | 56.3 [47.6; 65.1] | 66.7 [57.9; 74.6] | 76.2 [69.0; 83.3] | 49.4 [42.2; 56.6] | 34.0 [29.1; 39.1] | 39.9 [33.3; 46.8] | 4 | 6 |

## Recorte por tipo de query (descritivo)

| Sistema | Grupo | n | hit@3 | mrr@10 | ndcg@10 | cp@3 |
|---|---|---|---|---|---|---|
| fechado/e5_denso | contextual | 63 | 63.5 | 57.4 | 44.8 | 57.1 |
| fechado/e5_denso | direta | 63 | 98.4 | 95.1 | 80.3 | 90.5 |
| fechado/e5_rerank | contextual | 63 | 71.4 | 66.3 | 49.6 | 63.5 |
| fechado/e5_rerank | direta | 63 | 98.4 | 96.4 | 80.9 | 91.5 |
| fechado/bm25 | contextual | 63 | 63.5 | 54.4 | 39.8 | 52.4 |
| fechado/bm25 | direta | 63 | 93.7 | 85.9 | 70.7 | 83.6 |
| completo/e5_denso | contextual | 63 | 30.2 | 25.9 | 16.3 | 19.6 |
| completo/e5_denso | direta | 63 | 92.1 | 90.4 | 65.0 | 77.8 |
| completo/e5_rerank | contextual | 63 | 39.7 | 33.6 | 20.9 | 28.0 |
| completo/e5_rerank | direta | 63 | 93.7 | 87.4 | 63.0 | 73.0 |
| completo/bm25 | contextual | 63 | 44.4 | 35.9 | 20.3 | 26.5 |
| completo/bm25 | direta | 63 | 68.3 | 62.9 | 47.7 | 53.4 |

## Recorte por eixo temático (descritivo)

| Sistema | Grupo | n | hit@3 | mrr@10 | ndcg@10 | cp@3 |
|---|---|---|---|---|---|---|
| fechado/e5_denso | Combinatória, estatística e probabilidade | 24 | 87.5 | 77.0 | 67.1 | 81.9 |
| fechado/e5_denso | Geometria e trigonometria | 42 | 73.8 | 70.2 | 55.8 | 69.8 |
| fechado/e5_denso | Grandezas e medidas | 10 | 100.0 | 100.0 | 76.2 | 86.7 |
| fechado/e5_denso | Lógica | 4 | 100.0 | 87.5 | 89.6 | 100.0 |
| fechado/e5_denso | Matemática financeira | 10 | 100.0 | 100.0 | 85.4 | 93.3 |
| fechado/e5_denso | Números e operações | 18 | 72.2 | 74.7 | 55.1 | 57.4 |
| fechado/e5_denso | Álgebra e funções | 18 | 72.2 | 62.0 | 53.6 | 64.8 |
| fechado/e5_rerank | Combinatória, estatística e probabilidade | 24 | 83.3 | 82.7 | 68.0 | 84.7 |
| fechado/e5_rerank | Geometria e trigonometria | 42 | 78.6 | 78.0 | 60.5 | 76.2 |
| fechado/e5_rerank | Grandezas e medidas | 10 | 100.0 | 93.3 | 80.9 | 83.3 |
| fechado/e5_rerank | Lógica | 4 | 100.0 | 87.5 | 89.8 | 100.0 |
| fechado/e5_rerank | Matemática financeira | 10 | 100.0 | 100.0 | 88.3 | 96.7 |
| fechado/e5_rerank | Números e operações | 18 | 88.9 | 78.7 | 55.4 | 66.7 |
| fechado/e5_rerank | Álgebra e funções | 18 | 77.8 | 71.9 | 55.6 | 63.0 |
| fechado/bm25 | Combinatória, estatística e probabilidade | 24 | 70.8 | 64.9 | 52.9 | 70.8 |
| fechado/bm25 | Geometria e trigonometria | 42 | 78.6 | 68.1 | 53.7 | 68.3 |
| fechado/bm25 | Grandezas e medidas | 10 | 90.0 | 86.4 | 65.6 | 73.3 |
| fechado/bm25 | Lógica | 4 | 100.0 | 87.5 | 89.9 | 100.0 |
| fechado/bm25 | Matemática financeira | 10 | 100.0 | 95.0 | 76.6 | 86.7 |
| fechado/bm25 | Números e operações | 18 | 72.2 | 65.3 | 43.2 | 55.6 |
| fechado/bm25 | Álgebra e funções | 18 | 72.2 | 60.2 | 48.7 | 55.6 |
| completo/e5_denso | Combinatória, estatística e probabilidade | 24 | 58.3 | 54.2 | 37.8 | 45.8 |
| completo/e5_denso | Geometria e trigonometria | 42 | 64.3 | 57.6 | 36.6 | 46.8 |
| completo/e5_denso | Grandezas e medidas | 10 | 80.0 | 80.0 | 59.7 | 70.0 |
| completo/e5_denso | Lógica | 4 | 100.0 | 87.5 | 75.2 | 91.7 |
| completo/e5_denso | Matemática financeira | 10 | 70.0 | 63.7 | 49.1 | 53.3 |
| completo/e5_denso | Números e operações | 18 | 55.6 | 57.0 | 35.6 | 42.6 |
| completo/e5_denso | Álgebra e funções | 18 | 38.9 | 44.3 | 36.1 | 38.9 |
| completo/e5_rerank | Combinatória, estatística e probabilidade | 24 | 75.0 | 66.0 | 41.9 | 52.8 |
| completo/e5_rerank | Geometria e trigonometria | 42 | 61.9 | 55.9 | 35.6 | 46.8 |
| completo/e5_rerank | Grandezas e medidas | 10 | 80.0 | 73.3 | 62.8 | 66.7 |
| completo/e5_rerank | Lógica | 4 | 100.0 | 87.5 | 85.5 | 100.0 |
| completo/e5_rerank | Matemática financeira | 10 | 80.0 | 74.4 | 52.7 | 56.7 |
| completo/e5_rerank | Números e operações | 18 | 61.1 | 55.7 | 36.8 | 44.4 |
| completo/e5_rerank | Álgebra e funções | 18 | 50.0 | 47.7 | 34.7 | 38.9 |
| completo/bm25 | Combinatória, estatística e probabilidade | 24 | 45.8 | 44.0 | 32.5 | 38.9 |
| completo/bm25 | Geometria e trigonometria | 42 | 47.6 | 38.9 | 26.2 | 27.8 |
| completo/bm25 | Grandezas e medidas | 10 | 80.0 | 81.1 | 57.6 | 66.7 |
| completo/bm25 | Lógica | 4 | 100.0 | 75.0 | 80.9 | 91.7 |
| completo/bm25 | Matemática financeira | 10 | 90.0 | 80.3 | 52.3 | 63.3 |
| completo/bm25 | Números e operações | 18 | 55.6 | 52.3 | 28.6 | 33.3 |
| completo/bm25 | Álgebra e funções | 18 | 50.0 | 37.7 | 25.9 | 37.0 |

## Recorte por tamanho do documento (descritivo)

| Sistema | Grupo | n | hit@3 | mrr@10 | ndcg@10 | cp@3 |
|---|---|---|---|---|---|---|
| fechado/e5_denso | grande (>20 chunks) | 42 | 95.2 | 90.1 | 75.8 | 86.5 |
| fechado/e5_denso | medio (8-20 chunks) | 42 | 71.4 | 63.9 | 55.7 | 69.0 |
| fechado/e5_denso | pequeno (<=7 chunks) | 42 | 76.2 | 74.8 | 56.2 | 65.9 |
| fechado/e5_rerank | grande (>20 chunks) | 42 | 95.2 | 93.5 | 81.4 | 92.9 |
| fechado/e5_rerank | medio (8-20 chunks) | 42 | 78.6 | 70.1 | 55.5 | 69.8 |
| fechado/e5_rerank | pequeno (<=7 chunks) | 42 | 81.0 | 80.6 | 58.8 | 69.8 |
| fechado/bm25 | grande (>20 chunks) | 42 | 88.1 | 83.2 | 67.0 | 78.6 |
| fechado/bm25 | medio (8-20 chunks) | 42 | 69.0 | 56.4 | 48.3 | 62.7 |
| fechado/bm25 | pequeno (<=7 chunks) | 42 | 78.6 | 70.8 | 50.5 | 62.7 |
| completo/e5_denso | grande (>20 chunks) | 42 | 69.0 | 64.4 | 50.3 | 56.3 |
| completo/e5_denso | medio (8-20 chunks) | 42 | 50.0 | 48.6 | 36.7 | 44.4 |
| completo/e5_denso | pequeno (<=7 chunks) | 42 | 64.3 | 61.5 | 35.0 | 45.2 |
| completo/e5_rerank | grande (>20 chunks) | 42 | 78.6 | 73.6 | 54.1 | 60.3 |
| completo/e5_rerank | medio (8-20 chunks) | 42 | 52.4 | 45.6 | 35.6 | 44.4 |
| completo/e5_rerank | pequeno (<=7 chunks) | 42 | 69.0 | 62.3 | 36.2 | 46.8 |
| completo/bm25 | grande (>20 chunks) | 42 | 66.7 | 59.2 | 43.3 | 50.0 |
| completo/bm25 | medio (8-20 chunks) | 42 | 50.0 | 42.4 | 29.3 | 37.3 |
| completo/bm25 | pequeno (<=7 chunks) | 42 | 52.4 | 46.6 | 29.4 | 32.5 |

## Comparações pareadas — cenário fechado

Teste de aleatorização pareado (10.000 permutações), p ajustado por Holm na família.

| A | B | Métrica | A | B | Δ (A−B) | IC95% Δ | p perm. | p Holm | d_z |
|---|---|---|---|---|---|---|---|---|---|
| e5_denso | bm25 | hit@3 | 81.0 | 78.6 | 2.4 | [-4.0; 8.7] | 0.6474 | 0.6474 | 0.06 |
| e5_denso | bm25 | mrr@10 | 76.3 | 70.1 | 6.1 | [0.4; 12.1] | 0.0432 | 0.2160 | 0.18 |
| e5_denso | bm25 | ndcg@10 | 62.6 | 55.3 | 7.3 | [3.7; 11.0] | 0.0005 | 0.0045 | 0.35 |
| e5_denso | bm25 | cp@3 | 73.8 | 68.0 | 5.8 | [0.8; 10.8] | 0.0341 | 0.2046 | 0.20 |
| e5_rerank | e5_denso | hit@3 | 84.9 | 81.0 | 4.0 | [-0.8; 9.5] | 0.2258 | 0.4516 | 0.13 |
| e5_rerank | e5_denso | mrr@10 | 81.4 | 76.3 | 5.1 | [1.1; 9.4] | 0.0159 | 0.1113 | 0.21 |
| e5_rerank | e5_denso | ndcg@10 | 65.3 | 62.6 | 2.7 | [0.7; 4.7] | 0.0106 | 0.0848 | 0.24 |
| e5_rerank | e5_denso | cp@3 | 77.5 | 73.8 | 3.7 | [-0.3; 7.7] | 0.0949 | 0.3796 | 0.16 |
| e5_rerank | bm25 | hit@3 | 84.9 | 78.6 | 6.3 | [0.0; 12.7] | 0.0968 | 0.3796 | 0.17 |
| e5_rerank | bm25 | mrr@10 | 81.4 | 70.1 | 11.2 | [5.2; 17.5] | 0.0003 | 0.0030 | 0.32 |
| e5_rerank | bm25 | ndcg@10 | 65.3 | 55.3 | 10.0 | [6.7; 13.4] | 0.0001 | 0.0012 | 0.52 |
| e5_rerank | bm25 | cp@3 | 77.5 | 68.0 | 9.5 | [5.0; 14.0] | 0.0001 | 0.0012 | 0.36 |

## Comparações pareadas — cenário completo

Teste de aleatorização pareado (10.000 permutações), p ajustado por Holm na família.

| A | B | Métrica | A | B | Δ (A−B) | IC95% Δ | p perm. | p Holm | d_z |
|---|---|---|---|---|---|---|---|---|---|
| e5_denso | bm25 | hit@3 | 61.1 | 56.3 | 4.8 | [-4.8; 14.3] | 0.4105 | 0.9207 | 0.09 |
| e5_denso | bm25 | mrr@10 | 58.2 | 49.4 | 8.8 | [1.7; 16.0] | 0.0188 | 0.1316 | 0.21 |
| e5_denso | bm25 | ndcg@10 | 40.7 | 34.0 | 6.7 | [2.8; 10.5] | 0.0008 | 0.0080 | 0.30 |
| e5_denso | bm25 | cp@3 | 48.7 | 39.9 | 8.7 | [2.6; 14.8] | 0.0072 | 0.0576 | 0.25 |
| e5_rerank | e5_denso | hit@3 | 66.7 | 61.1 | 5.6 | [0.8; 11.1] | 0.0647 | 0.3235 | 0.19 |
| e5_rerank | e5_denso | mrr@10 | 60.5 | 58.2 | 2.3 | [-1.8; 6.5] | 0.2762 | 0.9207 | 0.10 |
| e5_rerank | e5_denso | ndcg@10 | 41.9 | 40.7 | 1.3 | [-0.8; 3.4] | 0.2302 | 0.9207 | 0.11 |
| e5_rerank | e5_denso | cp@3 | 50.5 | 48.7 | 1.9 | [-2.1; 5.8] | 0.4317 | 0.9207 | 0.08 |
| e5_rerank | bm25 | hit@3 | 66.7 | 56.3 | 10.3 | [1.6; 19.0] | 0.0293 | 0.1758 | 0.21 |
| e5_rerank | bm25 | mrr@10 | 60.5 | 49.4 | 11.1 | [3.9; 18.1] | 0.0025 | 0.0225 | 0.27 |
| e5_rerank | bm25 | ndcg@10 | 41.9 | 34.0 | 7.9 | [4.6; 11.3] | 0.0001 | 0.0012 | 0.41 |
| e5_rerank | bm25 | cp@3 | 50.5 | 39.9 | 10.6 | [5.3; 16.1] | 0.0005 | 0.0055 | 0.34 |
