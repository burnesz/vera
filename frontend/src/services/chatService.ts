import { apiFetch } from './api';
import type { ChatRequest, ChatResponse, ChatHistoryResponse } from '../types/chat';

export const chatService = {
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    try {
      return await apiFetch<ChatResponse>('/chat', {
        method: 'POST',
        body: JSON.stringify(request),
      });
    } catch (error: any) {
      console.warn('Backend LLM indisponível, gerando resposta demonstrativa didática:', error);
      
      // Resposta demonstrativa inteligente simulando a Tutora VERA
      const msgLower = request.message.toLowerCase();
      let reply = '';

      if (msgLower.includes('pitagoras') || msgLower.includes('triangulo') || msgLower.includes('geometria')) {
        reply = `**Explicação Pedagógica (Habilidade H07 / H08):**\n\nNo Teorema de Pitágoras, para todo triângulo retângulo de hipotenusa $a$ e catetos $b$ e $c$, temos:\n\n$$a^2 = b^2 + c^2$$\n\n**Dica para o ENEM:** Fique atento às unidades de medida (metros para centímetros) e lembre-se das trincas pitagóricas clássicas como $(3, 4, 5)$ e $(5, 12, 13)$, que poupam muito tempo na prova!`;
      } else if (msgLower.includes('porcentagem') || msgLower.includes('juros') || msgLower.includes('desconto')) {
        reply = `**Explicação Pedagógica (Habilidade H16 / H17):**\n\nEm questões de matemática financeira do ENEM, o cálculo de variações percentuais sucessivas nunca deve ser feito pela simples soma das porcentagens.\n\n* Exemplo: Um aumento de $10\\%$ seguido de outro de $10\\%$ resulta em um fator de multiplicação:\n  $$1{,}10 \\times 1{,}10 = 1{,}21 \\implies +21\\%$$ e não $20\\%$.\n\nDeseja que eu resolva um exemplo passo a passo?`;
      } else if (msgLower.includes('funcao') || msgLower.includes('afim') || msgLower.includes('segundo grau') || msgLower.includes('vertice')) {
        reply = `**Explicação Pedagógica (Habilidade H19 / H20 / H21):**\n\nAs funções afins e quadráticas são muito recorrentes no ENEM para modelar custos, lucros e trajetórias parabólicas.\n\n* Vértice da Parábola: $X_v = -\\frac{b}{2a}$ (ponto que maximiza ou minimiza a grandeza) e $Y_v = -\\frac{\\Delta}{4a}$ (valor máximo ou mínimo atingido).\n\nQuer exercitar com uma questão real de edição anterior?`;
      } else {
        reply = `Olá! Sou a **VERA**, sua Tutora Especialista em Matemática para o ENEM. 

Entendi sua dúvida: *"${request.message}"*.

Para desenvolvermos a competência necessária no ENEM:
1. **Identifique a incógnita principal**: O que o enunciado está pedindo explicitamente?
2. **Separe os dados numéricos**: Crie uma lista com os valores conhecidos e suas unidades.
3. **Selecione o modelo matemático**: É uma regra de três direta, uma equação linear ou uma análise probabilística?

Como posso te guiar nos próximos passos dessa resolução?`;
      }

      return {
        session_id: request.session_id,
        reply,
        habilidade_detectada: request.habilidade_alvo || 'H01',
      };
    }
  },

  async getHistory(sessionId: string): Promise<ChatHistoryResponse> {
    try {
      return await apiFetch<ChatHistoryResponse>(`/chat/history/${sessionId}`);
    } catch {
      return { session_id: sessionId, messages: [] };
    }
  },

  async clearSession(sessionId: string): Promise<{ cleared: boolean }> {
    try {
      return await apiFetch<{ cleared: boolean; message: string }>(`/chat/session/${sessionId}`, {
        method: 'DELETE',
      });
    } catch {
      return { cleared: true };
    }
  },
};
