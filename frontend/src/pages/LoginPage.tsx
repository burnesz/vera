import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { LogIn, AlertCircle, Lock, Mail, Sparkles } from 'lucide-react';

interface LoginPageProps {
  onNavigate: (page: string) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onNavigate }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Por favor, informe e-mail e senha.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login({
        email: email.trim().toLowerCase(),
        password,
      });
      onNavigate('home');
    } catch (err: any) {
      setError(err.message || 'Credenciais inválidas. Verifique seu e-mail e senha.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDemoFill = () => {
    setEmail('admin@vera.edu.br');
    setPassword('admin123456');
    setError(null);
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - var(--header-height) - 160px)',
        padding: '2rem 1rem',
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: '460px',
          boxShadow: 'var(--shadow-ocean)',
          border: '1.5px solid var(--border-ocean)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '1.75rem' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              backgroundColor: 'var(--ocean-100)',
              color: 'var(--ocean-700)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '1rem',
            }}
          >
            <LogIn size={28} />
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--ocean-950)' }}>
            Acessar Plataforma
          </h1>
          <p style={{ fontSize: '0.925rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            Entre para acessar seus simulados e o feedback pedagógico
          </p>
        </div>

        {error && (
          <div
            style={{
              backgroundColor: 'var(--color-danger-bg)',
              border: '1px solid #fca5a5',
              color: 'var(--color-danger)',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
              marginBottom: '1.25rem',
              fontSize: '0.9rem',
              fontWeight: 500,
            }}
          >
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label" htmlFor="login-email">
              E-mail
            </label>
            <div style={{ position: 'relative' }}>
              <Mail
                size={18}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--ocean-600)',
                }}
              />
              <input
                id="login-email"
                type="email"
                className="form-control"
                style={{ paddingLeft: '2.5rem' }}
                placeholder="seu.email@exemplo.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="login-password">
              Senha
            </label>
            <div style={{ position: 'relative' }}>
              <Lock
                size={18}
                style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--ocean-600)',
                }}
              />
              <input
                id="login-password"
                type="password"
                className="form-control"
                style={{ paddingLeft: '2.5rem' }}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            style={{ width: '100%', marginTop: '0.75rem' }}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Verificando...' : 'Entrar na Conta'}
          </button>
        </form>

        {/* Botão de Preenchimento Rápido / Demo */}
        <div style={{ marginTop: '1rem', textAlign: 'center' }}>
          <button
            type="button"
            onClick={handleDemoFill}
            className="btn btn-ghost btn-sm"
            style={{
              color: 'var(--ocean-700)',
              backgroundColor: 'var(--ocean-50)',
              border: '1px dashed var(--border-ocean)',
              width: '100%',
            }}
          >
            <Sparkles size={16} />
            Preenchimento Rápido (Demo / Admin)
          </button>
        </div>

        <div
          style={{
            marginTop: '1.75rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--border-light)',
            textAlign: 'center',
            fontSize: '0.9rem',
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>Ainda não tem conta? </span>
          <button
            onClick={() => onNavigate('register')}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--ocean-700)',
              fontWeight: 700,
              cursor: 'pointer',
              padding: 0,
            }}
          >
            Criar conta gratuita
          </button>
        </div>
      </div>
    </div>
  );
};
