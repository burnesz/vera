import React, { useState, useRef, useEffect } from 'react';
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
} from 'lucide-react';

interface ChatPageProps {
  onNavigate: (page: string) => void;
}

export const ChatPage: React.FC<ChatPageProps> = () => {
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
    } catch (err) {
      console.error('Erro ao enviar mensagem:', err);
      const errorMessage: ChatMessage = {
        id: 'msg-err-' + Date.now(),
        sender: 'vera',
        text: 'Desculpe, ocorreu uma instabilidade temporária na comunicação. Por favor, tente novamente em instantes.',
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

  return (
    <div className="container" style={{ padding: '1.5rem 1.25rem 3rem', maxWidth: '1000px' }}>
      <div
        className="card"
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: 'calc(100vh - var(--header-height) - 100px)',
          minHeight: '620px',
          padding: 0,
          overflow: 'hidden',
          border: '1.5px solid var(--border-ocean)',
          boxShadow: 'var(--shadow-ocean)',
        }}
      >
        {/* Cabeçalho do Chat */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1rem 1.5rem',
            backgroundColor: 'var(--white)',
            borderBottom: '1.5px solid var(--ocean-100)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '12px',
                backgroundColor: 'var(--ocean-600)',
                color: 'var(--white)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 10px rgba(2, 132, 199, 0.25)',
              }}
            >
              <BotMessageSquare size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
                  Tutora VERA
                </h2>
                <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>
                  Online
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                IA Especialista em Matemática • Matriz de Referência do ENEM
              </div>
            </div>
          </div>

          <button
            onClick={handleClearChat}
            className="btn btn-outline btn-sm"
            title="Reiniciar sessão e limpar histórico"
          >
            <RotateCcw size={15} />
            Nova Conversa
          </button>
        </div>

        {/* Feed de Mensagens */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.5rem',
            backgroundColor: 'var(--surface-subtle)',
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
                    width: '36px',
                    height: '36px',
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
                    maxWidth: '78%',
                    backgroundColor: isUser ? 'var(--ocean-600)' : 'var(--white)',
                    color: isUser ? 'var(--white)' : 'var(--text-primary)',
                    borderRadius: isUser
                      ? '16px 4px 16px 16px'
                      : '4px 16px 16px 16px',
                    padding: '1rem 1.25rem',
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

                  {/* Conteúdo com suporte a fórmulas */}
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
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--ocean-100)',
                  color: 'var(--ocean-700)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
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
                  fontWeight: 600,
                }}
              >
                <Sparkles size={16} color="var(--ocean-600)" />
                VERA está estruturando a resolução pedagógica...
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Chips de Perguntas Rápidas */}
        <div
          style={{
            padding: '0.65rem 1.25rem',
            backgroundColor: 'var(--white)',
            borderTop: '1px solid var(--border-light)',
            display: 'flex',
            gap: '0.5rem',
            overflowX: 'auto',
            whiteSpace: 'nowrap',
          }}
        >
          <span
            style={{
              fontSize: '0.8rem',
              fontWeight: 700,
              color: 'var(--ocean-900)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <Lightbulb size={15} color="var(--ocean-600)" />
            Sugestões:
          </span>
          {quickQuestions.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(q)}
              disabled={isTyping}
              className="btn btn-ghost btn-sm"
              style={{
                fontSize: '0.8rem',
                backgroundColor: 'var(--ocean-50)',
                border: '1px solid var(--border-ocean)',
                borderRadius: 'var(--radius-full)',
                padding: '0.25rem 0.75rem',
                color: 'var(--ocean-900)',
                fontWeight: 500,
              }}
            >
              {q}
            </button>
          ))}
        </div>

        {/* Área de Entrada de Mensagem */}
        <div
          style={{
            padding: '1rem 1.25rem',
            backgroundColor: 'var(--white)',
            borderTop: '1.5px solid var(--ocean-100)',
            display: 'flex',
            gap: '0.75rem',
            alignItems: 'center',
          }}
        >
          <textarea
            className="form-control"
            rows={1}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Digite sua dúvida de Matemática... (Pressione Enter para enviar)"
            disabled={isTyping}
            style={{
              resize: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.95rem',
              padding: '0.75rem 1rem',
            }}
          />

          <button
            onClick={() => handleSendMessage()}
            disabled={!inputMessage.trim() || isTyping}
            className="btn btn-primary"
            style={{
              padding: '0.75rem 1.25rem',
              borderRadius: 'var(--radius-md)',
              fontWeight: 700,
            }}
            title="Enviar mensagem"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
