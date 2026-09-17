import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { simuladoService } from '../services/simuladoService';
import type { Simulado, AlternativaLetra, SimuladoResultado } from '../types/simulado';
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
} from 'lucide-react';

interface SimuladoPageProps {
  onNavigate: (page: string) => void;
}

export const SimuladoPage: React.FC<SimuladoPageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();
  const [simulado, setSimulado] = useState<Simulado | null>(null);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  // Respostas salvas: questao_id -> alternativa marcada
  const [respostas, setRespostas] = useState<Record<string, AlternativaLetra>>({});
  // Marcadas para revisão: Set de questao_id
  const [revisao, setRevisao] = useState<Set<string>>(new Set());
  // Cronômetro (em segundos): 2 horas e 30 minutos padrão ENEM = 9000 segundos
  const [secondsRemaining, setSecondsRemaining] = useState<number>(9000);
  const [isTimerRunning, setIsTimerRunning] = useState<boolean>(true);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [resultado, setResultado] = useState<SimuladoResultado | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Inicialização do caderno de 45 questões vinculado ao estudante
  useEffect(() => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }

    async function carregarSimulado() {
      setIsLoading(true);
      try {
        const data = await simuladoService.gerarSimulado(user?.id);
        setSimulado(data);
      } catch (err) {
        console.error('Erro ao inicializar simulado:', err);
      } finally {
        setIsLoading(false);
      }
    }

    carregarSimulado();
  }, [isAuthenticated, user?.id]);

  // Temporizador do Simulado
  useEffect(() => {
    if (!isTimerRunning || resultado || !simulado) return;

    const timer = setInterval(() => {
      setSecondsRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleAutoSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [isTimerRunning, resultado, simulado]);

  const handleAutoSubmit = () => {
    handleSubmitSimulado();
  };

  const formatTime = (secs: number) => {
    const hours = Math.floor(secs / 3600);
    const minutes = Math.floor((secs % 3600) / 60);
    const seconds = secs % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes
      .toString()
      .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const currentQuestion = simulado?.itens[currentIndex];
  const totalQuestions = simulado?.itens.length || 45;
  const answeredCount = Object.keys(respostas).length;
  const progressPercent = Math.round((answeredCount / totalQuestions) * 100);

  const handleSelectAlternativa = (letra: AlternativaLetra) => {
    if (!currentQuestion) return;
    setRespostas((prev) => ({
      ...prev,
      [currentQuestion.questao_id]: letra,
    }));
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
    } catch (err) {
      console.error('Erro ao submeter simulado:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRestart = async () => {
    setResultado(null);
    setRespostas({});
    setRevisao(new Set());
    setCurrentIndex(0);
    setSecondsRemaining(9000);
    setIsTimerRunning(true);
    setIsLoading(true);
    try {
      const data = await simuladoService.gerarSimulado(user?.id);
      setSimulado(data);
    } finally {
      setIsLoading(false);
    }
  };

  // Bloqueio de acesso para estudantes não cadastrados / não autenticados
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
            Acesso Restrito ao Simulado
          </h1>
          <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '2rem' }}>
            Para realizar o <strong>Simulado Geral com 45 questões</strong> e salvar seu histórico de proficiência nas 30 habilidades da Matriz do ENEM, é necessário estar cadastrado e conectado à plataforma.
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

  if (isLoading) {
    return (
      <div
        className="container"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          gap: '1.25rem',
        }}
      >
        <div
          style={{
            width: '48px',
            height: '48px',
            border: '4px solid var(--ocean-100)',
            borderTopColor: 'var(--ocean-600)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }}
        />
        <p style={{ fontWeight: 700, color: 'var(--ocean-900)' }}>
          Montando caderno de 45 questões estratificadas pela Matriz do ENEM...
        </p>
        <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  // --- TELA DE RESULTADOS DO SIMULADO ---
  if (resultado) {
    return (
      <div className="container" style={{ padding: '2.5rem 1.25rem 4rem' }}>
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
            Simulado Geral Concluído!
          </h1>
          <p style={{ fontSize: '1.05rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto 1.75rem' }}>
            Confira seu aproveitamento nas <strong>45 questões</strong> e veja o detalhamento por habilidade oficial da Matriz de Referência do ENEM.
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
            <button onClick={handleRestart} className="btn btn-outline">
              <RotateCcw size={18} />
              Realizar Novo Simulado
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
              Gabarito e Conferência dos 45 Itens
            </h2>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
              Verifique quais itens você acertou e revise as habilidades com maior incidência de dúvidas
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

  // --- TELA DE EXECUÇÃO DO SIMULADO ---
  return (
    <div className="container" style={{ padding: '1.5rem 1.25rem 4rem' }}>
      {/* Barra Superior Fixa do Simulado: Título, Cronômetro e Progresso */}
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
        <div>
          <h1 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
            Simulado Geral de Matemática
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '0.25rem' }}>
            <span className="badge badge-ocean">Caderno Padrão ENEM</span>
            {user && <span className="badge badge-dark">Estudante: {user.nome}</span>}
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Respondidas: {answeredCount} de {totalQuestions} ({progressPercent}%)
            </span>
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

      {/* Grid Principal: Questão Central + Navegador Lateral de 45 Questões */}
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

            {/* Enunciado Formatado com Suporte a Fórmulas Matemáticas */}
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
                Finalizar Simulado?
              </h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                Você respondeu <strong>{answeredCount}</strong> de <strong>{totalQuestions}</strong> questões.
                {answeredCount < totalQuestions && (
                  <span style={{ display: 'block', color: 'var(--color-warning)', marginTop: '0.35rem', fontWeight: 600 }}>
                    Atenção: ainda restam {totalQuestions - answeredCount} questões sem resposta.
                  </span>
                )}
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
