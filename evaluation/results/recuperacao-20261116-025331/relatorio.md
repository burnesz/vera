# Experimento 1 — Recuperação em materiais_didaticos

- Gerado em: 2026-11-16T02:53:31
- Gabarito: versão 2.0 (congelado: True, sha256 `4a6e9006a0f2`)
- Commit: `f6a427631ee3`

Valores em %, com IC 95% por bootstrap entre colchetes. Unidade ranqueada: chunk.

## Resultados gerais

| Sistema | n | hit@1 | hit@3 | hit@5 | hit@10 | mrr@10 | ndcg@10 | cp@3 | p@3 | r@3 | p@10 | r@10 | lat. p50 (ms) | lat. p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fechado/e5_denso | 126 | 69.8 [61.9; 77.8] | 81.0 [73.8; 87.3] | 84.9 [78.6; 91.3] | 89.7 [84.1; 94.4] | 76.3 [69.5; 82.8] | 62.6 [57.3; 67.8] | 73.8 [67.5; 79.9] | 62.2 [55.6; 68.8] | 80.6 [73.4; 87.3] | 46.2 [40.6; 51.7] | 89.7 [84.1; 94.4] | 264 | 411 |
| fechado/e5_rerank | 126 | 77.0 [69.0; 84.1] | 84.9 [78.6; 91.3] | 87.3 [81.0; 92.9] | 90.5 [84.9; 95.2] | 81.4 [74.9; 87.4] | 65.3 [60.0; 70.3] | 77.5 [71.7; 83.1] | 63.2 [56.6; 69.6] | 84.9 [78.6; 91.3] | 47.9 [42.2; 53.3] | 90.5 [84.9; 95.2] | 1686 | 2286 |
| fechado/bm25 | 126 | 60.3 [51.6; 69.0] | 78.6 [71.4; 85.7] | 81.0 [73.8; 87.3] | 86.5 [80.2; 92.1] | 70.1 [63.1; 76.9] | 55.3 [50.0; 60.4] | 68.0 [61.9; 74.1] | 54.8 [48.1; 61.4] | 78.6 [71.4; 85.7] | 40.9 [35.6; 46.1] | 86.5 [80.2; 92.1] | 1 | 2 |
| completo/e5_denso | 126 | 73.0 [65.1; 81.0] | 85.7 [79.4; 91.3] | 89.7 [84.1; 94.4] | 93.7 [88.9; 97.6] | 80.6 [74.6; 86.4] | 65.0 [59.9; 69.8] | 77.5 [71.7; 82.8] | 64.3 [58.2; 70.4] | 30.9 [25.7; 36.6] | 53.9 [48.5; 59.2] | 41.7 [36.7; 47.0] | 276 | 306 |
| completo/e5_rerank | 126 | 74.6 [66.7; 81.7] | 86.5 [80.2; 92.1] | 91.3 [85.7; 96.0] | 92.1 [87.3; 96.0] | 81.4 [75.3; 87.1] | 68.4 [63.6; 73.0] | 80.2 [74.6; 85.4] | 68.5 [62.2; 74.6] | 33.7 [28.3; 39.4] | 57.4 [52.2; 62.4] | 43.4 [38.4; 48.9] | 2229 | 2827 |
| completo/bm25 | 126 | 64.3 [55.6; 73.0] | 81.0 [73.8; 87.3] | 87.3 [81.0; 92.9] | 93.7 [88.9; 97.6] | 74.5 [68.2; 80.7] | 58.4 [53.3; 63.3] | 72.2 [66.1; 77.8] | 59.5 [53.2; 65.9] | 32.4 [26.9; 38.5] | 47.9 [42.5; 53.0] | 44.3 [39.2; 49.8] | 4 | 7 |

## Recorte por tipo de query (descritivo)

| Sistema | Grupo | n | hit@3 | mrr@10 | ndcg@10 | cp@3 |
|---|---|---|---|---|---|---|
| fechado/e5_denso | contextual | 63 | 63.5 | 57.4 | 44.8 | 57.1 |
| fechado/e5_denso | direta | 63 | 98.4 | 95.1 | 80.3 | 90.5 |
| fechado/e5_rerank | contextual | 63 | 71.4 | 66.3 | 49.6 | 63.5 |
| fechado/e5_rerank | direta | 63 | 98.4 | 96.4 | 80.9 | 91.5 |
| fechado/bm25 | contextual | 63 | 63.5 | 54.4 | 39.8 | 52.4 |
| fechado/bm25 | direta | 63 | 93.7 | 85.9 | 70.7 | 83.6 |
| completo/e5_denso | contextual | 63 | 73.0 | 64.8 | 48.7 | 65.1 |
| completo/e5_denso | direta | 63 | 98.4 | 96.4 | 81.3 | 89.9 |
| completo/e5_rerank | contextual | 63 | 74.6 | 68.0 | 52.3 | 65.1 |
| completo/e5_rerank | direta | 63 | 98.4 | 94.8 | 84.6 | 95.2 |
| completo/bm25 | contextual | 63 | 74.6 | 65.6 | 45.5 | 64.0 |
| completo/bm25 | direta | 63 | 87.3 | 83.5 | 71.3 | 80.4 |

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
| completo/e5_denso | Combinatória, estatística e probabilidade | 24 | 83.3 | 79.9 | 69.9 | 87.5 |
| completo/e5_denso | Geometria e trigonometria | 42 | 92.9 | 84.5 | 66.4 | 85.7 |
| completo/e5_denso | Grandezas e medidas | 10 | 80.0 | 80.0 | 60.1 | 70.0 |
| completo/e5_denso | Lógica | 4 | 100.0 | 87.5 | 75.2 | 91.7 |
| completo/e5_denso | Matemática financeira | 10 | 90.0 | 73.3 | 62.5 | 70.0 |
| completo/e5_denso | Números e operações | 18 | 83.3 | 84.1 | 57.5 | 61.1 |
| completo/e5_denso | Álgebra e funções | 18 | 72.2 | 72.0 | 64.6 | 66.7 |
| completo/e5_rerank | Combinatória, estatística e probabilidade | 24 | 95.8 | 93.8 | 78.8 | 94.4 |
| completo/e5_rerank | Geometria e trigonometria | 42 | 85.7 | 79.8 | 67.2 | 81.0 |
| completo/e5_rerank | Grandezas e medidas | 10 | 80.0 | 73.3 | 63.7 | 66.7 |
| completo/e5_rerank | Lógica | 4 | 100.0 | 87.5 | 85.5 | 100.0 |
| completo/e5_rerank | Matemática financeira | 10 | 80.0 | 82.0 | 68.1 | 73.3 |
| completo/e5_rerank | Números e operações | 18 | 88.9 | 79.3 | 59.9 | 74.1 |
| completo/e5_rerank | Álgebra e funções | 18 | 77.8 | 73.6 | 65.0 | 72.2 |
| completo/bm25 | Combinatória, estatística e probabilidade | 24 | 79.2 | 66.5 | 61.6 | 77.8 |
| completo/bm25 | Geometria e trigonometria | 42 | 78.6 | 76.5 | 57.6 | 71.4 |
| completo/bm25 | Grandezas e medidas | 10 | 80.0 | 81.1 | 58.0 | 66.7 |
| completo/bm25 | Lógica | 4 | 100.0 | 75.0 | 80.9 | 91.7 |
| completo/bm25 | Matemática financeira | 10 | 100.0 | 100.0 | 71.9 | 90.0 |
| completo/bm25 | Números e operações | 18 | 88.9 | 77.8 | 53.0 | 64.8 |
| completo/bm25 | Álgebra e funções | 18 | 66.7 | 59.4 | 49.1 | 63.0 |

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
| completo/e5_denso | grande (>20 chunks) | 42 | 90.5 | 82.1 | 69.5 | 79.4 |
| completo/e5_denso | medio (8-20 chunks) | 42 | 78.6 | 76.0 | 65.1 | 78.6 |
| completo/e5_denso | pequeno (<=7 chunks) | 42 | 88.1 | 83.7 | 60.4 | 74.6 |
| completo/e5_rerank | grande (>20 chunks) | 42 | 90.5 | 87.4 | 74.1 | 81.7 |
| completo/e5_rerank | medio (8-20 chunks) | 42 | 81.0 | 73.3 | 65.9 | 77.0 |
| completo/e5_rerank | pequeno (<=7 chunks) | 42 | 88.1 | 83.5 | 65.3 | 81.7 |
| completo/bm25 | grande (>20 chunks) | 42 | 83.3 | 76.9 | 62.7 | 73.8 |
| completo/bm25 | medio (8-20 chunks) | 42 | 78.6 | 75.2 | 58.4 | 73.8 |
| completo/bm25 | pequeno (<=7 chunks) | 42 | 81.0 | 71.5 | 54.1 | 69.0 |

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
| e5_denso | bm25 | hit@3 | 85.7 | 81.0 | 4.8 | [-2.4; 11.9] | 0.2843 | 0.8528 | 0.11 |
| e5_denso | bm25 | mrr@10 | 80.6 | 74.5 | 6.1 | [-0.1; 12.3] | 0.0570 | 0.3990 | 0.17 |
| e5_denso | bm25 | ndcg@10 | 65.0 | 58.4 | 6.6 | [3.0; 10.5] | 0.0007 | 0.0077 | 0.31 |
| e5_denso | bm25 | cp@3 | 77.5 | 72.2 | 5.3 | [-0.0; 10.8] | 0.0753 | 0.4518 | 0.17 |
| e5_rerank | e5_denso | hit@3 | 86.5 | 85.7 | 0.8 | [-4.0; 6.3] | 1.0000 | 1.0000 | 0.03 |
| e5_rerank | e5_denso | mrr@10 | 81.4 | 80.6 | 0.8 | [-3.7; 5.3] | 0.7423 | 1.0000 | 0.03 |
| e5_rerank | e5_denso | ndcg@10 | 68.4 | 65.0 | 3.4 | [1.3; 5.6] | 0.0030 | 0.0300 | 0.27 |
| e5_rerank | e5_denso | cp@3 | 80.2 | 77.5 | 2.6 | [-0.8; 6.1] | 0.1779 | 0.8474 | 0.13 |
| e5_rerank | bm25 | hit@3 | 86.5 | 81.0 | 5.6 | [-1.6; 11.9] | 0.1695 | 0.8474 | 0.14 |
| e5_rerank | bm25 | mrr@10 | 81.4 | 74.5 | 6.9 | [0.5; 13.3] | 0.0388 | 0.3104 | 0.19 |
| e5_rerank | bm25 | ndcg@10 | 68.4 | 58.4 | 10.0 | [6.4; 13.8] | 0.0001 | 0.0012 | 0.48 |
| e5_rerank | bm25 | cp@3 | 80.2 | 72.2 | 7.9 | [2.6; 13.2] | 0.0045 | 0.0405 | 0.26 |
