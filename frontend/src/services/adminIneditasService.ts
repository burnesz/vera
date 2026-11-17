import { apiFetch } from './api';

export interface HabilidadeAtiva {
  codigo: string;
  descricao: string;
}

export interface QuestaoGerada {
  id: string;
  habilidade_codigo: string;
  enunciado: string;
  alternativas: Record<string, string>;
  gabarito: string;
  justificativa: string;
  no_acervo?: boolean;
}

export type StatusPedido = 'aguardando' | 'gerando' | 'aprovada' | 'reprovada' | 'nao_gerado';

export interface PedidoLote {
  n: number;
  habilidade: string;
  status: StatusPedido;
  tentativas: number;
  questao: QuestaoGerada | null;
}

export interface Lote {
  id: string;
  status: 'em_andamento' | 'concluido' | 'cancelado' | 'erro';
  erro: string | null;
  max_tentativas: number;
  total: number;
  feitos: number;
  aprovadas: number;
  pedidos: PedidoLote[];
}

const BASE = '/admin/ineditas';

/** Rotas de administrador que repassam os pedidos ao serviço de questões inéditas. */
export const adminIneditasService = {
  habilidades: () => apiFetch<HabilidadeAtiva[]>(`${BASE}/habilidades`),

  criarLote: (habilidades: string[] | 'all', quantidade: number, max_tentativas: number) =>
    apiFetch<{ id: string; total: number }>(`${BASE}/lotes`, {
      method: 'POST',
      body: JSON.stringify({ habilidades, quantidade, max_tentativas }),
    }),

  consultarLote: (id: string) => apiFetch<Lote>(`${BASE}/lotes/${id}`),

  cancelarLote: (id: string) => apiFetch<Lote>(`${BASE}/lotes/${id}/cancelar`, { method: 'POST' }),

  importar: (lote_id: string, questao_ids: string[]) =>
    apiFetch<{ importadas: string[]; ja_existiam: string[] }>(`${BASE}/importar`, {
      method: 'POST',
      body: JSON.stringify({ lote_id, questao_ids }),
    }),
};
