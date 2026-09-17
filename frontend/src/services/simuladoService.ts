import { apiFetch } from './api';
import type {
  Simulado,
  SimuladoResumo,
  SimuladoSubmissaoPayload,
  SimuladoResultado,
  QuestaoItem,
  AlternativaLetra,
  RespostaItemInput,
} from '../types/simulado';

// Banco demonstrativo estuturado de 45 questões caso o backend esteja em modo offline
function gerarCadernoMock45(userId?: string): Simulado {
  const habilidades = [
    'H01', 'H02', 'H03', 'H04', 'H05', 'H06', 'H07', 'H08', 'H09', 'H10',
    'H11', 'H12', 'H13', 'H14', 'H15', 'H16', 'H17', 'H18', 'H19', 'H20',
    'H21', 'H22', 'H23', 'H24', 'H25', 'H26', 'H27', 'H28', 'H29', 'H30',
    'H01', 'H02', 'H03', 'H04', 'H08', 'H10', 'H15', 'H16', 'H19', 'H21',
    'H24', 'H25', 'H27', 'H28', 'H30'
  ];

  const questoesMock: QuestaoItem[] = habilidades.map((hab, idx) => {
    const ordem = idx + 1;
    const isEnem = ordem % 3 !== 0;

    return {
      simulado_item_id: `mock-item-${ordem}`,
      ordem,
      origem_questao: isEnem ? 'enem' : 'inedita',
      questao_id: `mock-q-${ordem}`,
      ano: isEnem ? 2019 + (ordem % 5) : null,
      habilidade_codigo: hab,
      enunciado: `(Questão ${ordem} - ENEM) Um pesquisador analisa a variação de um determinado índice de produtividade ao longo de ${ordem * 2} dias. Observou-se que o crescimento seguiu um modelo linear definido pela função f(x) = ${ordem}x + ${(ordem * 3) % 25}. Considerando as condições apresentadas para a competência avaliada pela habilidade ${hab}, qual é o valor estimado para o índice correspondente ao período x = 5?`,
      alternativas: {
        A: `${ordem * 5 + 5}`,
        B: `${ordem * 5 + 10}`,
        C: `${ordem * 5 + 15}`,
        D: `${ordem * 5 + 20}`,
        E: `${ordem * 5 + 25}`,
      },
    };
  });

  return {
    id: 'mock-simulado-45',
    user_id: userId || null,
    titulo: 'Simulado Geral de Matemática — Caderno Padrão ENEM (45 Questões)',
    descricao: 'Caderno equilibrado contemplando todas as 30 habilidades da Matriz de Referência do ENEM.',
    tipo: 'geral_45',
    total_itens: 45,
    total_enem: 30,
    total_ineditas: 15,
    itens: questoesMock,
    created_at: new Date().toISOString(),
  };
}

export const simuladoService = {
  async listarSimulados(userId?: string): Promise<SimuladoResumo[]> {
    try {
      const res = await apiFetch<SimuladoResumo[]>('/simulados/');
      if (Array.isArray(res)) {
        return res;
      }
      return [];
    } catch (error) {
      console.warn('Erro ao listar simulados da API:', error);
      const salvosLocalmente = localStorage.getItem(`vera_simulados_${userId || 'demo'}`);
      if (salvosLocalmente) {
        try {
          return JSON.parse(salvosLocalmente);
        } catch {
          return [];
        }
      }
      return [];
    }
  },

  async gerarSimulado(titulo?: string, userId?: string): Promise<Simulado> {
    try {
      const res = await apiFetch<Simulado>('/simulados/gerar', {
        method: 'POST',
        body: JSON.stringify({
          titulo: titulo || 'Simulado Geral de Matemática — ENEM (45 Questões)',
          tipo: 'geral_45',
          proporcao_ineditas: 0.15,
        }),
      });

      if (res && res.itens && res.itens.length > 0) {
        return res;
      }
      return gerarCadernoMock45(userId);
    } catch (error) {
      console.warn('Backend indisponível ou vazio, utilizando caderno de 45 questões padrão:', error);
      const mock = gerarCadernoMock45(userId);
      const storageKey = `vera_simulados_${userId || 'demo'}`;
      try {
        const salvos = localStorage.getItem(storageKey);
        const list: SimuladoResumo[] = salvos ? JSON.parse(salvos) : [];
        if (!list.some((s) => s.id === mock.id)) {
          list.unshift({
            id: mock.id,
            titulo: mock.titulo,
            descricao: mock.descricao,
            tipo: mock.tipo,
            total_itens: mock.total_itens,
            created_at: mock.created_at,
            status: 'pendente',
          });
          localStorage.setItem(storageKey, JSON.stringify(list));
        }
      } catch {
        // ignore
      }
      return mock;
    }
  },

  async obterSimulado(id: string): Promise<Simulado> {
    try {
      return await apiFetch<Simulado>(`/simulados/${id}`);
    } catch {
      return gerarCadernoMock45();
    }
  },

  async obterResultadoSimulado(simuladoId: string, tentativaId?: string): Promise<SimuladoResultado> {
    try {
      if (tentativaId && !tentativaId.startsWith('tentativa-mock-')) {
        return await apiFetch<SimuladoResultado>(`/simulados/tentativas/${tentativaId}`);
      }
      return await apiFetch<SimuladoResultado>(`/simulados/${simuladoId}/resultado`);
    } catch (error) {
      console.warn('Erro ao obter resultado do simulado da API, tentando cache local:', error);
      const cached = localStorage.getItem(`vera_resultado_${simuladoId}`);
      if (cached) {
        try {
          return JSON.parse(cached);
        } catch {
          // ignore
        }
      }
      throw error;
    }
  },

  async submeterSimulado(
    simuladoId: string,
    respostas: RespostaItemInput[],
    itens: QuestaoItem[],
    userId?: string
  ): Promise<SimuladoResultado> {
    try {
      const payload: SimuladoSubmissaoPayload = { respostas };
      const res = await apiFetch<SimuladoResultado>(`/simulados/${simuladoId}/submeter`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      try {
        localStorage.setItem(`vera_resultado_${simuladoId}`, JSON.stringify(res));
      } catch {
        // ignore
      }

      return res;
    } catch (error) {
      console.warn('Submissão online falhou, calculando e persistindo resultado localmente:', error);
      // Cálculo local de conferência
      let acertos = 0;
      const itensCorrecao = itens.map((item) => {
        const resp = respostas.find((r) => r.questao_id === item.questao_id || r.simulado_item_id === item.simulado_item_id);
        const marcada = resp && resp.alternativa_selecionada !== 'X'
          ? (resp.alternativa_selecionada as AlternativaLetra)
          : null;
        // Gabarito mock fixo determinado pela ordem
        const gabaritos: AlternativaLetra[] = ['A', 'B', 'C', 'D', 'E'];
        const gabaritoOficial = gabaritos[(item.ordem - 1) % 5];
        const isCorreto = marcada === gabaritoOficial;
        if (isCorreto) acertos++;

        return {
          ordem: item.ordem,
          simulado_item_id: item.simulado_item_id,
          questao_id: item.questao_id,
          habilidade_codigo: item.habilidade_codigo,
          alternativa_selecionada: marcada,
          gabarito_oficial: gabaritoOficial,
          is_correto: isCorreto,
        };
      });

      const resultadoLocal: SimuladoResultado = {
        tentativa_id: 'tentativa-mock-' + Date.now(),
        simulado_id: simuladoId,
        user_id: userId || 'user-demo',
        status: 'finalizado',
        total_itens: itens.length,
        total_acertos: acertos,
        score_percentual: Number(((acertos / itens.length) * 100).toFixed(1)),
        started_at: new Date(Date.now() - 3600000).toISOString(),
        completed_at: new Date().toISOString(),
        itens: itensCorrecao,
      };

      // Atualiza lista local persistida para refletir no hub
      const storageKey = `vera_simulados_${userId || 'demo'}`;
      try {
        const salvos = localStorage.getItem(storageKey);
        if (salvos) {
          const list: SimuladoResumo[] = JSON.parse(salvos);
          const itemIdx = list.findIndex((s) => s.id === simuladoId);
          if (itemIdx >= 0) {
            list[itemIdx] = {
              ...list[itemIdx],
              status: 'finalizado',
              tentativa_id: resultadoLocal.tentativa_id,
              total_acertos: resultadoLocal.total_acertos,
              score_percentual: resultadoLocal.score_percentual,
              completed_at: resultadoLocal.completed_at,
            };
            localStorage.setItem(storageKey, JSON.stringify(list));
          }
        }
        localStorage.setItem(`vera_resultado_${simuladoId}`, JSON.stringify(resultadoLocal));
      } catch {
        // ignore
      }

      return resultadoLocal;
    }
  },

  async excluirSimulado(simuladoId: string, userId?: string): Promise<void> {
    try {
      await apiFetch<void>(`/simulados/${simuladoId}`, {
        method: 'DELETE',
      });
    } catch (error) {
      console.warn('Erro ao excluir simulado na API:', error);
      // Fallback para persistência local caso offline
      const storageKey = `vera_simulados_${userId || 'demo'}`;
      const salvos = localStorage.getItem(storageKey);
      if (salvos) {
        try {
          const list: SimuladoResumo[] = JSON.parse(salvos);
          const filtrados = list.filter((s) => s.id !== simuladoId);
          localStorage.setItem(storageKey, JSON.stringify(filtrados));
        } catch {
          // ignore
        }
      }
      throw error;
    }
  },
};

