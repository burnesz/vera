import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { simuladoService } from '../services/simuladoService';
import type { Simulado, SimuladoResumo, AlternativaLetra, SimuladoResultado } from '../types/simulado';
import { MathText } from '../components/MathText';
import {
  Clock,
  Pause,
  Play,
  Flag,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  Send,
  RotateCcw,
  BotMessageSquare,
  Award,
  Lock,
  Plus,
  ArrowLeft,
  Calendar,
  CheckCircle,
  FileSpreadsheet,
  Layers,
  Save,
} from 'lucide-react';

interface SimuladoPageProps {
  onNavigate: (page: string) => void;
}

type ViewMode = 'hub' | 'exam' | 'result';
type TabType = 'pendentes' | 'arquivados';

export const SimuladoPage: React.FC<SimuladoPageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();

  // Estados de navegação interna da página
  const [viewMode, setViewMode] = useState<ViewMode>('hub');
  const [activeTab, setActiveTab] = useState<TabType>('pendentes');

  // Dados do Hub de Simulados
  const [simulados, setSimulados] = useState<SimuladoResumo[]>([]);
  const [isLoadingList, setIsLoadingList] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [showNewModal, setShowNewModal] = useState<boolean>(false);
  const [novoTitulo, setNovoTitulo] = useState<string>('');

  // Dados do Simulado Ativo (Modo Prova)
  const [simulado, setSimulado] = useState<Simulado | null>(null);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [respostas, setRespostas] = useState<Record<string, AlternativaLetra>>({});
  const [revisao, setRevisao] = useState<Set<string>>(new Set());
  const [secondsRemaining, setSecondsRemaining] = useState<number>(9000);
  const [isTimerRunning, setIsTimerRunning] = useState<boolean>(true);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isLoadingExam, setIsLoadingExam] = useState<boolean>(false);

  // Dados do Resultado (Modo Gabarito)
  const [resultado, setResultado] = useState<SimuladoResultado | null>(null);
  const [isLoadingResult, setIsLoadingResult] = useState<boolean>(false);

  // Carrega a lista de simulados do estudante
  const carregarMeusSimulados = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoadingList(true);
    try {
      const data = await simuladoService.listarSimulados(user?.id);
      setSimulados(data);
    } catch (err) {
      console.error('Erro ao carregar simulados do estudante:', err);
    } finally {
      setIsLoadingList(false);
    }
  }, [isAuthenticated, user]);

  useEffect(() => {
    if (isAuthenticated) {
      carregarMeusSimulados();
    } else {
      setIsLoadingList(false);
    }
  }, [isAuthenticated, carregarMeusSimulados]);

  // Referência mutável para submissão automática pelo temporizador
  const handleSubmitRef = React.useRef<() => void>(() => {});

  // Temporizador do Simulado em Execução
  useEffect(() => {
    if (viewMode !== 'exam' || !isTimerRunning || !simulado) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleSubmitRef.current();
          return 0;
        }
        // Salva periodicamente o tempo restante no localStorage
        if (prev % 10 === 0 && simulado) {
          try {
            localStorage.setItem(`vera_timer_${simulado.id}`, String(prev - 1));
          } catch {
            // storage cheio ou inacessível
          }
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [viewMode, isTimerRunning, simulado]);

  const formatTime = (secs: number) => {
    const hours = Math.floor(secs / 3600);
    const minutes = Math.floor((secs % 3600) / 60);
    const seconds = secs % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes
      .toString()
      .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const formatDate = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  // Abre ou retoma um simulado para realização
  const handleIniciarSimulado = async (simuladoId: string) => {
    setIsLoadingExam(true);
    try {
      const data = await simuladoService.obterSimulado(simuladoId);
      setSimulado(data);
      setCurrentIndex(0);

      // Recupera respostas salvas do localStorage se existirem
      const savedAnswers = localStorage.getItem(`vera_answers_${simuladoId}`);
      if (savedAnswers) {
        try {
          setRespostas(JSON.parse(savedAnswers));
        } catch {
          setRespostas({});
        }
      } else {
        setRespostas({});
      }

      // Recupera tempo salvo
      const savedTimer = localStorage.getItem(`vera_timer_${simuladoId}`);
      if (savedTimer && !isNaN(Number(savedTimer))) {
        setSecondsRemaining(Math.max(60, Number(savedTimer)));
      } else {
        setSecondsRemaining(9000);
      }

      setIsTimerRunning(true);
      setViewMode('exam');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Erro ao abrir simulado:', err);
    } finally {
      setIsLoadingExam(false);
    }
  };

  // Cria um novo simulado
  const handleGerarNovoSimulado = async () => {
    setIsGenerating(true);
    try {
      const title = novoTitulo.trim() || `Simulado ENEM Matemática #${simulados.length + 1}`;
      const novo = await simuladoService.gerarSimulado(title, user?.id);
      setShowNewModal(false);
      setNovoTitulo('');
      // Inicia imediatamente o novo simulado
      setSimulado(novo);
      setRespostas({});
      setRevisao(new Set());
      setCurrentIndex(0);
      setSecondsRemaining(9000);
      setIsTimerRunning(true);
      setViewMode('exam');
      // Atualiza lista em segundo plano
      carregarMeusSimulados();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Erro ao gerar novo simulado:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  // Salva o progresso e retorna ao Hub de Simulados
  const handleSalvarEVoltar = () => {
    if (simulado) {
      try {
        localStorage.setItem(`vera_answers_${simulado.id}`, JSON.stringify(respostas));
        localStorage.setItem(`vera_timer_${simulado.id}`, String(secondsRemaining));
      } catch (err) {
        console.warn('Não foi possível persistir no localStorage:', err);
      }
    }
    setViewMode('hub');
    carregarMeusSimulados();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Abre o resultado de um simulado arquivado
  const handleVerResultado = async (simuladoId: string, tentativaId?: string | null) => {
    setIsLoadingResult(true);
    try {
      const res = await simuladoService.obterResultadoSimulado(simuladoId, tentativaId || undefined);
      setResultado(res);
      setViewMode('result');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Erro ao recuperar resultado do simulado:', err);
    } finally {
      setIsLoadingResult(false);
    }
  };

  const handleSelectAlternativa = (letra: AlternativaLetra) => {
    if (!currentQuestion || !simulado) return;
    const novasRespostas = {
      ...respostas,
      [currentQuestion.questao_id]: letra,
    };
    setRespostas(novasRespostas);

    // Persiste no storage para não perder em caso de refresh
    try {
      localStorage.setItem(`vera_answers_${simulado.id}`, JSON.stringify(novasRespostas));
    } catch {
      // Ignora falha de cota
    }
  };

  const toggleMarcarRevisao = () => {
    if (!currentQuestion) return;
    setRevisao((prev) => {
      const next = new Set(prev);
      if (next.has(currentQuestion.questao_id)) {
        next.delete(currentQuestion.questao_id);
      } else {
        next.add(currentQuestion.questao_id);
      }
      return next;
    });
  };

  const handleSubmitSimulado = async () => {
    if (!simulado) return;
    setIsSubmitting(true);

    const payload: Array<{ questao_id: string; alternativa_marcada: AlternativaLetra | 'X' }> =
      simulado.itens.map((item) => ({
        questao_id: item.questao_id,
        alternativa_marcada: (respostas[item.questao_id] || 'X') as AlternativaLetra | 'X',
      }));

    try {
      const res = await simuladoService.submeterSimulado(simulado.id, payload, simulado.itens, user?.id);
      setResultado(res);
      setShowConfirmModal(false);
      setViewMode('result');

      // Limpa do storage o rascunho do simulado submetido
      try {
        localStorage.removeItem(`vera_answers_${simulado.id}`);
        localStorage.removeItem(`vera_timer_${simulado.id}`);
      } catch {
        // ignora
      }

      // Atualiza lista em segundo plano para refletir no hub
      carregarMeusSimulados();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error('Erro ao submeter simulado:', err);
    } finally {
      setIsSubmitting(false);
    }
  };
  handleSubmitRef.current = handleSubmitSimulado;

  // Itens calculados para o simulado ativo
  const currentQuestion = simulado?.itens[currentIndex];
  const totalQuestions = simulado?.itens.length || 45;
  const answeredCount = Object.keys(respostas).length;
  const progressPercent = Math.round((answeredCount / totalQuestions) * 100);

  // Listas filtradas para o Hub
  const simuladosPendentes = simulados.filter((s) => s.status === 'pendente');
  const simuladosArquivados = simulados.filter((s) => s.status === 'finalizado');

  // Conta respostas salvas em rascunho de um simulado pendente no localStorage
  const getQtdRespondidasLocal = (simuladoId: string) => {
    try {
      const item = localStorage.getItem(`vera_answers_${simuladoId}`);
      if (item) {
        const obj = JSON.parse(item);
        return Object.keys(obj).length;
      }
    } catch {
      return 0;
    }
    return 0;
  };

  // Bloqueio de acesso para estudantes não autenticados
  if (!isAuthenticated) {
    return (
      <div className="container" style={{ padding: '4rem 1.25rem', textAlign: 'center' }}>
        <div
          className="card"
          style={{
            maxWidth: '560px',
            margin: '0 auto',
            padding: '3rem 2rem',
            borderTop: '6px solid var(--ocean-600)',
            boxShadow: 'var(--shadow-ocean)',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: 'var(--ocean-100)',
              color: 'var(--ocean-700)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1.25rem',
            }}
          >
            <Lock size={32} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.75rem' }}>
            Acesso Restrito aos Simulados
          </h1>
          <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '2rem' }}>
            Para gerar simulados de 45 questões, salvar seu progresso e consultar o histórico de simulados arquivados, é necessário estar conectado.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <button
              onClick={() => onNavigate('register')}
              className="btn btn-primary btn-lg"
              style={{ width: '100%', fontWeight: 700 }}
            >
              Criar Conta Gratuita
            </button>
            <button
              onClick={() => onNavigate('login')}
              className="btn btn-outline"
              style={{ width: '100%' }}
            >
              Já possui conta? Fazer Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // MODO 1: HUB DE SIMULADOS (LISTAGEM PENDENTES E ARQUIVADOS)
  // =========================================================================
  if (viewMode === 'hub') {
    return (
      <div className="container" style={{ padding: '2.5rem 1.25rem 4rem' }}>
        {/* Cabeçalho Principal do Hub */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1.25rem',
            marginBottom: '2rem',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
              <span className="badge badge-ocean">Ambiente do Estudante</span>
              <span className="badge badge-dark">Matemática ENEM</span>
            </div>
            <h1 style={{ fontSize: '2.1rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
              Meus Simulados
            </h1>
            <p style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>
              Acompanhe simulados em andamento e consulte o histórico de cadernos arquivados com correção detalhada.
            </p>
          </div>

          <button
            onClick={() => setShowNewModal(true)}
            className="btn btn-primary btn-lg"
            style={{ fontWeight: 700, gap: '0.5rem' }}
          >
            <Plus size={20} />
            Gerar Novo Simulado
          </button>
        </div>

        {/* Métricas Rápidas */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1.25rem',
            marginBottom: '2.5rem',
          }}
        >
          <div
            className="card"
            style={{
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              borderLeft: '4px solid var(--color-warning)',
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                backgroundColor: 'var(--color-warning-bg)',
                color: 'var(--color-warning)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Clock size={22} />
            </div>
            <div>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {simuladosPendentes.length}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                Em Andamento / Pendentes
              </div>
            </div>
          </div>

          <div
            className="card"
            style={{
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              borderLeft: '4px solid var(--color-success)',
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                backgroundColor: 'var(--color-success-bg)',
                color: 'var(--color-success)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <CheckCircle size={22} />
            </div>
            <div>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {simuladosArquivados.length}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                Finalizados
              </div>
            </div>
          </div>

          <div
            className="card"
            style={{
              padding: '1.25rem 1.5rem',
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              borderLeft: '4px solid var(--ocean-600)',
            }}
          >
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                backgroundColor: 'var(--ocean-100)',
                color: 'var(--ocean-700)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Layers size={22} />
            </div>
            <div>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)', lineHeight: 1.1 }}>
                {simulados.length}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                Total de Cadernos Gerados
              </div>
            </div>
          </div>
        </div>

        {/* Barra de Abas: Pendentes vs Arquivados */}
        <div
          style={{
            display: 'flex',
            gap: '0.5rem',
            borderBottom: '2px solid var(--border-light)',
            marginBottom: '1.75rem',
          }}
        >
          <button
            onClick={() => setActiveTab('pendentes')}
            style={{
              padding: '0.85rem 1.35rem',
              fontWeight: 700,
              fontSize: '0.975rem',
              border: 'none',
              background: 'transparent',
              borderBottom: activeTab === 'pendentes' ? '3px solid var(--ocean-600)' : '3px solid transparent',
              color: activeTab === 'pendentes' ? 'var(--ocean-700)' : 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              transition: 'all 0.15s ease',
              marginBottom: '-2px',
            }}
          >
            <Clock size={18} />
            <span>Em Andamento ({simuladosPendentes.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('arquivados')}
            style={{
              padding: '0.85rem 1.35rem',
              fontWeight: 700,
              fontSize: '0.975rem',
              border: 'none',
              background: 'transparent',
              borderBottom: activeTab === 'arquivados' ? '3px solid var(--ocean-600)' : '3px solid transparent',
              color: activeTab === 'arquivados' ? 'var(--ocean-700)' : 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              transition: 'all 0.15s ease',
              marginBottom: '-2px',
            }}
          >
            <FileSpreadsheet size={18} />
            <span>Finalizados ({simuladosArquivados.length})</span>
          </button>
        </div>

        {/* Estado de Carregamento */}
        {isLoadingList && (
          <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                border: '3px solid var(--ocean-100)',
                borderTopColor: 'var(--ocean-600)',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
                margin: '0 auto 1rem',
              }}
            />
            <p style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Carregando seus simulados...</p>
            <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {/* ABA: SIMULADOS EM ANDAMENTO (PENDENTES) */}
        {!isLoadingList && activeTab === 'pendentes' && (
          <div>
            {simuladosPendentes.length === 0 ? (
              <div
                className="card"
                style={{
                  textAlign: 'center',
                  padding: '4rem 2rem',
                  border: '2px dashed var(--border-medium)',
                  backgroundColor: 'var(--white)',
                }}
              >
                <div
                  style={{
                    width: '60px',
                    height: '60px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--ocean-50)',
                    color: 'var(--ocean-600)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '1rem',
                  }}
                >
                  <Clock size={30} />
                </div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.5rem' }}>
                  Nenhum simulado em andamento
                </h3>
                <p style={{ color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto 1.5rem' }}>
                  Você não possui simulados pendentes. Gere um novo caderno de 45 questões no padrão ENEM para iniciar seus treinos.
                </p>
                <button
                  onClick={() => setShowNewModal(true)}
                  className="btn btn-primary"
                  style={{ fontWeight: 700 }}
                >
                  <Plus size={18} />
                  Gerar Primeiro Simulado
                </button>
              </div>
            ) : (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                  gap: '1.5rem',
                }}
              >
                {simuladosPendentes.map((sim) => {
                  const qtdRespondidas = getQtdRespondidasLocal(sim.id);
                  return (
                    <div
                      key={sim.id}
                      className="card"
                      style={{
                        padding: '1.5rem',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        borderTop: '4px solid var(--color-warning)',
                        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                          <span
                            style={{
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              padding: '0.2rem 0.6rem',
                              borderRadius: 'var(--radius-full)',
                              backgroundColor: 'var(--color-warning-bg)',
                              color: 'var(--color-warning)',
                            }}
                          >
                            Em Andamento
                          </span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                            {sim.total_itens} Itens
                          </span>
                        </div>

                        <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.4rem' }}>
                          {sim.titulo}
                        </h3>

                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.25rem', lineHeight: 1.4 }}>
                          {sim.descricao || 'Caderno de 45 questões com amostragem estratificada pela Matriz do ENEM.'}
                        </p>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                          <Calendar size={14} />
                          <span>Criado em: {formatDate(sim.created_at)}</span>
                        </div>

                        {/* Progresso salvo em rascunho */}
                        <div style={{ marginBottom: '1.5rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                            <span>Progresso</span>
                            <span>{qtdRespondidas} de {sim.total_itens} respondidas</span>
                          </div>
                          <div
                            style={{
                              width: '100%',
                              height: '6px',
                              backgroundColor: 'var(--ocean-100)',
                              borderRadius: '3px',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                width: `${Math.round((qtdRespondidas / sim.total_itens) * 100)}%`,
                                height: '100%',
                                backgroundColor: 'var(--color-warning)',
                                transition: 'width 0.3s ease',
                              }}
                            />
                          </div>
                        </div>
                      </div>

                      <button
                        onClick={() => handleIniciarSimulado(sim.id)}
                        disabled={isLoadingExam}
                        className="btn btn-primary"
                        style={{ width: '100%', fontWeight: 700, gap: '0.5rem' }}
                      >
                        <Play size={18} />
                        {qtdRespondidas > 0 ? 'Continuar Simulado' : 'Iniciar Simulado'}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ABA: SIMULADOS ARQUIVADOS (FINALIZADOS) */}
        {!isLoadingList && activeTab === 'arquivados' && (
          <div>
            {simuladosArquivados.length === 0 ? (
              <div
                className="card"
                style={{
                  textAlign: 'center',
                  padding: '4rem 2rem',
                  border: '2px dashed var(--border-medium)',
                  backgroundColor: 'var(--white)',
                }}
              >
                <div
                  style={{
                    width: '60px',
                    height: '60px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--ocean-50)',
                    color: 'var(--ocean-600)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '1rem',
                  }}
                >
                  <FileSpreadsheet size={30} />
                </div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.5rem' }}>
                  Nenhum simulado arquivado ainda
                </h3>
                <p style={{ color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto' }}>
                  Quando você concluir e entregar um simulado, suas notas, percentuais de acertos e o gabarito oficial ficarão arquivados nesta seção.
                </p>
              </div>
            ) : (
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
                  gap: '1.5rem',
                }}
              >
                {simuladosArquivados.map((sim) => (
                  <div
                    key={sim.id}
                    className="card"
                    style={{
                      padding: '1.5rem',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      borderTop: '4px solid var(--color-success)',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            fontWeight: 700,
                            padding: '0.2rem 0.6rem',
                            borderRadius: 'var(--radius-full)',
                            backgroundColor: 'var(--color-success-bg)',
                            color: 'var(--color-success)',
                          }}
                        >
                          Concluído & Arquivado
                        </span>
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {sim.total_itens} Itens
                        </span>
                      </div>

                      <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.5rem' }}>
                        {sim.titulo}
                      </h3>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1.25rem' }}>
                        <Calendar size={14} />
                        <span>Entregue em: {formatDate(sim.completed_at || sim.created_at)}</span>
                      </div>

                      {/* Box de Desempenho Arquivado */}
                      <div
                        style={{
                          backgroundColor: 'var(--ocean-50)',
                          border: '1px solid var(--border-ocean)',
                          borderRadius: 'var(--radius-md)',
                          padding: '1rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-around',
                          marginBottom: '1.5rem',
                        }}
                      >
                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-900)' }}>
                            {sim.score_percentual !== null ? `${sim.score_percentual}%` : '--'}
                          </div>
                          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                            Aproveitamento
                          </div>
                        </div>

                        <div style={{ width: '1px', height: '36px', backgroundColor: 'var(--border-ocean)' }} />

                        <div style={{ textAlign: 'center' }}>
                          <div style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-900)' }}>
                            {sim.total_acertos !== null ? `${sim.total_acertos} / ${sim.total_itens}` : '--'}
                          </div>
                          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                            Total de Acertos
                          </div>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handleVerResultado(sim.id, sim.tentativa_id)}
                      disabled={isLoadingResult}
                      className="btn btn-outline"
                      style={{ width: '100%', fontWeight: 700, gap: '0.5rem' }}
                    >
                      <FileSpreadsheet size={18} />
                      Ver Gabarito & Desempenho
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modal de Criação de Novo Simulado */}
        {showNewModal && (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              backgroundColor: 'rgba(4, 28, 46, 0.6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 2000,
              padding: '1rem',
              backdropFilter: 'blur(3px)',
            }}
          >
            <div
              className="card"
              style={{
                width: '100%',
                maxWidth: '480px',
                padding: '2rem',
                border: '2px solid var(--border-ocean)',
              }}
            >
              <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.5rem' }}>
                Gerar Novo Simulado ENEM
              </h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: 1.5 }}>
                O sistema montará um caderno exclusivo com <strong>45 questões</strong> no formato oficial do ENEM, distribuídas entre históricas e inéditas geradas por IA.
              </p>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, color: 'var(--ocean-900)', marginBottom: '0.4rem' }}>
                  Título do Simulado (Opcional)
                </label>
                <input
                  type="text"
                  value={novoTitulo}
                  onChange={(e) => setNovoTitulo(e.target.value)}
                  placeholder={`Simulado ENEM Matemática #${simulados.length + 1}`}
                  style={{
                    width: '100%',
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1.5px solid var(--border-medium)',
                    fontSize: '0.95rem',
                    outline: 'none',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowNewModal(false)}
                  className="btn btn-outline"
                  disabled={isGenerating}
                >
                  Cancelar
                </button>
                <button
                  onClick={handleGerarNovoSimulado}
                  className="btn btn-primary"
                  disabled={isGenerating}
                  style={{ fontWeight: 700, gap: '0.5rem' }}
                >
                  {isGenerating ? 'Gerando Caderno...' : 'Gerar e Começar'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // =========================================================================
  // MODO 2: TELA DE RESULTADOS E GABARITO (CONFERÊNCIA DE ARQUIVADOS)
  // =========================================================================
  if (viewMode === 'result' && resultado) {
    return (
      <div className="container" style={{ padding: '2.5rem 1.25rem 4rem' }}>
        {/* Botão de Retorno ao Hub */}
        <div style={{ marginBottom: '1.5rem' }}>
          <button
            onClick={() => {
              setViewMode('hub');
              carregarMeusSimulados();
            }}
            className="btn btn-outline btn-sm"
            style={{ gap: '0.4rem', fontWeight: 700 }}
          >
            <ArrowLeft size={16} />
            Voltar aos Meus Simulados
          </button>
        </div>

        {/* Card de Resumo do Resultado */}
        <div
          className="card"
          style={{
            borderTop: '6px solid var(--ocean-600)',
            marginBottom: '2.5rem',
            textAlign: 'center',
            padding: '2.5rem 1.5rem',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '50%',
              backgroundColor: 'var(--ocean-100)',
              color: 'var(--ocean-700)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
            }}
          >
            <Award size={36} />
          </div>

          <h1 style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.5rem' }}>
            Relatório de Desempenho
          </h1>
          <p style={{ fontSize: '1.05rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto 1.75rem' }}>
            Aproveitamento nas <strong>{resultado.total_itens} questões</strong> com detalhamento por habilidade oficial da Matriz de Referência do ENEM.
          </p>

          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              gap: '2rem',
              flexWrap: 'wrap',
              marginBottom: '2rem',
            }}
          >
            <div
              style={{
                backgroundColor: 'var(--ocean-50)',
                border: '1px solid var(--border-ocean)',
                padding: '1.25rem 2rem',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--ocean-800)' }}>
                {resultado.total_acertos} / {resultado.total_itens}
              </div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Total de Acertos
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--ocean-50)',
                border: '1px solid var(--border-ocean)',
                padding: '1.25rem 2rem',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--ocean-800)' }}>
                {resultado.score_percentual}%
              </div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                Taxa de Acerto Geral
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => {
                setViewMode('hub');
                carregarMeusSimulados();
              }}
              className="btn btn-outline"
            >
              <RotateCcw size={18} />
              Voltar aos Simulados
            </button>
            <button onClick={() => onNavigate('chat')} className="btn btn-primary">
              <BotMessageSquare size={18} />
              Revisar Questões com a Tutora VERA
            </button>
          </div>
        </div>

        {/* Grade de Conferência Item a Item */}
        <div className="card">
          <div style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '1rem' }}>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
              Gabarito Oficial e Conferência dos Itens
            </h2>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
              Verifique os acertos e erros de cada item para focar seus estudos nas habilidades necessárias.
            </p>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
              gap: '0.75rem',
            }}
          >
            {resultado.itens.map((item) => (
              <div
                key={item.ordem}
                style={{
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-md)',
                  border: `1.5px solid ${item.is_correto ? 'var(--color-success)' : 'var(--color-danger)'}`,
                  backgroundColor: item.is_correto ? 'var(--color-success-bg)' : 'var(--color-danger-bg)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.25rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ fontSize: '0.95rem', color: 'var(--text-primary)' }}>Q{item.ordem}</strong>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      color: item.is_correto ? 'var(--color-success)' : 'var(--color-danger)',
                    }}
                  >
                    {item.is_correto ? 'ACERTOU' : 'ERROU'}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Sua: <strong>{item.alternativa_selecionada || 'Em branco'}</strong>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Oficial: <strong>{item.gabarito_oficial}</strong>
                </div>
                <div
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: 'var(--ocean-900)',
                    marginTop: '0.25rem',
                  }}
                >
                  Hab: {item.habilidade_codigo}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // MODO 3: TELA DE EXECUÇÃO DO SIMULADO (MODO PROVA)
  // =========================================================================
  return (
    <div className="container" style={{ padding: '1.5rem 1.25rem 4rem' }}>
      {/* Barra Superior Fixa: Voltar, Título, Cronômetro e Botão de Entrega */}
      <div
        className="card"
        style={{
          marginBottom: '1.75rem',
          padding: '1.25rem 1.5rem',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          backgroundColor: 'var(--white)',
          borderLeft: '5px solid var(--ocean-600)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            onClick={handleSalvarEVoltar}
            className="btn btn-outline btn-sm"
            title="Salva as respostas e volta para Meus Simulados"
            style={{ gap: '0.35rem', fontWeight: 700 }}
          >
            <Save size={16} />
            Salvar e Voltar
          </button>

          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ocean-950)', margin: 0 }}>
              {simulado?.titulo || 'Simulado Geral de Matemática'}
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginTop: '0.2rem' }}>
              <span className="badge badge-ocean">Caderno Padrão ENEM</span>
              <span style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Respondidas: {answeredCount} de {totalQuestions} ({progressPercent}%)
              </span>
            </div>
          </div>
        </div>

        {/* Cronômetro e Botão de Entrega */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: 'var(--ocean-50)',
              border: '1.5px solid var(--border-ocean)',
              padding: '0.45rem 0.95rem',
              borderRadius: 'var(--radius-md)',
              color: secondsRemaining < 900 ? 'var(--color-danger)' : 'var(--ocean-900)',
              fontWeight: 800,
              fontSize: '1.15rem',
              fontFamily: 'monospace',
            }}
          >
            <Clock size={18} />
            <span>{formatTime(secondsRemaining)}</span>
            <button
              onClick={() => setIsTimerRunning(!isTimerRunning)}
              className="btn btn-ghost btn-sm"
              style={{ padding: '0.2rem', marginLeft: '0.25rem' }}
              title={isTimerRunning ? 'Pausar Cronômetro' : 'Retomar Cronômetro'}
            >
              {isTimerRunning ? <Pause size={16} /> : <Play size={16} />}
            </button>
          </div>

          <button
            onClick={() => setShowConfirmModal(true)}
            className="btn btn-primary"
            style={{ fontWeight: 700 }}
          >
            <Send size={18} />
            Entregar Simulado
          </button>
        </div>
      </div>

      {/* Grid Principal: Questão Central + Navegador Lateral */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 340px',
          gap: '1.75rem',
          alignItems: 'start',
        }}
        className="simulado-layout"
      >
        {/* Painel Central: Enunciado e Alternativas da Questão Atual */}
        {currentQuestion && (
          <div className="card" style={{ padding: '2rem' }}>
            {/* Header da Questão */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: '1.5px solid var(--border-light)',
                paddingBottom: '1rem',
                marginBottom: '1.5rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span
                  style={{
                    fontSize: '1.25rem',
                    fontWeight: 800,
                    color: 'var(--ocean-900)',
                  }}
                >
                  Questão {currentQuestion.ordem}
                </span>
                <span className="badge badge-ocean">
                  Habilidade {currentQuestion.habilidade_codigo}
                </span>
                <span className="badge badge-dark">
                  {currentQuestion.origem_questao === 'enem'
                    ? `ENEM ${currentQuestion.ano || 'Oficial'}`
                    : 'Inédita VERA'}
                </span>
              </div>

              <button
                onClick={toggleMarcarRevisao}
                className="btn btn-sm"
                style={{
                  backgroundColor: revisao.has(currentQuestion.questao_id)
                    ? 'var(--color-warning-bg)'
                    : 'var(--surface-subtle)',
                  color: revisao.has(currentQuestion.questao_id)
                    ? 'var(--color-warning)'
                    : 'var(--text-muted)',
                  borderColor: revisao.has(currentQuestion.questao_id)
                    ? 'var(--color-warning)'
                    : 'var(--border-subtle)',
                }}
              >
                <Flag size={16} />
                {revisao.has(currentQuestion.questao_id) ? 'Marcada para Revisão' : 'Revisar Depois'}
              </button>
            </div>

            {/* Enunciado Formatado com KaTeX */}
            <div style={{ marginBottom: '2rem', fontSize: '1.05rem' }}>
              <MathText content={currentQuestion.enunciado} />
            </div>

            {/* Alternativas A, B, C, D, E */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '2.5rem' }}>
              {(['A', 'B', 'C', 'D', 'E'] as AlternativaLetra[]).map((letra) => {
                const isSelected = respostas[currentQuestion.questao_id] === letra;
                const textoAlternativa = currentQuestion.alternativas[letra];

                return (
                  <button
                    key={letra}
                    onClick={() => handleSelectAlternativa(letra)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '1rem',
                      padding: '1rem 1.25rem',
                      borderRadius: 'var(--radius-md)',
                      border: `2px solid ${isSelected ? 'var(--ocean-600)' : 'var(--border-medium)'}`,
                      backgroundColor: isSelected ? 'var(--ocean-50)' : 'var(--white)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease',
                      width: '100%',
                    }}
                  >
                    <div
                      style={{
                        width: '34px',
                        height: '34px',
                        borderRadius: '50%',
                        backgroundColor: isSelected ? 'var(--ocean-600)' : 'var(--ocean-100)',
                        color: isSelected ? 'var(--white)' : 'var(--ocean-900)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: '1rem',
                        flexShrink: 0,
                      }}
                    >
                      {letra}
                    </div>
                    <div style={{ flex: 1, fontSize: '0.975rem', color: 'var(--text-primary)' }}>
                      <MathText content={textoAlternativa} />
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Rodapé de Navegação da Questão */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderTop: '1.5px solid var(--border-light)',
                paddingTop: '1.5rem',
              }}
            >
              <button
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentIndex === 0}
                className="btn btn-outline"
              >
                <ChevronLeft size={18} />
                Anterior
              </button>

              <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                Item {currentIndex + 1} de {totalQuestions}
              </span>

              {currentIndex < totalQuestions - 1 ? (
                <button
                  onClick={() => setCurrentIndex((prev) => Math.min(totalQuestions - 1, prev + 1))}
                  className="btn btn-primary"
                >
                  Próxima
                  <ChevronRight size={18} />
                </button>
              ) : (
                <button
                  onClick={() => setShowConfirmModal(true)}
                  className="btn btn-primary"
                  style={{ fontWeight: 700 }}
                >
                  Concluir e Entregar
                  <CheckCircle2 size={18} />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Navegador Lateral: Grade das 45 Questões */}
        <div className="card" style={{ padding: '1.5rem' }}>
          <div style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
              Grade do Simulado
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Navegue diretamente pelos 45 itens
            </p>
          </div>

          {/* Legenda de Cores */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.4rem',
              fontSize: '0.8rem',
              fontWeight: 600,
              padding: '0.75rem',
              backgroundColor: 'var(--ocean-50)',
              borderRadius: 'var(--radius-md)',
              marginBottom: '1.25rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div
                style={{
                  width: '14px',
                  height: '14px',
                  borderRadius: '3px',
                  backgroundColor: 'var(--ocean-600)',
                }}
              />
              <span style={{ color: 'var(--text-secondary)' }}>Respondida</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div
                style={{
                  width: '14px',
                  height: '14px',
                  borderRadius: '3px',
                  backgroundColor: 'var(--color-warning)',
                }}
              />
              <span style={{ color: 'var(--text-secondary)' }}>Marcada para Revisão</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div
                style={{
                  width: '14px',
                  height: '14px',
                  borderRadius: '3px',
                  backgroundColor: 'var(--white)',
                  border: '1.5px solid var(--border-medium)',
                }}
              />
              <span style={{ color: 'var(--text-secondary)' }}>Pendente (em branco)</span>
            </div>
          </div>

          {/* Grid de 45 Botões Numerados */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, 1fr)',
              gap: '0.5rem',
            }}
          >
            {simulado?.itens.map((item, idx) => {
              const isAnswered = !!respostas[item.questao_id];
              const isFlagged = revisao.has(item.questao_id);
              const isCurrent = idx === currentIndex;

              let bgColor = 'var(--white)';
              let textColor = 'var(--text-primary)';
              let borderColor = 'var(--border-medium)';

              if (isFlagged) {
                bgColor = 'var(--color-warning)';
                textColor = 'var(--white)';
                borderColor = 'var(--color-warning)';
              } else if (isAnswered) {
                bgColor = 'var(--ocean-600)';
                textColor = 'var(--white)';
                borderColor = 'var(--ocean-600)';
              }

              return (
                <button
                  key={item.simulado_item_id}
                  onClick={() => setCurrentIndex(idx)}
                  style={{
                    aspectRatio: '1',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    backgroundColor: bgColor,
                    color: textColor,
                    border: isCurrent ? '2.5px solid var(--ocean-950)' : `1.5px solid ${borderColor}`,
                    boxShadow: isCurrent ? '0 0 0 2px var(--ocean-400)' : 'none',
                    cursor: 'pointer',
                    transition: 'all 0.1s ease',
                  }}
                  title={`Questão ${item.ordem} - Hab ${item.habilidade_codigo}`}
                >
                  {item.ordem}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Modal de Confirmação de Entrega */}
      {showConfirmModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(4, 28, 46, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2000,
            padding: '1rem',
            backdropFilter: 'blur(3px)',
          }}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '460px',
              boxShadow: 'var(--shadow-lg)',
              border: '2px solid var(--border-ocean)',
              padding: '2rem',
            }}
          >
            <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
              <div
                style={{
                  width: '52px',
                  height: '52px',
                  borderRadius: '50%',
                  backgroundColor: answeredCount === totalQuestions ? 'var(--ocean-100)' : 'var(--color-warning-bg)',
                  color: answeredCount === totalQuestions ? 'var(--ocean-700)' : 'var(--color-warning)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1rem',
                }}
              >
                {answeredCount === totalQuestions ? <CheckCircle2 size={30} /> : <AlertTriangle size={30} />}
              </div>
              <h2 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
                Finalizar e Entregar Simulado?
              </h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                Você respondeu <strong>{answeredCount}</strong> de <strong>{totalQuestions}</strong> questões.
                {answeredCount < totalQuestions && (
                  <span style={{ display: 'block', color: 'var(--color-warning)', marginTop: '0.35rem', fontWeight: 600 }}>
                    Atenção: ainda restam {totalQuestions - answeredCount} questões sem resposta.
                  </span>
                )}
              </p>
              <p style={{ fontSize: '0.825rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                Após a entrega, o caderno será <strong>arquivado</strong> com a sua nota e o gabarito oficial será disponibilizado.
              </p>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <button
                onClick={() => setShowConfirmModal(false)}
                className="btn btn-outline"
                disabled={isSubmitting}
                style={{ flex: 1 }}
              >
                Continuar Prova
              </button>
              <button
                onClick={handleSubmitSimulado}
                className="btn btn-primary"
                disabled={isSubmitting}
                style={{ flex: 1, fontWeight: 700 }}
              >
                {isSubmitting ? 'Processando...' : 'Confirmar Entrega'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Estilos responsivos inline para o layout do Simulado */}
      <style>{`
        @media (max-width: 900px) {
          .simulado-layout {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
};
export default SimuladoPage;
