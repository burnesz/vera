import { apiFetch } from './api';
import type {
  ChatRequest,
  ChatResponse,
  ChatHistoryResponse,
  ChatSessionSummary,
  ChatSessionListResponse
} from '../types/chat';

export const chatService = {
  /**
   * Envia uma mensagem para o endpoint real do backend FastAPI (/api/v1/chat),
   * que consulta Pinecone (RAG) e executa o Qwen2.5 via Ollama local com CoT.
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return await apiFetch<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Lista as sessões anteriores de conversa do estudante salvas no PostgreSQL.
   */
  async listSessions(): Promise<ChatSessionSummary[]> {
    try {
      const response = await apiFetch<ChatSessionListResponse>('/chat/sessions');
      return response.sessions || [];
    } catch (err) {
      console.warn('Não foi possível listar sessões do chat:', err);
      return [];
    }
  },

  /**
   * Recupera o histórico de mensagens de uma sessão específica no PostgreSQL.
   */
  async getHistory(sessionId: string): Promise<ChatHistoryResponse> {
    try {
      return await apiFetch<ChatHistoryResponse>(`/chat/history/${sessionId}`);
    } catch {
      return { session_id: sessionId, messages: [] };
    }
  },

  /**
   * Renomeia o título de uma conversa.
   */
  async renameSession(sessionId: string, titulo: string): Promise<boolean> {
    try {
      await apiFetch(`/chat/session/${sessionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ titulo }),
      });
      return true;
    } catch (err) {
      console.error('Erro ao renomear sessão de conversa:', err);
      return false;
    }
  },

  /**
   * Exclui permanentemente uma sessão de conversa e todas as mensagens associadas.
   */
  async deleteSession(sessionId: string): Promise<boolean> {
    try {
      const res = await apiFetch<{ cleared: boolean; message: string }>(`/chat/session/${sessionId}`, {
        method: 'DELETE',
      });
      return res.cleared;
    } catch (err) {
      console.error('Erro ao excluir sessão de conversa:', err);
      return false;
    }
  },

  /**
   * Alias para limpar/excluir histórico de sessão.
   */
  async clearSession(sessionId: string): Promise<{ cleared: boolean }> {
    const success = await this.deleteSession(sessionId);
    return { cleared: success };
  },
};
