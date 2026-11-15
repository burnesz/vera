---
title: "Frontend Web, Design System e Experiência do Usuário"
domain: "frontend-ux"
rules: ["RN-CHAT04", "RN-SIM02", "RN-SIM03", "RN-FB03"]
related_code:
  - "frontend/src/App.tsx"
  - "frontend/src/index.css"
  - "frontend/src/App.css"
  - "frontend/src/components/MathText.tsx"
  - "frontend/src/context/AuthContext.tsx"
  - "frontend/src/pages/HomePage.tsx"
  - "frontend/src/pages/LoginPage.tsx"
  - "frontend/src/pages/RegisterPage.tsx"
  - "frontend/src/pages/StudentDashboard.tsx"
  - "frontend/src/pages/SimuladoPage.tsx"
  - "frontend/src/pages/ChatPage.tsx"
  - "frontend/src/services/api.ts"
  - "frontend/src/services/authService.ts"
  - "frontend/src/services/simuladoService.ts"
  - "frontend/src/services/chatService.ts"
  - "frontend/src/services/dashboardService.ts"
  - "frontend/src/services/feedbackService.ts"
  - "frontend/src/types/simulado.ts"
  - "frontend/src/types/dashboard.ts"
  - "frontend/src/types/feedback.ts"
related_notes:
  - "./tutoria-rag-chat.md"
  - "./simulados-e-diagnostico.md"
  - "./feedback-pedagogico-item.md"
  - "../01-arquitetura-e-dados/visao-arquitetural.md"
---

# Frontend Web, Design System e Experiência do Usuário

O frontend da plataforma VERA (`frontend/`) é uma Single Page Application (SPA) construída com **React 18**, **TypeScript** e **Vite**, estilizada com um Design System proprietário em **Vanilla CSS** (*Ocean & Coral Palette*).

---

## 1. Arquitetura de Páginas e Componentes

| Arquivo | Responsabilidade Principal |
|---|---|
| `src/context/AuthContext.tsx` | Gerenciamento global de sessão JWT, persistência no `localStorage` e proteção de rotas autenticadas. |
| `src/components/MathText.tsx` | Renderizador matemático e Markdown baseado em **KaTeX**: processa blocos `$$...$$`, expressões inline `$...$` e tabelas Markdown de questões e respostas da tutora (`RN-CHAT04`). |
| `src/components/Sidebar.tsx`, `Topbar.tsx`, `Navbar.tsx`, `Footer.tsx` | Componentes estruturais de navegação e layout responsivo. |
| `src/pages/HomePage.tsx` | Landing page apresentando a proposta pedagógica da plataforma VERA. |
| `src/pages/LoginPage.tsx` & `RegisterPage.tsx` | Fluxos de autenticação e criação de conta de estudante. |
| `src/pages/StudentDashboard.tsx` | Painel de diagnóstico alimentado por `GET /dashboard/desempenho`: métricas globais, **7 Competências (`C1`–`C7`)**, **30 Habilidades (`H01`–`H30`)** filtráveis por nível de domínio (Críticas / Em Treino / Consolidadas) e últimas tentativas. |
| `src/pages/SimuladoPage.tsx` | Ambiente completo de prova: cronômetro, navegação pelos 45 itens, marcação de revisão/dúvida, folha de respostas lateral, submissão e tela pós-prova de revisão item a item (enunciado, alternativas, gabarito, justificativa) com card **"Explicação Pedagógica da Tutora VERA"** para questões erradas (`RN-FB01`–`04`) e atalho para o Chat. Falhas da API aparecem num aviso fixo no topo da página (`errorBanner`). |
| `src/pages/ChatPage.tsx` | Interface conversacional com a Tutora VERA: barra lateral de histórico de sessões (`chat_sessions`), exibição retrátil do bloco `<pensamento>` (*Chain-of-Thought*), citações dos materiais didáticos recuperados e renderização KaTeX. |

---

## 2. Camada de Serviços e Integração HTTP (`frontend/src/services/`)

- `api.ts`: instância configurada de cliente HTTP com interceptors para injeção automática do header `Authorization: Bearer <token>`.
- `authService.ts`: chamadas para `/api/v1/auth/login/json`, `/register` e `/me`.
- `simuladoService.ts`: listagem (`/simulados/`), geração de caderno (`/simulados/gerar`), carregamento de prova ativa, submissão (`/submeter`), resultados (`/tentativas/{id}`, `/{id}/resultado`), histórico (`/tentativas/me`) e exclusão. **Sem dados fictícios**: não há caderno, gabarito ou correção simulados no cliente nem cache local de simulados/resultados; toda falha da API é propagada como `ApiError` e exibida ao estudante. O `localStorage` guarda apenas o rascunho da prova em andamento (respostas e cronômetro), preservado se a submissão falhar. Decisão de 2026-11-15: o fallback mock anterior podia apresentar questões e notas falsas como reais durante a avaliação/defesa.
- `chatService.ts`: envio de mensagens (`/chat`), listagem de sessões (`/chat/sessions`), histórico (`/chat/history/{session_id}`), exclusão e renomeação (`DELETE`/`PATCH /chat/session/{session_id}`).
- `dashboardService.ts`: diagnóstico consolidado (`/dashboard/desempenho`).
- `feedbackService.ts`: geração (`POST /feedback/explicar`) e consulta (`GET /feedback/{resposta_item_id}`) do feedback por item.

---

## 3. Diretrizes de UI e Renderização Matemática

1. **Compatibilidade Estrita com `MathText.tsx`**: qualquer texto matemático vindo do backend (enunciados, alternativas, justificativas de questões inéditas ou respostas do chat) deve utilizar delimitadores `$` ou `$$` balanceados para evitar quebras de renderização no KaTeX.
2. **Transparência Pedagógica**: na `ChatPage.tsx`, o raciocínio interno (`thought`) nunca deve ser misturado ao texto principal da resposta (`reply`); ele deve permanecer encapsulado no card expansível de raciocínio da tutora. O mesmo vale para `feedback_content` vs. `thought_scratchpad` no card de feedback da `SimuladoPage.tsx`.

---

## Notas Relacionadas

- [Fluxo da Tutora Virtual VERA (Chat RAG)](./tutoria-rag-chat.md)
- [Fluxo de Simulados e Diagnóstico](./simulados-e-diagnostico.md)
- [Visão Arquitetural e Infraestrutura](../01-arquitetura-e-dados/visao-arquitetural.md)
