import { apiFetch, ApiError } from './api';
import type {
  Simulado,
  SimuladoResumo,
  SimuladoSubmissaoPayload,
  SimuladoResultado,
  RespostaItemInput,
  TentativaHistorico,
} from '../types/simulado';

/**
 * Serviço de simulados. Todas as operações dependem do backend: não há caderno,
 * gabarito ou correção simulados no cliente. Falhas da API são propagadas como
 * ApiError para que a interface informe o estudante em vez de exibir dados fictícios.
 */
export const simuladoService = {
  async listarSimulados(): Promise<SimuladoResumo[]> {
    const res = await apiFetch<SimuladoResumo[]>('/simulados/');
    return Array.isArray(res) ? res : [];
  },

  async gerarSimulado(titulo?: string): Promise<Simulado> {
    const res = await apiFetch<Simulado>('/simulados/gerar', {
      method: 'POST',
      body: JSON.stringify({
        titulo: titulo || 'Simulado Geral de Matemática — ENEM (45 Questões)',
        tipo: 'geral_45',
        proporcao_ineditas: 0.15,
      }),
    });

    if (!res || !Array.isArray(res.itens) || res.itens.length === 0) {
      throw new ApiError('O servidor não retornou questões para o simulado. Verifique o acervo de questões.', 0);
    }
    return res;
  },

  async obterSimulado(id: string): Promise<Simulado> {
    return await apiFetch<Simulado>(`/simulados/${id}`);
  },

  async obterResultadoSimulado(simuladoId: string, tentativaId?: string): Promise<SimuladoResultado> {
    if (tentativaId) {
      return await apiFetch<SimuladoResultado>(`/simulados/tentativas/${tentativaId}`);
    }
    return await apiFetch<SimuladoResultado>(`/simulados/${simuladoId}/resultado`);
  },

  async submeterSimulado(simuladoId: string, respostas: RespostaItemInput[]): Promise<SimuladoResultado> {
    const payload: SimuladoSubmissaoPayload = { respostas };
    return await apiFetch<SimuladoResultado>(`/simulados/${simuladoId}/submeter`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async excluirSimulado(simuladoId: string): Promise<void> {
    await apiFetch<void>(`/simulados/${simuladoId}`, {
      method: 'DELETE',
    });
  },

  async listarMinhasTentativas(): Promise<TentativaHistorico[]> {
    const res = await apiFetch<TentativaHistorico[]>('/simulados/tentativas/me');
    return Array.isArray(res) ? res : [];
  },
};
