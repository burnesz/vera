import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { chatService } from '../services/chatService';
import type { ChatMessage } from '../types/chat';
import { MathText } from '../components/MathText';
import {
  Send,
  RotateCcw,
  Sparkles,
  BotMessageSquare,
  User as UserIcon,
  Lightbulb,
  Lock,
} from 'lucide-react';

interface ChatPageProps {
  onNavigate: (page: string) => void;
}

export const ChatPage: React.FC<ChatPageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    return [
      {
        id: 'welcome-1',
        sender: 'vera',
        text: `Olá! Sou a **VERA**, sua Tutora Especialista em Matemática para o ENEM. 

Estou aqui para tirar dúvidas teóricas, detalhar resoluções passo a passo (com fórmulas matemáticas) e ajudá-lo a compreender as 30 habilidades da Matriz de Referência.

Sobre qual conteúdo de Matemática você gostaria de conversar hoje?`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ];
  });

  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId] = useState<string>(() => 'session-' + Date.now());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll para o final da conversa
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

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
        session_id: sessionId,
        message: text,
      });

      const veraMessage: ChatMessage = {
        id: 'msg-' + (Date.now() + 1),
        sender: 'vera',
        text: response.reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        habilidade_codigo: response.habilidade_detectada,
      };

      setMessages((prev) => [...prev, veraMessage]);
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

  const handleClearChat = async () => {
    await chatService.clearSession(sessionId);
    setMessages([
      {
        id: 'welcome-reset-' + Date.now(),
        sender: 'vera',
        text: 'Histórico reiniciado com sucesso. Em que tópico de Matemática posso te ajudar agora?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
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
            Para conversar com a Tutora Inteligente e ter seu histórico de aprendizado registrado, você precisa estar cadastrado e conectado à plataforma.
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
  // Janela de Chat Full-Bleed (topando na sidebar e na topbar sem molduras)
  // =========================================================================
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - var(--topbar-height))',
        width: '100%',
        backgroundColor: 'var(--surface-subtle)',
        overflow: 'hidden',
      }}
    >
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
                  Estudante: {user.nome.split(' ')[0]}
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.775rem', color: 'var(--text-muted)' }}>
              IA Especialista em Matemática • Matriz de Referência do ENEM
            </div>
          </div>
        </div>

        <button
          onClick={handleClearChat}
          className="btn btn-outline btn-sm"
          title="Reiniciar sessão e limpar histórico"
          style={{ gap: '0.4rem' }}
        >
          <RotateCcw size={15} />
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

                  {/* Conteúdo com renderizador KaTeX */}
                  <div style={{ color: isUser ? 'var(--white)' : 'var(--text-primary)' }}>
                    <MathText content={msg.text} />
                  </div>

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
                <Sparkles size={16} className="animate-spin" />
                <span>Tutora VERA está pensando na resolução passo a passo...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
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
  );
};
