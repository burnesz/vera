import React from 'react';
import { BookOpen, ShieldCheck, Heart } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer
      style={{
        backgroundColor: 'var(--white)',
        borderTop: '1px solid var(--border-light)',
        marginTop: 'auto',
        padding: '2.5rem 0 1.75rem',
      }}
    >
      <div className="container">
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '2rem',
            marginBottom: '2rem',
          }}
        >
          {/* Coluna 1: Sobre */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
              <span style={{ fontWeight: 800, fontSize: '1.25rem', color: 'var(--ocean-900)' }}>VERA</span>
              <span className="badge badge-ocean">TCC 2026</span>
            </div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              Plataforma baseada em RAG para feedback pedagógico personalizado e geração de questões inéditas de Matemática no contexto do ENEM.
            </p>
          </div>

          {/* Coluna 2: Pilares da Pesquisa */}
          <div>
            <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--ocean-950)' }}>
              Metodologia & IA
            </h4>
            <ul style={{ listStyle: 'none', fontSize: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', color: 'var(--text-secondary)' }}>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <BookOpen size={16} color="var(--ocean-600)" />
                Matriz de Referência Oficial (H01–H30)
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <ShieldCheck size={16} color="var(--ocean-600)" />
                RAG com Qwen 2.5 7B & Pinecone
              </li>
              <li style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Heart size={16} color="var(--ocean-600)" />
                Chain-of-Thought Pedagógico
              </li>
            </ul>
          </div>

          {/* Coluna 3: Escopo e Segurança */}
          <div>
            <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--ocean-950)' }}>
              Escopo Estrito
            </h4>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.6' }}>
              Focado exclusivamente na área de <strong>Matemática e suas Tecnologias</strong> do ENEM (2009–2024), assegurando precisão conceitual e verificação de gabaritos.
            </p>
          </div>
        </div>

        <div
          style={{
            borderTop: '1px solid var(--border-light)',
            paddingTop: '1.25rem',
            textAlign: 'center',
            fontSize: '0.825rem',
            color: 'var(--text-muted)',
          }}
        >
          © 2026 VERA — Sistema de Aprendizado de Matemática do ENEM. Todos os direitos reservados.
        </div>
      </div>
    </footer>
  );
};
