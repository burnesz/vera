---
title: "Baseline Zero-Shot e Avaliação Científica do TCC (DSR)"
domain: "avaliacao-cientifica"
rules: ["RN-AVAL01", "RN-AVAL02"]
related_code:
  - "app/services/baseline_service.py"
  - "evaluation/quantitative.py"
  - "evaluation/retrieval_experiment.py"
  - "evaluation/bm25.py"
  - "evaluation/data/retrieval_gold.json"
  - "evaluation/data/rewriting_dialogs.json"
  - "scripts/run_retrieval_eval.py"
  - "scripts/run_rewriting_eval.py"
  - "scripts/relevance_agreement.py"
  - "scripts/freeze_gold.py"
  - "evaluation/likert_rubric.py"
related_notes:
  - "../00-fundamentos/visao-e-escopo.md"
  - "../00-fundamentos/decisoes-dsr.md"
  - "../04-operacoes-e-roadmap/roadmap-e-status.md"
---

# Baseline Zero-Shot e Avaliação Científica do TCC (DSR)

Para fundamentar a monografia de TCC sob a ótica da metodologia **Design Science Research (DSR)**, a plataforma VERA foi projetada para permitir a avaliação empírica rigorosa dos artefatos construídos frente a uma condição de controle científica (**Baseline Zero-Shot**).

> **Status (2026-11-15)**: a avaliação da recuperação (Seção 2.1) está implementada em `evaluation/quantitative.py`, `evaluation/bm25.py` e `evaluation/retrieval_experiment.py`. A baseline zero-shot está implementada em `app/services/baseline_service.py`, e os pares para o especialista são gerados por `scripts/run_baseline_pairs.py` (Seção 1.1). `evaluation/likert_rubric.py` ainda é um arquivo vazio (Fase 4 do [roadmap](../04-operacoes-e-roadmap/roadmap-e-status.md)).

---

## 1. Configuração da Baseline Experimental (Zero-Shot)

- **Isolamento da Variável Independente**:
  - A condição **Baseline** (`app/services/baseline_service.py`) usa o **mesmo modelo e os mesmos prompts** de cada fluxo da VERA, na mesma infraestrutura. No feedback e na tutora, o modelo é o `LLM_MODEL_TUTORIA` (Qwen3 8B sem raciocínio, `RN-INF07`, `DSR-08`).
  - Opera em modo **zero-shot**: sem recuperação vetorial no Pinecone, sem exemplos *few-shot* e sem as camadas de verificação. No feedback, uma única geração, sem a verificação contra o gabarito (`RN-FB04`); na tutora, sem a reescrita da consulta.
  - A baseline das **questões inéditas** fica no serviço de questões (`questoes-ineditas-enem`, `app/services/baseline_service.py`): o mesmo prompt de geração do Qwen 2.5 7B, para a mesma habilidade, tema, abertura e tipologia da questão da VERA, sem RAG, sem *few-shot*, sem PoT e sem validação.
- **Justificativa Científica**: Garante uma comparação controlada e justa onde a arquitetura (RAG, PoT e verificações) é a variável manipulada, e não o modelo nem as instruções. Um teste (`tests/test_baseline.py`) confirma que o prompt do feedback da VERA e o da baseline só diferem pelo bloco de material recuperado.

### 1.1 Pares para a avaliação com o especialista

`./.venv/bin/python scripts/run_baseline_pairs.py` gera, com semente fixa, 10 pares por fluxo em `evaluation/results/pares-especialista-<data>/`:

| Fluxo | Insumo | VERA | Baseline |
| :--- | :--- | :--- | :--- |
| Feedback | Questão histórica do ENEM (só texto, sem H06/H20, uma por habilidade) e uma alternativa errada sorteada como resposta do estudante | `FeedbackService.gerar_feedback_verificado` | `BaselineService.gerar_feedback` |
| Tutora | Diálogo de 2 turnos de `evaluation/data/rewriting_dialogs.json` | `ChatService.send_message` (sessão em memória) | `BaselineService.responder_tutoria` |

- Se a VERA recusar um feedback (`RN-FB04`), o insumo é registrado como recusado e o próximo candidato entra no lugar. A taxa de recusas é um resultado.
- Os tempos de cada condição são gravados, o que dá a latência de cada fluxo (Seção 2, item 2).
- A rodada é retomável (`--retomar <pasta>`), e o `manifest.json` registra o commit, o modelo, a versão do Ollama e a semente.

---

## 2. Métricas Quantitativas (`evaluation/quantitative.py`)

O módulo de avaliação quantitativa deverá acompanhar três dimensões de performance e confiabilidade:

1. **Qualidade da Recuperação Vetorial (RAG)**:
   - *Precision@K* e *Recall@K* na busca semântica sobre os namespaces `materiais_didaticos` e `questoes_enem`.
   - Impacto do *Query Rewriting* (`RN-CHAT01`) no score de similaridade cosseno em turnos conversacionais com anáforas.
   - Protocolo detalhado na Seção 2.1.
2. **Desempenho e Latência de Inferência Local**:
   - Tempo médio de resposta por chamada ao Ollama (Chat RAG vs. Etapas do Pipeline PoT vs. Baseline).
3. **Taxa de Retenção, Auto-Healing e Barragem de Alucinações**:
   - Percentual de questões recuperadas em 0ms pelo **Auto-Healing Algorítmico** (`auto_heal_distractors` — `DSR-05`).
   - Percentual de itens defeituosos barrados por etapa:
     - Violação de *groundedness* numérico ou exceção no `CodeExecutor`.
     - Divergência matemática no Confronto de Equivalência (*Early Exit* na Etapa 2 — `DSR-06`).
     - Reprovação nas 5 flags da Auditoria Semântica (Etapa 3 — `DSR-06`).

### 2.1 Protocolo de Avaliação da Recuperação (paradigma Cranfield)

> **Status (2026-11-15)**: instrumentos e scripts implementados e testados (`tests/test_retrieval_evaluation.py`). Teste de fumaça com 4 queries executado. O gabarito (versão 1.0) **ainda não está congelado**: falta a rodada piloto, a anotação do segundo avaliador e o congelamento (`RN-AVAL02`).

#### 2.1.1 Fundamentação metodológica

- **Paradigma Cranfield**: avaliação com coleção de teste fixa (documentos + queries + julgamentos de relevância), método padrão da Recuperação de Informação (RI) desde Cleverdon (1967) e adotado pelo TREC. Referências: Voorhees (2002), Sanderson (2010), Manning, Raghavan & Schütze (2008, cap. 8).
- **Enquadramento DSR**: avaliação *artificial, somativa e ex post* no quadro FEDS (Venable, Pries-Heje & Baskerville, 2016), equivalente ao método experimental controlado de Hevner et al. (2004). Pela taxonomia de Prat, Comyn-Wattiau & Akoka (2015), as métricas de acerto medem **eficácia** e a latência mede **eficiência**.

#### 2.1.2 Coleção de teste

- **Corpus julgado**: o namespace `materiais_didaticos` tem 4.038 chunks.
  - Os 63 PDFs `raw/ENEM_MAT_XX_<topico>.pdf` do R2 (artigos da Wikipédia, 1.285 chunks) são julgados **por documento**. O tópico vem do nome do arquivo.
  - **Gabarito 2.0**: as 8 apostilas (`TEO_*`, `caderno_matematica.pdf` e `ebook-matematica-e-suas-tecnologias.pdf`, 2.753 chunks) são julgadas **por segmento de páginas** com o mesmo assunto. São 161 segmentos e 723 páginas, que cobrem 1.898 chunks. Cada segmento lista os tópicos (PDFs `ENEM_MAT_*`) que ensina, e o seu grau numa query é o maior grau que ela dá a esses tópicos (`regra_segmentos` no JSON).
  - Os volumes `TEO_*` foram segmentados pelo sumário, porque a página impressa coincide com a página do PDF. O e-book e o caderno foram lidos página a página. O caderno quase não tem camada de texto e foi rotulado pelas imagens das páginas.
  - Páginas fora dos segmentos têm grau 0: capas, sumários e assuntos sem tópico no gabarito, como matrizes, polinômios e números complexos.
  - A página do chunk vem do id gravado na ingestão (`..._p<página>_c<chunk>_...`). A rotulagem foi feita com assistência de IA.
  - A versão 1.0, só com os `ENEM_MAT_*`, foi usada na rodada `recuperacao-20261116-022117`, que guarda uma cópia dela.
- **Duplicatas exatas**: `05_analise-combinatoria` = `05_arranjo-combinatoria` (artigo "Combinatória") e `06_juros-compostos` = `06_juros-simples` (artigo "Juro"). As duas cópias contam como alvo (grau 2). São 61 artigos distintos. As duplicatas também ocupam posições do top-K no sistema real.
- **Eixo do arquivo ≠ competência**: o prefixo `01`..`07` é um agrupamento temático do acervo e **não** coincide com `C1`–`C7` da Matriz.
- **Queries** ([`evaluation/data/retrieval_gold.json`](../../evaluation/data/retrieval_gold.json)): 126, duas por PDF. A `direta` cita o tópico (sinal lexical). A `contextual` descreve uma situação no estilo ENEM sem nomear o tópico (sinal semântico). 126 queries está acima das 50 usuais no TREC (Voorhees & Buckley, 2002).
- **Relevância graduada (qrels)**: `2` = documento-alvo, `1` = correlato aceitável (ex.: `variancia` para uma query de `desvio-padrao`), `0` = resto. O grau 2 é objetivo (vem do nome do arquivo). O grau 1 é subjetivo e por isso passa pela validação com segundo avaliador (2.1.5).
- **Diálogos de Query Rewriting** ([`evaluation/data/rewriting_dialogs.json`](../../evaluation/data/rewriting_dialogs.json)): 30 diálogos de 2 turnos cuja segunda mensagem depende do histórico (ex.: "E a área total dele, como faço?" depois de uma pergunta sobre cilindro). Cada diálogo tem uma consulta-oráculo autocontida escrita à mão.

#### 2.1.3 Desenho experimental

**Experimento 1 — Qualidade da recuperação** (`scripts/run_retrieval_eval.py`)

| Fator | Níveis |
|---|---|
| Sistema (variável independente) | `e5_denso` (produção), `e5_rerank` (E5 + `bge-reranker-v2-m3` sobre 25 candidatos, mesmo procedimento de `search(rerank=True)`), `bm25` (baseline lexical, Okapi BM25 k1 = 1,2, b = 0,75 sobre os mesmos chunks) |
| Cenário | `fechado`: filtro `document_name $in [63 PDFs]`, medição limpa, só com os julgamentos por documento. `completo`: namespace inteiro, como na produção, com as apostilas julgadas por segmento (gabarito 2.0) |
| Unidade experimental | query (126), medidas pareadas em todos os sistemas |

Hipóteses pré-registradas (H1 = métrica primária Hit@3):
- **H1a**: `e5_denso` > `bm25` (a busca semântica do artefato supera a alternativa simples).
- **H1b**: `e5_rerank` ≠ `e5_denso` (o reranker, hoje desligado, muda a qualidade?).
- **H1c**: `e5_rerank` > `bm25`.

**Experimento 2 — Query Rewriting** (`scripts/run_rewriting_eval.py`, exige Ollama ativo)

Condições sobre os 30 diálogos, com a busca de produção (E5 denso, cenário fechado):
- `sem_reescrita`: mensagem crua;
- `com_reescrita`: saída de `ChatService.rewrite_query` (LLM de produção, temperatura 0);
- `oraculo`: consulta autocontida (limite superior).

Hipóteses: **H2a** `com_reescrita` > `sem_reescrita`; **H2b** `oraculo` × `com_reescrita` (quanto falta para o teto). As reescritas produzidas são salvas na rodada, porque o LLM pode variar entre execuções.

#### 2.1.4 Métricas e convenções

A unidade ranqueada é o **chunk**, porque é o que chega ao prompt. Cada chunk herda o grau da sua unidade de relevância: o PDF de origem (`metadata.document_name`) ou, nas apostilas, o segmento de páginas (`retrieval_experiment.relevance_unit`). No cenário `fechado`, o ranking ideal do nDCG usa só os documentos, porque as apostilas não podem ser recuperadas ali. Os rankings são salvos até a profundidade 25.

| Métrica | Definição | Papel | Referência |
|---|---|---|---|
| **Hit@K** (K = 1, 3, 5, 10) | 1 se algum dos K primeiros chunks vem de documento grau 2 | **Primária: Hit@3**, porque K = 3 é o `top_k` do Chat e do Feedback | *top-k accuracy* de Karpukhin et al. (2020); Gao et al. (2023) |
| **MRR@10** | 1 / posição do primeiro chunk grau 2 | Ordenação | Voorhees (1999); MS MARCO |
| **nDCG@10** | DCG com ganho linear (rel / log2(i+1)), como trec_eval/BEIR. O ideal usa todos os chunks julgados de cada PDF | Usa os graus 2 e 1 | Järvelin & Kekäläinen (2002); Thakur et al. (2021) |
| **Context Precision@3** | fração dos 3 chunks com grau ≥ 1 (denominador fixo em 3) | Ruído no prompt. Versão determinística da métrica do RAGAS (que usa LLM como juiz) | Es et al. (2024) |
| **Latência p50/p95** | tempo de embed + Pinecone (+ rerank), sem a query de aquecimento | Eficiência | — |

- A **MAP** não é reportada: com um documento-alvo por query, ela é idêntica à MRR.
- O **Recall@K** não é reportado em separado: com um artigo-alvo por query, ele coincide com o Hit@K.
- Pela crítica de Fuhr (2017) às médias de MRR, a MRR é sempre apresentada **junto** com o Hit@K.

#### 2.1.5 Análise estatística

- **IC 95%** de cada média por *bootstrap* percentil das queries (10.000 reamostragens, semente 42).
- **Comparações pareadas**: teste de aleatorização (permutação) pareado bilateral, recomendado por Smucker, Allan & Carterette (2007). O Wilcoxon foi descartado por gerar mais falsos positivos em RI. O p-valor usa a correção +1 de Phipson & Smyth (2010).
- **Comparações múltiplas**: Holm-Bonferroni na família de cada cenário (3 pares × 4 métricas).
- **Tamanho de efeito**: d_z pareado e diferença média com IC por bootstrap (Sakai, 2014).
- **Recortes descritivos** (sem teste): tipo de query, eixo temático e tamanho do PDF (≤ 7, 8–20, > 20 chunks). Alguns eixos têm poucas queries (o eixo 07 tem 4).
- **Concordância do gabarito**: pooling no estilo TREC (gabarito + top-5 PDFs de cada rodada piloto), julgamento cego por um segundo avaliador e kappa de Cohen simples e ponderado linear (`scripts/relevance_agreement.py`). As divergências são resolvidas por consenso antes do congelamento.

#### 2.1.6 Procedimento de execução

1. **Revisão humana** das 126 queries e dos 30 diálogos. Editar os JSONs de `evaluation/data/`.
2. **Rodada piloto** (resultados com prefixo `piloto-`): `./.venv/bin/python scripts/run_retrieval_eval.py`
3. **Pool para o segundo avaliador**: `./.venv/bin/python scripts/relevance_agreement.py exportar --rodada evaluation/results/piloto-recuperacao-<data>`. O avaliador preenche a coluna `grau` de `evaluation/data/anotacao/pool.csv` sem ver o gabarito.
4. **Concordância**: `./.venv/bin/python scripts/relevance_agreement.py calcular --anotacao <csv preenchido>`. Resolver as divergências e ajustar `retrieval_gold.json`.
5. **Congelamento**: `./.venv/bin/python scripts/freeze_gold.py`, seguido de commit dos dois JSONs.
6. **Rodadas oficiais**: `scripts/run_retrieval_eval.py` e `scripts/run_rewriting_eval.py`. Para medir a latência do Experimento 1, o Ollama não deve estar gerando nada (ver 2.1.7). Cada rodada grava o manifest (commit, SHA-256 do gabarito, modelos, parâmetros, carga da máquina), os rankings brutos (`runs/*.jsonl`), as métricas por query (CSV), o `resumo.json` e o `relatorio.md`.
7. **Reprocessamento** sem consultar o Pinecone: `--recalcular <pasta>`.

#### 2.1.7 Ameaças à validade e observações

- **Construção do instrumento**: as queries foram redigidas por um LLM (assistente de código) que tinha visto os documentos. É uma crítica conhecida ao paradigma Cranfield, mitigada pela revisão humana e pelo segundo avaliador.
- **Corpus**: no gabarito 1.0, os chunks relevantes das apostilas contavam como erro no cenário `completo`, e os números eram um limite inferior. O gabarito 2.0 corrige isso com os segmentos de páginas. Restam duas limitações:
  - o segmento é mais grosso que o chunk: um chunk de exercício misto herda os tópicos do segmento inteiro;
  - os segmentos foram rotulados por uma única pessoa com assistência de IA, sem segundo avaliador.
- **BM25**: usa o texto salvo no metadado (até 3.000 caracteres; os chunks têm cerca de 1.200, então não há corte na prática) e não aplica stemming.
- **Latência (achado do teste de fumaça)**: `EmbeddingService` fixa `torch.set_num_threads(os.cpu_count())`. Com o `llama-server` ocupando ~7 núcleos, um embedding de query levou ~5,6 s com 16 threads, contra ~0,15 s com 4 threads. Isso afeta a produção e a medição. A correção está pendente de decisão e não foi aplicada.

#### 2.1.8 Referências

- Cleverdon, C. W. (1967). The Cranfield tests on index language devices. *Aslib Proceedings*, 19(6).
- Es, S. et al. (2024). RAGAS: Automated evaluation of retrieval augmented generation. *EACL (System Demonstrations)*.
- Fuhr, N. (2017). Some common mistakes in IR evaluation, and how they can be avoided. *SIGIR Forum*, 51(3).
- Gao, Y. et al. (2023). Retrieval-augmented generation for large language models: A survey. *arXiv:2312.10997*.
- Hevner, A. R. et al. (2004). Design science in information systems research. *MIS Quarterly*, 28(1).
- Järvelin, K.; Kekäläinen, J. (2002). Cumulated gain-based evaluation of IR techniques. *ACM TOIS*, 20(4).
- Karpukhin, V. et al. (2020). Dense passage retrieval for open-domain question answering. *EMNLP*.
- Manning, C. D.; Raghavan, P.; Schütze, H. (2008). *Introduction to Information Retrieval*. Cambridge University Press.
- Phipson, B.; Smyth, G. K. (2010). Permutation p-values should never be zero. *Statistical Applications in Genetics and Molecular Biology*, 9(1).
- Prat, N.; Comyn-Wattiau, I.; Akoka, J. (2015). A taxonomy of evaluation methods for information systems artifacts. *JMIS*, 32(3).
- Robertson, S.; Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in IR*, 3(4).
- Sakai, T. (2014). Statistical reform in information retrieval? *SIGIR Forum*, 48(1).
- Sanderson, M. (2010). Test collection based evaluation of information retrieval systems. *Foundations and Trends in IR*, 4(4).
- Smucker, M. D.; Allan, J.; Carterette, B. (2007). A comparison of statistical significance tests for information retrieval evaluation. *CIKM*.
- Thakur, N. et al. (2021). BEIR: A heterogeneous benchmark for zero-shot evaluation of information retrieval models. *NeurIPS Datasets and Benchmarks*.
- Venable, J.; Pries-Heje, J.; Baskerville, R. (2016). FEDS: A framework for evaluation in design science research. *European Journal of Information Systems*, 25(1).
- Voorhees, E. M. (1999). The TREC-8 question answering track report. *TREC-8*.
- Voorhees, E. M. (2002). The philosophy of information retrieval evaluation. *CLEF 2001, LNCS 2406*.
- Voorhees, E. M.; Buckley, C. (2002). The effect of topic set size on retrieval experiment error. *SIGIR*.

> Conferir volume, número e páginas de cada referência na fonte original antes de usá-las na monografia.

---

## 3. Avaliação Qualitativa — Rubrica Likert Cega (`evaluation/likert_rubric.py`)

Aplicação de questionário **duplo-cego** com especialista humano em Matemática do Ensino Médio/ENEM, avaliando pares de saídas (**VERA RAG/PoT** vs. **Baseline Zero-Shot**) em escala Likert de **1 a 5**:

### 3.1 Critérios para Tutoria Pedagógica (Chat)
1. **Correção Conceitual e Matemática**: ausência de erros de cálculo ou definições incorretas.
2. **Clareza e Didática Passo a Passo**: facilidade de compreensão pelo estudante de Ensino Médio.
3. **Adequação da Linguagem ao Contexto ENEM**: tom acolhedor, rigor terminológico e uso de exemplos adequados.
4. **Fidelidade e Ausência de Alucinações**: aderência aos conceitos matemáticos sem invenção de regras ou teoremas falsos.

### 3.2 Critérios para Questões Inéditas Geradas
1. **Plausibilidade da Situação-Problema**: realismo do contexto cotidiano e verossimilhança dos dados numéricos.
2. **Clareza e Inequivocidade do Comando**: ausência de ambiguidade ou comando duplo.
3. **Qualidade Pedagógica dos Distratores**: plausibilidade das alternativas incorretas frente a erros cognitivos comuns.
4. **Adequação do Grau de Dificuldade**: compatibilidade com o nível exigido na prova de Matemática do ENEM.
5. **Alinhamento à Habilidade da Matriz (`H01`–`H30`)**: aderência estrita ao descritor oficial do INEP.

---

## 4. Regras de Negócio da Avaliação (`RN-AVAL01` e `RN-AVAL02`)

- **`RN-AVAL01` (Critério de Aceite Empírico)**: As saídas produzidas com a arquitetura completa (RAG + PoT) devem demonstrar escores médios iguais ou superiores aos da Baseline Zero-Shot nos critérios avaliados.
- **`RN-AVAL02` (Congelamento de Instrumentos)**: A rubrica Likert e os formulários/scripts de coleta em `evaluation/` devem permanecer congelados e versionados durante a rodada de avaliação com o especialista humano para assegurar validade metodológica.

---

## Notas Relacionadas

- [Visão Geral, Escopo Pedagógico e Glossário](../00-fundamentos/visao-e-escopo.md)
- [Decisões de Engenharia DSR](../00-fundamentos/decisoes-dsr.md)
- [Roadmap e Status de Implementação](../04-operacoes-e-roadmap/roadmap-e-status.md)
