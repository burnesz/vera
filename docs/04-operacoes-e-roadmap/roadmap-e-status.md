---
title: "Roadmap e Checklist Consolidado de Implementação"
domain: "roadmap"
rules: []
related_code:
  - "app/services/baseline_service.py"
  - "evaluation/quantitative.py"
  - "evaluation/likert_rubric.py"
related_notes:
  - "../00-fundamentos/decisoes-dsr.md"
  - "../03-avaliacao-cientifica/baseline-e-metricas-tcc.md"
  - "./guia-operacional-e-scripts.md"
---

# Roadmap e Checklist Consolidado de Implementação

Registro atualizado do progresso das 4 fases de desenvolvimento do projeto VERA.

---

## Fase 1: Infraestrutura e Armazenamento (Concluída)

- [x] Configuração do modelo local Qwen 2.5 7B quantizado (`qwen2.5:7b-instruct-q4_K_M`) no Ollama (`http://localhost:11434`)
- [x] Cliente LLM resiliente com health-check, timeout de 300s (`num_ctx=4096`), retry exponencial e suporte a modo mock (`app/services/llm_client.py`)
- [x] Modelos relacionais completos no PostgreSQL 15: usuários, habilidades, questões ENEM, inéditas, simulados, tentativas, respostas, desempenho, feedbacks e chat (`app/db/models/`)
- [x] Carga da Matriz de Referência do ENEM (`H01` a `H30`, `C1` a `C7`) via script (`scripts/seed_habilidades.py`)
- [x] Carga do acervo de 402 questões históricas textuais do ENEM no PostgreSQL (`scripts/seed_questoes.py`)
- [x] Vetorização e carga dos itens históricos no namespace `questoes_enem` do Pinecone (`scripts/seed_questoes_pinecone.py`)
- [x] Pipeline de chunking semântico de PDFs didáticos com Unstructured, fallback PyMuPDF e OCR de fórmulas via `pix2tex` (`app/pipeline/chunking.py` e `app/pipeline/formula_extractor.py`)
- [x] Vetorização de materiais didáticos no namespace `materiais_didaticos` do Pinecone com `intfloat/multilingual-e5-large` (`app/pipeline/index_embeddings.py`)
- [x] Integração com Cloudflare R2 para armazenamento em nuvem de PDFs didáticos (`app/services/storage.py`)

---

## Fase 2: Serviços de Negócio, Pipeline PoT e APIs (Concluída)

- [x] Autenticação stateless JWT (`HS256`) com senhas criptografadas via Bcrypt (`app/api/v1/auth.py` e `app/core/security.py`)
- [x] Engine de simulados estratificados com 45 itens (85% históricas + 15% inéditas, cobertura de habilidades e omissão de gabarito durante a prova) (`app/services/simulado_service.py` e `app/api/v1/simulado.py`)
- [x] Recuperação RAG diversificada para *few-shot*: Top-10 candidatos no Pinecone com sorteio aleatório de 2 exemplos + sorteio de temas e aberturas narrativas (`DSR-04`)
- [x] Pipeline PoT (*Program-Aided Generation*) com execução de `def resolver()` em subprocesso isolado, inspeção de AST, *groundedness* numérico e montagem determinística de gabarito (`app/services/code_executor.py` — `DSR-03`)
- [x] Defesa em cascata contra *Anchoring Bias*: **Auto-Healing Algorítmico de Distratores** em 0ms + **Stateless Retry** com contexto limpo (`DSR-05`)
- [x] Pipeline de **Validação Modular em 3 Etapas** contra *Sycophancy*: Resolução Cega Pura $\rightarrow$ Confronto de Equivalência com *Early Exit* $\rightarrow$ Auditoria Semântica com flags booleanas e rejeição determinística (`DSR-06`)
- [x] Suporte estruturado a `tabela_dados` (conversão automática para Markdown) e sanitização de escapes LaTeX em JSON (`app/services/question_validator.py`)
- [x] Script multi-round de geração em lote e povoamento de questões inéditas (`scripts/populate_questoes_ineditas.py`)
- [x] Serviço de Tutoria RAG Interativa com *Query Rewriting*, CoT obrigatório (`<pensamento>` + `<resposta>`) e persistência relacional (`app/services/chat_service.py` e `app/api/v1/chat.py` — `DSR-02`)
- [x] Feedback pedagógico pontual por item errado com RAG determinístico, CoT e cache em `feedbacks` (`app/services/feedback_service.py` e `app/api/v1/feedback.py` — `RN-FB01`..`03`)
- [x] Pós-processamento do feedback: verificação automática contra gabarito e habilidade, com Stateless Retry (até 3 tentativas) e HTTP `422` se reprovado (`app/services/feedback_verifier.py` — `RN-FB04`, 2026-11-15)
- [x] Atualização cumulativa de `desempenho_habilidades` na submissão, histórico de tentativas (`/simulados/tentativas/me`) e API de dashboard (`app/api/v1/dashboard.py` — `RN-SIM03`)

---

## Fase 3: Frontend e Experiência do Usuário (Concluída)

- [x] Aplicação web SPA em React 18 + TypeScript + Vite com Design System *Ocean & Coral* (`frontend/`)
- [x] Autenticação, cadastro e proteção de rotas com `AuthContext.tsx`
- [x] Caderno de Simulado (`SimuladoPage.tsx`) com cronômetro, folha de respostas dinâmica, marcação de revisão, revisão item a item pós-submissão e card de feedback da Tutora VERA
- [x] Interface da Tutora VERA (`ChatPage.tsx`) com renderização matemática KaTeX (`MathText.tsx`), histórico de sessões e card retrátil para o bloco `<pensamento>`
- [x] Dashboard de diagnóstico do estudante por Competências (`C1`–`C7`) e Habilidades, com dados reais de `/dashboard/desempenho` (`StudentDashboard.tsx`)
- [x] Containerização com Docker Compose (`Dockerfile`, `docker-compose.yml`)
- [x] Remoção do fallback de caderno/correção fictícios no frontend: falhas da API são exibidas ao estudante (`simuladoService.ts`, `SimuladoPage.tsx` — 2026-11-15)
- [x] Suíte de testes automatizados com Pytest (`tests/` — 21 módulos, 203 testes em 2026-11-15)

---

## Fase 4: Avaliação Científica e Conclusão do TCC (Em Andamento)

- [x] Serviço de execução em modo **Baseline Zero-Shot** (`app/services/baseline_service.py`): mesmo modelo e mesmos prompts, sem RAG e sem verificações; pares VERA × baseline gerados por `scripts/run_baseline_pairs.py` (2026-11-15)
- [x] Feedback e tutora passam a usar o **Qwen3 8B sem raciocínio** (`LLM_MODEL_TUTORIA`, `RN-INF07`), escolhido pelo Experimento 1 de seleção de modelos (`DSR-08`) (2026-11-15)
- [x] Correção: o feedback enviava a lista de mensagens no campo `prompt` do `/api/generate` e o Ollama recusava a chamada (HTTP 400); agora vira `system` + `prompt` (2026-11-15)
- [ ] Rodada completa dos pares VERA × baseline (feedback e tutora) e montagem do caderno do especialista
- [x] Métricas e experimento de recuperação implementados: `evaluation/quantitative.py`, `evaluation/bm25.py`, `evaluation/retrieval_experiment.py`, gabarito de 126 queries e 30 diálogos em `evaluation/data/`, scripts `run_retrieval_eval.py`, `run_rewriting_eval.py`, `relevance_agreement.py` e `freeze_gold.py` (2026-11-15)
- [ ] Revisão humana das queries, rodada piloto, anotação do segundo avaliador e congelamento do gabarito
- [ ] Rodadas oficiais dos Experimentos 1 (recuperação) e 2 (Query Rewriting)
- [ ] Métricas do pipeline PoT (Auto-Healing, barragem por etapa) e latência de inferência (Seção 2, itens 2 e 3 da nota de avaliação)
- [ ] Implementação do formulário e rubrica Likert estruturada para avaliação cega por especialista (`evaluation/likert_rubric.py` — arquivo ainda vazio)
- [ ] Execução dos experimentos comparativos (RAG/PoT vs. Baseline Zero-Shot) e consolidação dos dados na monografia do TCC

---

## Notas Relacionadas

- [Baseline Zero-Shot e Avaliação Científica do TCC](../03-avaliacao-cientifica/baseline-e-metricas-tcc.md)
- [Guia Operacional e Scripts Utilitários](./guia-operacional-e-scripts.md)
- [Decisões de Engenharia DSR](../00-fundamentos/decisoes-dsr.md)
