import { apiFetch } from './api';
import type { FeedbackVera } from '../types/feedback';

export const feedbackService = {
  /**
   * Solicita à Tutora VERA a geração (ou resgate do cache) de um feedback explicativo
   * analítico e pedagógico para uma resposta errada do estudante em um item de simulado.
   */
  async solicitarFeedback(respostaItemId: string): Promise<FeedbackVera> {
    return await apiFetch<FeedbackVera>('/feedback/explicar', {
      method: 'POST',
      body: JSON.stringify({ resposta_item_id: respostaItemId }),
    });
  },

  /**
   * Consulta se já existe um feedback previamente salvo para este item de resposta.
   */
  async obterFeedback(respostaItemId: string): Promise<FeedbackVera | null> {
    try {
      return await apiFetch<FeedbackVera>(`/feedback/${respostaItemId}`);
    } catch {
      return null;
    }
  },
};
