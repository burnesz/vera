import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { chatService } from '../services/chatService';
import type { ChatMessage, ChatSessionSummary } from '../types/chat';
import { MathText } from '../components/MathText';
import {
  Send,
  Sparkles,
  BotMessageSquare,
  User as UserIcon,
  Lightbulb,
  Lock,
  Plus,
  Trash2,
  Pencil,
  MessageSquare,
  BookOpen,
  Brain,
  Check,
  X,
  History,
} from 'lucide-react';

interface ChatPageProps {
  onNavigate: (page: string) => void;
}

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome-default',
  sender: 'vera',
  text: `Olá! Sou a **VERA**, sua Tutora Especialista em Matemática para o ENEM. 

Estou aqui para tirar dúvidas teóricas, detalhar resoluções passo a passo (com fórmulas matemáticas) e ajudá-lo a compreender as 30 habilidades da Matriz de Referência do ENEM.

Sobre qual conteúdo ou questão de Matemática você gostaria de conversar hoje?`,
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
};

export const ChatPage: React.FC<ChatPageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();

  // Estados da Sessão e Conversas
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>(() => 'sess_' + Date.now());
  const [currentTitle, setCurrentTitle] = useState<string>('Nova Conversa');
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);

  // Estados de Interface e Controle
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Estados para Edição de Título
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editedTitle, setEditedTitle] = useState('');

  // Estado para Modal de Exclusão
  const [sessionToDelete, setSessionToDelete] = useState<ChatSessionSummary | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll para o final da conversa
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Carrega a lista de sessões do usuário ao entrar na página
  const loadSessionsList = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const list = await chatService.listSessions();
      setSessions(list);
    } catch (err) {
      console.warn('Erro ao carregar lista de conversas:', err);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadSessionsList();
  }, [loadSessionsList]);

  // Seleciona uma conversa anterior para carregar o histórico
  const handleSelectSession = async (session: ChatSessionSummary) => {
    if (session.id === currentSessionId && messages.length > 1) return;

    setCurrentSessionId(session.id);
    setCurrentTitle(session.titulo);
    setIsLoadingHistory(true);

    try {
      const historyData = await chatService.getHistory(session.id);
      if (historyData.messages && historyData.messages.length > 0) {
        const mapped: ChatMessage[] = historyData.messages.map((m, index) => ({
          id: m.id || `msg-${session.id}-${index}`,
          sender: (m.role === 'user' || m.sender === 'user') ? 'user' : 'vera',
          text: m.content || m.text || '',
          timestamp: m.created_at
            ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : (typeof m.timestamp === 'number'
                ? new Date(m.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })),
          thought: m.thought,
          context_chunks: m.context_chunks,
        }));
        setMessages(mapped);
      } else {
        setMessages([WELCOME_MESSAGE]);
      }
    } catch (err) {
      console.error('Erro ao carregar histórico da sessão:', err);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Inicia uma nova conversa limpa
  const handleNewChat = () => {
    const newId = 'sess_' + Date.now();
    setCurrentSessionId(newId);
    setCurrentTitle('Nova Conversa');
    setMessages([
      {
        id: 'welcome-' + Date.now(),
        sender: 'vera',
        text: 'Nova conversa iniciada! Em qual conceito ou questão de Matemática posso te guiar agora?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    setInputMessage('');
  };

  // Envio de mensagem com persistência
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isTyping) return;

    const userMessage: ChatMessage = {
      id: 'msg-' + Date.now(),
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage('');
    setIsTyping(true);

    try {
      const response = await chatService.sendMessage({
        session_id: currentSessionId,
        message: text,
      });

      // Se o backend confirmou ou gerou o session_id, sincronizamos
      if (response.session_id && response.session_id !== currentSessionId) {
        setCurrentSessionId(response.session_id);
      }

      const veraMessage: ChatMessage = {
        id: 'msg-' + (Date.now() + 1),
        sender: 'vera',
        text: response.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        thought: response.thought,
        context_chunks: response.context_chunks,
        habilidade_codigo: response.habilidade_detectada,
      };

      setMessages((prev) => [...prev, veraMessage]);

      // Atualiza a lista de sessões no painel lateral
      await loadSessionsList();
    } catch (err: any) {
      console.error('Erro ao enviar mensagem:', err);
      const errorMessage: ChatMessage = {
        id: 'msg-err-' + Date.now(),
        sender: 'vera',
        text: err?.message
          ? `Desculpe, não consegui completar a resposta: ${err.message}`
          : 'Desculpe, ocorreu uma instabilidade temporária na comunicação. Por favor, tente novamente em instantes.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Inicia edição de título
  const handleStartRename = (session: ChatSessionSummary, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(session.id);
    setEditedTitle(session.titulo);
  };

  // Salva renomeação de título
  const handleSaveRename = async (sessionId: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!editedTitle.trim()) {
      setEditingSessionId(null);
      return;
    }

    const success = await chatService.renameSession(sessionId, editedTitle.trim());
    if (success) {
      if (sessionId === currentSessionId) {
        setCurrentTitle(editedTitle.trim());
      }
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, titulo: editedTitle.trim() } : s))
      );
    }
    setEditingSessionId(null);
  };

  // Confirmação de exclusão
  const handleConfirmDelete = async () => {
    if (!sessionToDelete) return;
    const deletedId = sessionToDelete.id;
    const success = await chatService.deleteSession(deletedId);

    if (success) {
      setSessions((prev) => prev.filter((s) => s.id !== deletedId));
      // Se apagou a conversa que estava aberta, inicia uma nova
      if (currentSessionId === deletedId) {
        handleNewChat();
      }
    }
    setSessionToDelete(null);
  };

  const quickQuestions = [
    'Como calcular o Teorema de Pitágoras no ENEM?',
    'Como resolver questões de aumento percentual sucessivo?',
    'Explique a fórmula do vértice da parábola (H21)',
    'Qual a diferença entre média aritmética e média ponderada?',
  ];

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
              color: 'var(--ocean-800)',
              margin: '0 auto 1.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Lock size={32} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)', marginBottom: '0.75rem' }}>
            Acesso Restrito à Tutora VERA
          </h1>
          <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '2rem' }}>
            Para conversar com a Tutora Inteligente e ter seu histórico de aprendizado registrado no banco de dados, você precisa estar cadastrado e conectado à plataforma.
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
  // Janela de Chat Full-Bleed com Sidebar de Sessões Persistidas
  // =========================================================================
  return (
    <div
      style={{
        display: 'flex',
        height: 'calc(100vh - var(--topbar-height))',
        width: '100%',
        backgroundColor: 'var(--surface-subtle)',
        overflow: 'hidden',
      }}
    >
      {/* -----------------------------------------------------------------
          Painel Lateral: Histórico de Sessões de Conversa
      ------------------------------------------------------------------ */}
      <aside
        style={{
          width: isSidebarOpen ? '300px' : '0px',
          transition: 'width 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
          backgroundColor: 'var(--white)',
          borderRight: isSidebarOpen ? '1px solid var(--border-light)' : 'none',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          overflow: 'hidden',
          zIndex: 10,
        }}
      >
        <div style={{ width: '300px', display: 'flex', flexDirection: 'column', height: '100%' }}>
          {/* Topo da Sidebar: Botão Nova Conversa */}
          <div
            style={{
              padding: '1rem',
              borderBottom: '1px solid var(--border-light)',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--ocean-950)', fontWeight: 700, fontSize: '0.95rem' }}>
                <History size={18} className="text-ocean-600" />
                <span>Minhas Conversas</span>
              </div>
              <span className="badge badge-ocean" style={{ fontSize: '0.7rem' }}>
                {sessions.length}
              </span>
            </div>

            <button
              onClick={handleNewChat}
              className="btn btn-primary"
              style={{
                width: '100%',
                justifyContent: 'center',
                gap: '0.5rem',
                fontWeight: 600,
                fontSize: '0.875rem',
                padding: '0.65rem 1rem',
              }}
            >
              <Plus size={16} />
              <span>Nova Conversa</span>
            </button>
          </div>

          {/* Lista de Conversas Salvas */}
          <div
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '0.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.25rem',
            }}
          >
            {sessions.length === 0 ? (
              <div
                style={{
                  padding: '2.5rem 1rem',
                  textAlign: 'center',
                  color: 'var(--text-muted)',
                  fontSize: '0.85rem',
                  lineHeight: '1.5',
                }}
              >
                <BotMessageSquare size={32} style={{ margin: '0 auto 0.75rem', opacity: 0.4 }} />
                <p>Nenhuma conversa salva ainda.</p>
                <p style={{ fontSize: '0.75rem' }}>Envie sua primeira dúvida para a Tutora VERA!</p>
              </div>
            ) : (
              sessions.map((sess) => {
                const isActive = sess.id === currentSessionId;
                const isEditing = editingSessionId === sess.id;

                return (
                  <div
                    key={sess.id}
                    onClick={() => !isEditing && handleSelectSession(sess)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.65rem 0.75rem',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: isActive ? 'var(--ocean-50)' : 'transparent',
                      border: isActive ? '1px solid var(--border-ocean)' : '1px solid transparent',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      position: 'relative',
                    }}
                    className={!isActive ? 'hover:bg-slate-50' : ''}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1, minWidth: 0 }}>
                      <MessageSquare
                        size={16}
                        style={{
                          flexShrink: 0,
                          color: isActive ? 'var(--ocean-600)' : 'var(--text-muted)',
                        }}
                      />

                      {isEditing ? (
                        <div
                          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flex: 1 }}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            value={editedTitle}
                            onChange={(e) => setEditedTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveRename(sess.id);
                              if (e.key === 'Escape') setEditingSessionId(null);
                            }}
                            autoFocus
                            style={{
                              fontSize: '0.825rem',
                              padding: '0.2rem 0.4rem',
                              borderRadius: '4px',
                              border: '1px solid var(--ocean-600)',
                              width: '100%',
                            }}
                          />
                          <button
                            onClick={() => handleSaveRename(sess.id)}
                            className="btn btn-sm"
                            style={{ padding: '0.2rem', color: 'var(--color-success)' }}
                            title="Salvar"
                          >
                            <Check size={14} />
                          </button>
                          <button
                            onClick={() => setEditingSessionId(null)}
                            className="btn btn-sm"
                            style={{ padding: '0.2rem', color: 'var(--text-muted)' }}
                            title="Cancelar"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      ) : (
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div
                            style={{
                              fontSize: '0.85rem',
                              fontWeight: isActive ? 600 : 500,
                              color: isActive ? 'var(--ocean-950)' : 'var(--text-secondary)',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                            title={sess.titulo}
                          >
                            {sess.titulo}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            {new Date(sess.updated_at).toLocaleDateString([], {
                              day: '2-digit',
                              month: '2-digit',
                            })}{' '}
                            • {sess.total_messages} msgs
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Botões de Ação na Sessão (Renomear / Excluir) */}
                    {!isEditing && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.2rem', marginLeft: '0.25rem' }}>
                        <button
                          onClick={(e) => handleStartRename(sess, e)}
                          className="btn btn-sm"
                          style={{
                            padding: '0.25rem',
                            color: 'var(--text-muted)',
                            opacity: isActive ? 0.8 : 0.4,
                          }}
                          title="Renomear conversa"
                        >
                          <Pencil size={13} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSessionToDelete(sess);
                          }}
                          className="btn btn-sm"
                          style={{
                            padding: '0.25rem',
                            color: 'var(--color-danger)',
                            opacity: isActive ? 0.8 : 0.4,
                          }}
                          title="Excluir conversa"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </aside>

      {/* -----------------------------------------------------------------
          Área Principal de Conversa
      ------------------------------------------------------------------ */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {/* Sub-header integrado do chat */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.75rem 1.75rem',
            backgroundColor: 'var(--white)',
            borderBottom: '1px solid var(--border-light)',
            flexShrink: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="btn btn-outline btn-sm"
              title={isSidebarOpen ? 'Ocultar histórico' : 'Ver histórico de conversas'}
              style={{ padding: '0.4rem 0.6rem', color: 'var(--ocean-800)' }}
            >
              <History size={16} />
            </button>

            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: '10px',
                backgroundColor: 'var(--ocean-600)',
                color: 'var(--white)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(2, 132, 199, 0.25)',
                flexShrink: 0,
              }}
            >
              <BotMessageSquare size={22} />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <strong style={{ fontSize: '1.05rem', color: 'var(--ocean-950)' }}>
                  Tutora VERA
                </strong>
                <span className="badge badge-success" style={{ fontSize: '0.725rem' }}>
                  Online
                </span>
                {user && (
                  <span className="badge badge-ocean" style={{ fontSize: '0.725rem' }}>
                    {user.nome.split(' ')[0]}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>
                {currentTitle !== 'Nova Conversa' ? currentTitle : 'IA Especialista em Matemática • Matriz do ENEM'}
              </div>
            </div>
          </div>

          <button
            onClick={handleNewChat}
            className="btn btn-outline btn-sm"
            title="Iniciar nova conversa"
            style={{ gap: '0.4rem' }}
          >
            <Plus size={15} />
            <span>Nova Conversa</span>
          </button>
        </div>

        {/* Feed de Mensagens Rolável */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.5rem 1.75rem',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {isLoadingHistory ? (
            <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)' }}>
              <Sparkles size={28} className="animate-spin text-ocean-600" style={{ margin: '0 auto 0.75rem' }} />
              <p style={{ fontSize: '0.9rem' }}>Carregando histórico da conversa...</p>
            </div>
          ) : (
            <div
              style={{
                maxWidth: '920px',
                width: '100%',
                margin: '0 auto',
                display: 'flex',
                flexDirection: 'column',
                gap: '1.25rem',
              }}
            >
              {messages.map((msg) => {
                const isUser = msg.sender === 'user';

                return (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      flexDirection: isUser ? 'row-reverse' : 'row',
                      gap: '0.85rem',
                      alignItems: 'flex-start',
                    }}
                  >
                    {/* Avatar */}
                    <div
                      style={{
                        width: '38px',
                        height: '38px',
                        borderRadius: '50%',
                        backgroundColor: isUser ? 'var(--ocean-800)' : 'var(--ocean-100)',
                        color: isUser ? 'var(--white)' : 'var(--ocean-700)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 700,
                        fontSize: '0.85rem',
                        flexShrink: 0,
                        boxShadow: 'var(--shadow-sm)',
                      }}
                    >
                      {isUser ? <UserIcon size={18} /> : <BotMessageSquare size={18} />}
                    </div>

                    {/* Balão de Mensagem */}
                    <div
                      style={{
                        maxWidth: '82%',
                        backgroundColor: isUser ? 'var(--ocean-600)' : 'var(--white)',
                        color: isUser ? 'var(--white)' : 'var(--text-primary)',
                        borderRadius: isUser ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
                        padding: '1.1rem 1.35rem',
                        boxShadow: 'var(--shadow-sm)',
                        border: isUser ? 'none' : '1px solid var(--border-light)',
                      }}
                    >
                      {/* Tag de Habilidade se houver */}
                      {!isUser && msg.habilidade_codigo && (
                        <div style={{ marginBottom: '0.5rem' }}>
                          <span className="badge badge-ocean" style={{ fontSize: '0.75rem' }}>
                            Habilidade {msg.habilidade_codigo}
                          </span>
                        </div>
                      )}

                      {/* Bloco Retrátil de Chain-of-Thought Scratchpad (<pensamento>) */}
                      {!isUser && msg.thought && (
                        <details
                          style={{
                            marginBottom: '0.85rem',
                            padding: '0.6rem 0.85rem',
                            backgroundColor: 'var(--ocean-50)',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--border-ocean)',
                            fontSize: '0.8rem',
                            color: 'var(--ocean-950)',
                          }}
                        >
                          <summary
                            style={{
                              cursor: 'pointer',
                              fontWeight: 600,
                              color: 'var(--ocean-800)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.4rem',
                            }}
                          >
                            <Brain size={15} />
                            <span>Raciocínio Pedagógico (Chain-of-Thought)</span>
                          </summary>
                          <div
                            style={{
                              marginTop: '0.5rem',
                              paddingTop: '0.5rem',
                              borderTop: '1px dashed var(--border-ocean)',
                              lineHeight: '1.5',
                              whiteSpace: 'pre-wrap',
                              fontFamily: 'monospace',
                              fontSize: '0.775rem',
                              color: 'var(--text-secondary)',
                            }}
                          >
                            {msg.thought}
                          </div>
                        </details>
                      )}

                      {/* Conteúdo com renderizador KaTeX */}
                      <div style={{ color: isUser ? 'var(--white)' : 'var(--text-primary)' }}>
                        <MathText content={msg.text} />
                      </div>

                      {/* Fontes Didáticas Recuperadas via Pinecone (RAG) */}
                      {!isUser && msg.context_chunks && msg.context_chunks.length > 0 && (
                        <div
                          style={{
                            marginTop: '0.85rem',
                            paddingTop: '0.5rem',
                            borderTop: '1px solid var(--border-light)',
                            fontSize: '0.725rem',
                            color: 'var(--text-muted)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            flexWrap: 'wrap',
                          }}
                        >
                          <BookOpen size={13} className="text-ocean-600" />
                          <span>Fontes teóricas:</span>
                          {msg.context_chunks.map((chunk, idx) => (
                            <span
                              key={chunk.id || idx}
                              className="badge"
                              style={{
                                backgroundColor: 'var(--surface-subtle)',
                                color: 'var(--ocean-900)',
                                fontSize: '0.675rem',
                                padding: '0.15rem 0.4rem',
                              }}
                            >
                              {chunk.title || chunk.document_name || `Doc ${idx + 1}`}
                            </span>
                          ))}
                        </div>
                      )}

                      <div
                        style={{
                          marginTop: '0.5rem',
                          fontSize: '0.725rem',
                          textAlign: 'right',
                          color: isUser ? 'rgba(255, 255, 255, 0.8)' : 'var(--text-muted)',
                        }}
                      >
                        {msg.timestamp}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Indicador de Digitação da Tutora */}
              {isTyping && (
                <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center' }}>
                  <div
                    style={{
                      width: '38px',
                      height: '38px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--ocean-100)',
                      color: 'var(--ocean-700)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <BotMessageSquare size={18} />
                  </div>
                  <div
                    style={{
                      backgroundColor: 'var(--white)',
                      padding: '0.75rem 1.25rem',
                      borderRadius: '4px 16px 16px 16px',
                      border: '1px solid var(--border-light)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      fontSize: '0.875rem',
                      color: 'var(--ocean-900)',
                      boxShadow: 'var(--shadow-sm)',
                    }}
                  >
                    <Sparkles size={16} className="animate-spin text-ocean-600" />
                    <span>Tutora VERA está pensando na resolução passo a passo...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Barra Inferior Fixa de Sugestões e Input */}
        <div
          style={{
            backgroundColor: 'var(--white)',
            borderTop: '1px solid var(--border-light)',
            padding: '0.75rem 1.75rem 1rem',
            flexShrink: 0,
          }}
        >
          <div style={{ maxWidth: '920px', margin: '0 auto', width: '100%' }}>
            {/* Linha de Sugestões Rápidas */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '0.75rem',
                overflowX: 'auto',
                paddingBottom: '0.25rem',
              }}
            >
              <span
                style={{
                  fontSize: '0.775rem',
                  color: 'var(--text-muted)',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  flexShrink: 0,
                }}
              >
                <Lightbulb size={14} />
                Sugestões:
              </span>
              {quickQuestions.map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(q)}
                  disabled={isTyping}
                  className="btn btn-sm"
                  style={{
                    fontSize: '0.775rem',
                    padding: '0.25rem 0.65rem',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: 'var(--ocean-50)',
                    border: '1px solid var(--border-ocean)',
                    color: 'var(--ocean-900)',
                    whiteSpace: 'nowrap',
                    fontWeight: 500,
                  }}
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Campo de Digitação e Botão de Envio */}
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end' }}>
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Digite sua dúvida de Matemática... (Pressione Enter para enviar)"
                rows={2}
                disabled={isTyping}
                style={{
                  flex: 1,
                  padding: '0.75rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  border: '1.5px solid var(--border-medium)',
                  outline: 'none',
                  fontFamily: 'inherit',
                  fontSize: '0.95rem',
                  resize: 'none',
                  lineHeight: 1.5,
                  backgroundColor: 'var(--surface-subtle)',
                }}
              />

              <button
                onClick={() => handleSendMessage()}
                disabled={!inputMessage.trim() || isTyping}
                className="btn btn-primary"
                style={{
                  padding: '0.75rem 1.25rem',
                  height: '52px',
                  borderRadius: 'var(--radius-md)',
                  flexShrink: 0,
                }}
              >
                <Send size={18} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* -----------------------------------------------------------------
          Modal de Confirmação de Exclusão de Conversa
      ------------------------------------------------------------------ */}
      {sessionToDelete && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 999,
            padding: '1rem',
          }}
          onClick={() => setSessionToDelete(null)}
        >
          <div
            className="card"
            style={{
              maxWidth: '460px',
              width: '100%',
              padding: '1.75rem',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--white)',
              boxShadow: 'var(--shadow-lg)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-danger-bg)',
                  color: 'var(--color-danger)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Trash2 size={20} />
              </div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--ocean-950)' }}>
                Excluir Conversa?
              </h3>
            </div>

            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '1.5rem' }}>
              Tem certeza que deseja apagar a conversa <strong>"{sessionToDelete.titulo}"</strong>? Todas as mensagens e raciocínios salvos serão permanentemente removidos.
            </p>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button
                onClick={() => setSessionToDelete(null)}
                className="btn btn-outline"
                style={{ fontSize: '0.875rem' }}
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmDelete}
                className="btn"
                style={{
                  backgroundColor: 'var(--color-danger)',
                  color: 'var(--white)',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                }}
              >
                Sim, Excluir
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
