---
title: "Visão Geral, Escopo Pedagógico e Glossário do VERA"
domain: "fundamentos"
rules: ["ESCOPO-ENEM-MAT"]
related_code:
  - "data/habilidades_queries.json"
  - "scripts/seed_habilidades.py"
  - "app/db/models/habilidade.py"
related_notes:
  - "./decisoes-dsr.md"
  - "../01-arquitetura-e-dados/visao-arquitetural.md"
  - "../03-avaliacao-cientifica/baseline-e-metricas-tcc.md"
---

# Visão Geral, Escopo Pedagógico e Glossário

> Nota integrante da Memória do Projeto **VERA** (*Validação e Ensino com Recuperação Aumentada*), derivada do TCC *"VERA: uma plataforma baseada em RAG para feedback pedagógico personalizado e geração de questões inéditas de Matemática no contexto do ENEM"* (Metodologia *Design Science Research* — DSR).

---

## 1. Propósito do Sistema

**VERA** é uma plataforma educacional inteligente projetada para apoiar estudantes na preparação para a prova de **Matemática e suas Tecnologias do ENEM**, articulando cinco capacidades centrais:

1. **Aplicação de Simulados Oficiais do ENEM**: caderno com **45 itens de Matemática** montados por amostragem estratificada pelas 30 habilidades oficiais (`H01` a `H30`) da Matriz de Referência do INEP, mesclando questões históricas reais (85%) e questões inéditas validadas por IA (15%).
2. **Diagnóstico de Lacunas e Desempenho**: correção automática de submissões, agregação contínua de domínio por habilidade (`critico`, `em_desenvolvimento`, `consolidado`) e visualização por Competência (`C1` a `C7`).
3. **Tutoria Pedagógica Interativa (Chat RAG)**: a tutora virtual VERA atende o estudante em sessões conversacionais persistentes com *Query Rewriting* (resolução de anáforas), recuperação semântica no acervo de materiais didáticos (`materiais_didaticos`), raciocínio passo a passo explícito via *Chain-of-Thought* (`<pensamento>`), citações de fontes e renderização matemática em LaTeX / KaTeX.
4. **Geração de Questões Inéditas com Garantia Matemática (PoT)**: pipeline *Program-Aided Generation* em que o LLM redige a situação-problema e uma função Python `resolver()`, executada em subprocesso isolado com validação de AST, nexo numérico (*groundedness*), *Auto-Healing* de distratores e validação cega em 3 etapas.
5. **Privacidade, Reprodutibilidade e Comparação Científica**: inferência 100% local com o modelo **Qwen 2.5 7B Instruct** (`qwen2.5:7b-instruct-q4_K_M`) via daemon do **Ollama**, sem custo por chamada e preparada para experimentos empíricos controlados (**Baseline Zero-Shot vs. RAG**).

---

## 2. Escopo Fechado e Rastreabilidade Acadêmica

- **Restrição Temática Estrita (`ESCOPO-ENEM-MAT`)**: o sistema atua **exclusivamente em Matemática e suas Tecnologias do ENEM** (Competências `C1` a `C7`, Habilidades `H01` a `H30`).
- **Justificativa Metodológica**: o escopo fechado garante conformidade estrita com a Matriz de Referência do INEP, viabiliza o *groundedness* algorítmico via interpretador Python e permite avaliação qualitativa profunda por especialista humano em Matemática do Ensino Médio.
- **Regra de Rastreabilidade DSR**: toda decisão de implementação ou alteração arquitetural deve:
  1. Ser rastreável a um objetivo formal do TCC; **ou**
  2. Estar registrada em [Decisões de Engenharia DSR](./decisoes-dsr.md), justificada por ciclos empíricos de performance, confiabilidade pedagógica ou mitigação de limitações de modelos locais de 7B parâmetros.

---

## 3. Matriz de Competências do ENEM (Matemática)

As 30 habilidades (`H01`–`H30`), cadastradas na tabela `habilidades_enem` via `scripts/seed_habilidades.py`, distribuem-se nas 7 Competências de Área do INEP:

| Competência | Eixo Temático Principal | Habilidades |
|---|---|---|
| **C1** | Construir significados para os números naturais, inteiros, racionais e reais | `H01` a `H05` |
| **C2** | Utilizar o conhecimento geométrico para realizar a leitura e a representação da realidade | `H06` a `H09` |
| **C3** | Construir noções de grandezas e medidas para a compreensão da realidade | `H10` a `H14` |
| **C4** | Construir noções de variação de grandezas para a compreensão da realidade | `H15` a `H18` |
| **C5** | Modelar e resolver problemas que envolvem variáveis socioeconômicas ou técnico-científicas (Álgebra/Funções) | `H19` a `H23` |
| **C6** | Interpretar informações de natureza científica e social obtidas da leitura de gráficos e tabelas | `H24` a `H26` |
| **C7** | Compreender o caráter aleatório e não-determinístico dos fenômenos naturais e sociais (Probabilidade/Estatística) | `H27` a `H30` |

---

## 4. Glossário Técnico e Pedagógico

| Termo | Significado no Projeto VERA |
|---|---|
| **RAG** | *Retrieval-Augmented Generation* — recuperação aumentada por busca vetorial semântica no Pinecone. |
| **PoT** | *Program-Aided Generation* — arquitetura onde o LLM gera código Python (`def resolver()`) e o interpretador executa os cálculos deterministicamente. |
| **CoT** | *Chain-of-Thought* — raciocínio interno estruturado passo a passo (`<pensamento>`) emitido antes da resposta final (`<resposta>`). |
| **DSR** | *Design Science Research* — metodologia científica que orienta o ciclo de construção, avaliação e refinamento dos artefatos do TCC. |
| **Habilidade (`H01`–`H30`)** | Código oficial da Matriz de Referência de Matemática do ENEM/INEP. |
| **Namespace** | Partição lógica dentro do índice Pinecone `vera-math-index` (`materiais_didaticos` e `questoes_enem`). |
| **Groundedness** | Garantia verificada por código de que os literais numéricos operados pelo solver Python constam explicitamente no enunciado ou na `tabela_dados`. |
| **Auto-Healing** | Algoritmo determinístico no backend que substitui distratores duplicados ou em colisão por variações cognitivas plausíveis sem nova chamada ao LLM. |
| **Stateless Retry** | Nova tentativa de geração com contexto 100% limpo e novo sorteio de tema/exemplos quando ocorre falha estrutural irreparável, evitando *context anchoring bias*. |
| **Resolução Cega Pura** | Primeira etapa da validação onde o LLM resolve o item recebendo apenas o enunciado (sem alternativas nem gabarito), evitando *sycophancy* (viés de confirmação). |
| **Baseline** | O mesmo modelo `Qwen2.5-7B-Instruct` operando em modo *zero-shot* (sem RAG e sem exemplos *few-shot*) como controle experimental. |

---

## Notas Relacionadas

- [Decisões de Engenharia DSR](./decisoes-dsr.md)
- [Visão Arquitetural e Infraestrutura](../01-arquitetura-e-dados/visao-arquitetural.md)
- [Pipeline PoT de Geração de Questões Inéditas](../02-dominios-e-fluxos/geracao-questoes-pot.md)
- [Baseline e Avaliação Científica do TCC](../03-avaliacao-cientifica/baseline-e-metricas-tcc.md)
