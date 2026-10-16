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
- [x] Cliente LLM resiliente com health-check, timeout de 300s (`num_ctx=8192`), retry exponencial e suporte a modo mock (`app/services/llm_client.py`)
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

---

## Fase 3: Frontend e Experiência do Usuário (Concluída)

- [x] Aplicação web SPA em React 18 + TypeScript + Vite com Design System *Ocean & Coral* (`frontend/`)
- [x] Autenticação, cadastro e proteção de rotas com `AuthContext.tsx`
- [x] Caderno de Simulado (`SimuladoPage.tsx`) com cronômetro, folha de respostas dinâmica, marcação de revisão e tela pós-submissão de conferência de gabarito
- [x] Interface da Tutora VERA (`ChatPage.tsx`) com renderização matemática KaTeX (`MathText.tsx`), histórico de sessões e card retrátil para o bloco `<pensamento>`
- [x] Dashboard de diagnóstico do estudante por Competências (`C1`–`C7`) e Habilidades (`StudentDashboard.tsx`)
- [x] Containerização com Docker Compose (`Dockerfile`, `docker-compose.yml`)
- [x] Suíte de testes automatizados com Pytest (`tests/` — 16 módulos de teste)

---

## Fase 4: Avaliação Científica e Conclusão do TCC (Em Andamento)

- [ ] Implementação do serviço de execução em modo **Baseline Zero-Shot** para benchmarking controlado (`app/services/baseline_service.py`)
- [ ] Implementação do script de cálculo e consolidação de métricas quantitativas (`evaluation/quantitative.py`)
- [ ] Implementação do formulário e rubrica Likert estruturada para avaliação cega por especialista (`evaluation/likert_rubric.py`)
- [ ] Execução dos experimentos comparativos (RAG/PoT vs. Baseline Zero-Shot) e consolidação dos dados na monografia do TCC

---

## Notas Relacionadas

- [Baseline Zero-Shot e Avaliação Científica do TCC](../03-avaliacao-cientifica/baseline-e-metricas-tcc.md)
- [Guia Operacional e Scripts Utilitários](./guia-operacional-e-scripts.md)
- [Decisões de Engenharia DSR](../00-fundamentos/decisoes-dsr.md)
