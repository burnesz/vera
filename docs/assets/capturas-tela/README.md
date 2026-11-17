# Capturas de tela da VERA

Telas usadas na demonstração da monografia (Seção 6.1). Todas estão em 16:9 (3200 × 1800 px, janela de 1600 × 900 com escala 2x) e foram geradas em 16/11/2026 por `scripts/capturar_telas.py`.

- **Contas e dados:** as contas são fictícias (`scripts/seed_alunos_ficticios.py`), e as respostas dos simulados foram simuladas pela TRI.
- **Feedbacks e conversas:** foram gerados pela própria plataforma (`scripts/gerar_conteudo_demo.py`), com o Qwen3 8B local e o limite de 3.072 tokens (`RN-INF07`).

| Arquivo | Conta | O que mostra |
|---|---|---|
| `01_inicio.png` | — | Página inicial, sem login |
| `02_login.png` | Mariana | Tela de acesso preenchida |
| `03_painel_resumo.png` | Mariana | Painel: saudação, 4 indicadores e ações rápidas |
| `04_painel_competencias.png` | Mariana | Proficiência nas 7 competências (C1–C7), com status e barras de acerto |
| `05_painel_habilidades_criticas.png` | Mariana | Matriz de habilidades filtrada em "Críticas", com o botão "Estudar" |
| `06_meus_simulados.png` | Mariana | Simulados finalizados, com aproveitamento |
| `07_gerar_simulado.png` | Mariana | Janela de geração de um novo simulado de 45 questões |
| `08_caderno_prova.png` | Lucas | Caderno de prova: cronômetro, grade 1–45 e questão inédita com o selo "Gerado por Vera" |
| `09_caderno_grade.png` | Lucas | Grade com questões respondidas, marcada para revisão e pendentes |
| `10_entrega_confirmacao.png` | Lucas | Confirmação de entrega, com o aviso de questões sem resposta |
| `11_relatorio_desempenho.png` | Mariana | Relatório de desempenho do simulado: acertos, taxa e navegação pelos itens |
| `12_gabarito_rapido.png` | Mariana | Gabarito rápido: resposta, gabarito e habilidade de cada item |
| `13_questao_errada.png` | Mariana | Revisão de uma questão errada: alternativa marcada × gabarito oficial |
| `14_questao_errada_convite.png` | Mariana | Convite "Pedir explicação da Vera" numa questão sem feedback |
| `15_feedback_vera_inicio.png` | Mariana | Feedback: diagnóstico do distrator e início da resolução passo a passo |
| `16_feedback_vera_continuacao.png` | Mariana | Feedback: fim da resolução, "O que estudar" e o botão para continuar no chat |
| `17_feedback_raciocinio.png` | Mariana | Raciocínio interno da tutora (`<pensamento>`) expandido |
| `18_tutora_inicio.png` | Mariana | Tutora: mensagem inicial, sugestões e histórico de conversas |
| `19_tutora_conversa_1.png` | Mariana | 1ª pergunta ("Como eu calculo o volume de um cilindro?") e resposta |
| `20_tutora_conversa_2.png` | Mariana | 2ª pergunta, que depende da 1ª ("E se eu dobrar o raio…?"), e resposta |
| `21_tutora_fontes.png` | Mariana | Fontes teóricas recuperadas para a resposta |
| `22_tutora_raciocinio.png` | Mariana | Raciocínio pedagógico (chain-of-thought) da tutora expandido |
| `23_admin_ineditas_lote.png` | Administrador | Questões inéditas: montagem de um lote (H03, H12 e H24) e andamento de cada pedido |
| `24_admin_ineditas_revisao.png` | Administrador | Questões inéditas: revisão de uma questão aprovada antes de adicioná-la ao acervo |

## Como refazer

1. Suba a API com `LLM_TIMEOUT_SECONDS=1200` e o frontend.
2. Rode `scripts/seed_alunos_ficticios.py` e `scripts/gerar_conteudo_demo.py`. A geração leva cerca de 35 minutos.
3. Rode `scripts/capturar_telas.py`. A captura leva cerca de 3 minutos.
4. Para as telas 23 e 24:
   - suba a API do serviço `questoes-ineditas-enem` com o comando `./.venv/bin/uvicorn app.api:app --port 8100`;
   - gere um lote real pela própria tela, como administrador, com H03, H12 e H24, 1 questão cada (cerca de 30 minutos);
   - rode `scripts/capturar_telas_admin.py <senha do admin> <id do lote> docs/assets/capturas-tela H03,H12,H24 H24`.
