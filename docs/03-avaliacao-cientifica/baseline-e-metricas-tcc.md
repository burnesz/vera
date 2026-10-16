---
title: "Baseline Zero-Shot e Avaliação Científica do TCC (DSR)"
domain: "avaliacao-cientifica"
rules: ["RN-AVAL01", "RN-AVAL02"]
related_code:
  - "app/services/baseline_service.py"
  - "evaluation/quantitative.py"
  - "evaluation/likert_rubric.py"
related_notes:
  - "../00-fundamentos/visao-e-escopo.md"
  - "../00-fundamentos/decisoes-dsr.md"
  - "../04-operacoes-e-roadmap/roadmap-e-status.md"
---

# Baseline Zero-Shot e Avaliação Científica do TCC (DSR)

Para fundamentar a monografia de TCC sob a ótica da metodologia **Design Science Research (DSR)**, a plataforma VERA foi projetada para permitir a avaliação empírica rigorosa dos artefatos construídos frente a uma condição de controle científica (**Baseline Zero-Shot**).

---

## 1. Configuração da Baseline Experimental (Zero-Shot)

- **Isolamento da Variável Independente**:
  - A condição **Baseline** (`app/services/baseline_service.py`) utiliza exatamente o **mesmo modelo local** (`qwen2.5:7b-instruct-q4_K_M` via Ollama) e a mesma infraestrutura de hardware.
  - Opera em modo **zero-shot**: sem recuperação vetorial no Pinecone (`materiais_didaticos` / `questoes_enem`) e sem injeção de exemplos *few-shot* da Matriz do ENEM.
- **Justificativa Científica**: Garante uma comparação controlada e justa onde a arquitetura RAG + PoT é a variável manipulada em relação ao modelo base puro.

---

## 2. Métricas Quantitativas (`evaluation/quantitative.py`)

O módulo de avaliação quantitativa acompanha três dimensões de performance e confiabilidade:

1. **Qualidade da Recuperação Vetorial (RAG)**:
   - *Precision@K* e *Recall@K* na busca semântica sobre os namespaces `materiais_didaticos` e `questoes_enem`.
   - Impacto do *Query Rewriting* (`RN-CHAT01`) no score de similaridade cosseno em turnos conversacionais com anáforas.
2. **Desempenho e Latência de Inferência Local**:
   - Tempo médio de resposta por chamada ao Ollama (Chat RAG vs. Etapas do Pipeline PoT vs. Baseline).
3. **Taxa de Retenção, Auto-Healing e Barragem de Alucinações**:
   - Percentual de questões recuperadas em 0ms pelo **Auto-Healing Algorítmico** (`auto_heal_distractors` — `DSR-05`).
   - Percentual de itens defeituosos barrados por etapa:
     - Violação de *groundedness* numérico ou exceção no `CodeExecutor`.
     - Divergência matemática no Confronto de Equivalência (*Early Exit* na Etapa 2 — `DSR-06`).
     - Reprovação nas 5 flags da Auditoria Semântica (Etapa 3 — `DSR-06`).

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
