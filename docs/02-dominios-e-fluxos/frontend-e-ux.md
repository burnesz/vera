---
title: "Frontend Web, Design System e Experiência do Usuário"
domain: "frontend-ux"
rules: ["RN-CHAT04", "RN-SIM02", "RN-SIM03"]
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
related_notes:
  - "./tutoria-rag-chat.md"
  - "./simulados-e-diagnostico.md"
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
| `src/pages/StudentDashboard.tsx` | Painel de diagnóstico mapeado pelas **7 Competências (`C1`–`C7`)** e **30 Habilidades (`H01`–`H30`)** da Matriz do ENEM, com indicadores de progresso e atalhos para estudo. |
| `src/pages/SimuladoPage.tsx` | Ambiente completo de prova: cronômetro, navegação pelos 45 itens, marcação de revisão/dúvida, folha de respostas lateral, submissão e tela pós-prova de conferência de gabarito com botão **"Tirar dúvida com a VERA"**. |
| `src/pages/ChatPage.tsx` | Interface conversacional com a Tutora VERA: barra lateral de histórico de sessões (`chat_sessions`), exibição retrátil do bloco `<pensamento>` (*Chain-of-Thought*), citações dos materiais didáticos recuperados e renderização KaTeX. |

---

## 2. Camada de Serviços e Integração HTTP (`frontend/src/services/`)

- `api.ts`: instância configurada de cliente HTTP com interceptors para injeção automática do header `Authorization: Bearer <token>`.
- `authService.ts`: chamadas para `/api/v1/auth/login`, `/register` e `/me`.
- `simuladoService.ts`: geração de caderno (`/api/v1/simulados/gerar`), carregamento de prova ativa e submissão de respostas (`/submeter`).
- `chatService.ts`: envio de mensagens para a Tutora VERA (`/api/v1/chat`), listagem de sessões (`/sessions`) e recuperação/exclusão de histórico (`/history/{session_id}`).

---

## 3. Diretrizes de UI e Renderização Matemática

1. **Compatibilidade Estrita com `MathText.tsx`**: qualquer texto matemático vindo do backend (enunciados, alternativas, justificativas de questões inéditas ou respostas do chat) deve utilizar delimitadores `$` ou `$$` balanceados para evitar quebras de renderização no KaTeX.
2. **Transparência Pedagógica**: na `ChatPage.tsx`, o raciocínio interno (`thought`) nunca deve ser misturado ao texto principal da resposta (`reply`); ele deve permanecer encapsulado no card expansível de raciocínio da tutora.

---

## Notas Relacionadas

- [Fluxo da Tutora Virtual VERA (Chat RAG)](./tutoria-rag-chat.md)
- [Fluxo de Simulados e Diagnóstico](./simulados-e-diagnostico.md)
- [Visão Arquitetural e Infraestrutura](../01-arquitetura-e-dados/visao-arquitetural.md)
