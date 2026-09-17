import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  FileCheck2,
  BotMessageSquare,
  Sparkles,
  GraduationCap,
  UserPlus,
  LogIn,
} from 'lucide-react';

interface HomePageProps {
  onNavigate: (page: string) => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();

  return (
    <div
      className="container"
      style={{
        padding: '3rem 1.25rem 4rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - var(--header-height) - 100px)',
      }}
    >
      {/* Hero Principal Simplificado */}
      <section
        style={{
          width: '100%',
          maxWidth: '960px',
          background: 'linear-gradient(135deg, var(--ocean-900) 0%, var(--ocean-700) 100%)',
          borderRadius: 'var(--radius-lg)',
          padding: 'clamp(2rem, 5vw, 3.5rem)',
          color: 'var(--white)',
          boxShadow: 'var(--shadow-ocean)',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ maxWidth: '720px', position: 'relative', zIndex: 2 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: 'rgba(255, 255, 255, 0.15)',
              padding: '0.35rem 0.85rem',
              borderRadius: 'var(--radius-full)',
              fontSize: '0.85rem',
              fontWeight: 600,
              marginBottom: '1.25rem',
              backdropFilter: 'blur(4px)',
            }}
          >
            <Sparkles size={16} />
            Plataforma RAG para Matemática no ENEM
          </div>

          <h1
            style={{
              fontSize: 'clamp(2rem, 4.5vw, 2.75rem)',
              fontWeight: 800,
              color: 'var(--white)',
              lineHeight: 1.15,
              marginBottom: '1.25rem',
            }}
          >
            {isAuthenticated && user
              ? `Olá, ${user.nome.split(' ')[0]}! Pronto para treinar?`
              : 'Domine a Matemática do ENEM com Inteligência Pedagógica'}
          </h1>

          <p
            style={{
              fontSize: '1.1rem',
              color: 'var(--ocean-100)',
              lineHeight: 1.6,
              marginBottom: '2.25rem',
              maxWidth: '640px',
            }}
          >
            Simulados com o caderno completo de <strong>45 questões</strong>, diagnósticos
            detalhados por habilidade da Matriz de Referência e tutoria interativa
            com Chain-of-Thought.
          </p>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
            {isAuthenticated ? (
              <>
                <button
                  onClick={() => onNavigate('simulado')}
                  className="btn btn-lg"
                  style={{
                    backgroundColor: 'var(--white)',
                    color: 'var(--ocean-900)',
                    fontWeight: 700,
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                  }}
                >
                  <FileCheck2 size={20} />
                  Iniciar Simulado Geral (45 Itens)
                </button>

                <button
                  onClick={() => onNavigate('chat')}
                  className="btn btn-lg btn-outline"
                  style={{
                    backgroundColor: 'transparent',
                    borderColor: 'var(--white)',
                    color: 'var(--white)',
                    fontWeight: 600,
                  }}
                >
                  <BotMessageSquare size={20} />
                  Tirar Dúvidas com a Tutora VERA
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => onNavigate('register')}
                  className="btn btn-lg"
                  style={{
                    backgroundColor: 'var(--white)',
                    color: 'var(--ocean-900)',
                    fontWeight: 700,
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                  }}
                >
                  <UserPlus size={20} />
                  Cadastre-se para Começar
                </button>

                <button
                  onClick={() => onNavigate('login')}
                  className="btn btn-lg btn-outline"
                  style={{
                    backgroundColor: 'transparent',
                    borderColor: 'var(--white)',
                    color: 'var(--white)',
                    fontWeight: 600,
                  }}
                >
                  <LogIn size={20} />
                  Já tenho conta (Entrar)
                </button>
              </>
            )}
          </div>
        </div>

        {/* Efeito decorativo sutil de fundo */}
        <div
          style={{
            position: 'absolute',
            right: '-30px',
            bottom: '-30px',
            opacity: 0.08,
            pointerEvents: 'none',
          }}
        >
          <GraduationCap size={340} />
        </div>
      </section>
    </div>
  );
};
