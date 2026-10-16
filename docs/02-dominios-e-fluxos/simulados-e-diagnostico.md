---
title: "Fluxo de Simulados Estratificados e Diagnóstico por Habilidade"
domain: "simulados-diagnostico"
rules: ["RN-SIM01", "RN-SIM02", "RN-SIM03"]
related_code:
  - "app/services/simulado_service.py"
  - "app/api/v1/simulado.py"
  - "app/api/v1/dashboard.py"
  - "app/schemas/simulado.py"
  - "app/db/models/simulado.py"
  - "app/db/models/submission.py"
  - "app/db/models/history.py"
  - "frontend/src/pages/SimuladoPage.tsx"
  - "frontend/src/pages/StudentDashboard.tsx"
related_notes:
  - "../01-arquitetura-e-dados/modelo-relacional.md"
  - "./geracao-questoes-pot.md"
  - "./frontend-e-ux.md"
---

# Fluxo de Simulados Estratificados e Diagnóstico por Habilidade

O módulo de simulados (`app/services/simulado_service.py`) reproduz a estrutura oficial do caderno de Matemática e suas Tecnologias do ENEM (45 itens), combinando questões históricas do INEP e questões inéditas validadas pelo pipeline PoT.

---

## 1. Regras de Negócio de Simulados (`RN-SIM01` a `RN-SIM03`)

### `RN-SIM01` — Montagem Estratificada do Caderno de 45 Questões (`gerar_simulado_enem`)
Cada simulado contém exatamente **45 questões** selecionadas por amostragem estratificada em 3 estágios:

1. **Proporção Híbrida Configurável (`proporcao_ineditas = 0.15` por padrão)**:
   - **Cota de Inéditas (15% = 7 itens)**: selecionadas dentre as questões com `is_validated = True` em `questoes_ineditas`, garantindo no máximo 1 questão inédita por habilidade sorteada. Caso o banco possua menos inéditas disponíveis, as vagas remanescentes são automaticamente transferidas para a cota histórica.
   - **Cota de Históricas (85% = 38 itens)**: selecionadas a partir das 402 questões reais em `questoes_enem`.
2. **Estágio 1 — Cobertura Horizontal da Matriz (28 habilidades textuais)**:
   - O algoritmo garante primeiro 1 questão para cada uma das habilidades disponíveis no acervo textual que ainda não tenha recebido questão inédita na etapa anterior.
3. **Estágio 2 — Complemento pelas Habilidades de Maior Peso Histórico (17 itens complementares)**:
   - As vagas restantes para completar 45 itens são preenchidas priorizando:
     - `HABILIDADES_TOP13` (habilidades com $\ge 15$ questões históricas no acervo: `H01, H02, H03, H04, H11, H12, H16, H17, H18, H19, H21, H28, H29`).
     - Sorteio complementar dentre `HABILIDADES_EMPATADAS_14` (`H05, H10, H14, H23, H27, H30`), evitando repetição de `questao.id` dentro do mesmo caderno.
4. **Embaralhamento e Persistência (*Exclusive Arc*)**:
   - Os 45 itens (históricos + inéditos) são embaralhados aleatoriamente e gravados em `simulado_itens` com `ordem` de `1` a `45` e `origem_questao` (`'enem'` ou `'inedita'`).

### `RN-SIM02` — Omissão Estrita de Gabarito Durante a Prova
- O endpoint de consulta do caderno (`GET /api/v1/simulados/{simulado_id}`) e o schema de exibição de prova ativa **nunca** retornam os campos `gabarito` ou `justificativa`.
- Isso impede vazamento de respostas no DevTools/rede do navegador enquanto o estudante realiza o simulado.

### `RN-SIM03` — Submissão, Correção Automática e Atualização de Diagnóstico
- Ao submeter as respostas (`POST /api/v1/simulados/{simulado_id}/submeter`):
  1. O backend compara cada alternativa marcada com o gabarito oficial da questão correspondente (`questoes_enem` ou `questoes_ineditas`).
  2. Persiste a tentativa (`simulado_tentativas`) com `total_acertos`, `score_percentual` e os registros individuais em `respostas_itens`.
  3. Atualiza a tabela agregadora `desempenho_habilidades` do estudante, recalculando `taxa_acerto` e classificando o `nivel_dominio` (`critico`, `em_desenvolvimento` ou `consolidado`).
  4. Libera o relatório completo de conferência (alternativa marcada, gabarito oficial, status de acerto/erro, justificativa/resolução e código da habilidade) com atalho direto para abrir a **Tutora VERA** contextualizada na questão errada.

---

## Notas Relacionadas

- [Modelo de Dados e Persistência Relacional](../01-arquitetura-e-dados/modelo-relacional.md)
- [Fluxo da Tutora Virtual VERA (Chat RAG)](./tutoria-rag-chat.md)
- [Frontend e Experiência do Usuário](./frontend-e-ux.md)
