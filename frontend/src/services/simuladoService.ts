import { apiFetch } from './api';
import type {
  Simulado,
  SimuladoSubmissaoPayload,
  SimuladoResultado,
  QuestaoItem,
  AlternativaLetra,
} from '../types/simulado';

// Banco demonstrativo estuturado de 45 questões caso o backend esteja em modo offline
function gerarCadernoMock45(): Simulado {
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
  async gerarSimulado(): Promise<Simulado> {
    try {
      const res = await apiFetch<Simulado>('/simulados/gerar', {
        method: 'POST',
        body: JSON.stringify({
          titulo: 'Simulado Geral de Matemática — ENEM (45 Questões)',
          tipo: 'geral_45',
          proporcao_ineditas: 0.2,
        }),
      });

      if (res && res.itens && res.itens.length > 0) {
        return res;
      }
      return gerarCadernoMock45();
    } catch (error) {
      console.warn('Backend indisponível ou vazio, utilizando caderno de 45 questões padrão:', error);
      return gerarCadernoMock45();
    }
  },

  async obterSimulado(id: string): Promise<Simulado> {
    try {
      return await apiFetch<Simulado>(`/simulados/${id}`);
    } catch {
      return gerarCadernoMock45();
    }
  },

  async submeterSimulado(
    simuladoId: string,
    respostas: Array<{ questao_id: string; alternativa_marcada: AlternativaLetra | 'X' }>,
    itens: QuestaoItem[]
  ): Promise<SimuladoResultado> {
    try {
      const payload: SimuladoSubmissaoPayload = { respostas };
      return await apiFetch<SimuladoResultado>(`/simulados/${simuladoId}/submeter`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } catch (error) {
      console.warn('Submissão offline/mock calculando resultado local:', error);
      // Cálculo local de conferência
      let acertos = 0;
      const itensCorrecao = itens.map((item) => {
        const resp = respostas.find((r) => r.questao_id === item.questao_id);
        const marcada = resp?.alternativa_marcada !== 'X' ? resp?.alternativa_marcada : null;
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

      return {
        tentativa_id: 'tentativa-mock-' + Date.now(),
        simulado_id: simuladoId,
        user_id: 'user-demo',
        status: 'finalizado',
        total_itens: itens.length,
        total_acertos: acertos,
        score_percentual: Number(((acertos / itens.length) * 100).toFixed(1)),
        started_at: new Date(Date.now() - 3600000).toISOString(),
        completed_at: new Date().toISOString(),
        itens: itensCorrecao,
      };
    }
  },
};
