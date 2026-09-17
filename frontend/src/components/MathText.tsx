import React from 'react';

interface MathTextProps {
  content: string;
  className?: string;
}

export const MathText: React.FC<MathTextProps> = ({ content, className = '' }) => {
  if (!content) return null;

  // Renderização formatada preservando quebras de linha e destacando fórmulas matemáticas
  const paragraphs = content.split('\n\n');

  return (
    <div className={`math-text-container ${className}`} style={{ lineHeight: '1.65' }}>
      {paragraphs.map((para, pIdx) => {
        // Se for fórmula em bloco com $$ ... $$
        if (para.trim().startsWith('$$') && para.trim().endsWith('$$')) {
          const formula = para.trim().slice(2, -2).trim();
          return (
            <div
              key={pIdx}
              style={{
                background: 'var(--ocean-50)',
                borderLeft: '4px solid var(--ocean-600)',
                padding: '0.75rem 1.25rem',
                margin: '0.85rem 0',
                borderRadius: '0 8px 8px 0',
                fontFamily: 'monospace',
                fontSize: '1.05rem',
                color: 'var(--text-primary)',
                fontWeight: 600,
                overflowX: 'auto',
              }}
            >
              {formula}
            </div>
          );
        }

        // Divide o parágrafo por linhas simples
        const lines = para.split('\n');

        return (
          <p key={pIdx} style={{ marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {renderInlineMathAndBold(line)}
                {lIdx < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
};

// Auxiliar para destacar fórmulas inline $...$ e textos em negrito **...**
function renderInlineMathAndBold(text: string): React.ReactNode[] {
  // Expressão regular para capturar $formula$ ou **bold** ou *italic*
  const tokenRegex = /(\$[^$]+\$|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  const parts = text.split(tokenRegex);

  return parts.map((part, index) => {
    if (part.startsWith('$') && part.endsWith('$')) {
      const math = part.slice(1, -1);
      return (
        <span
          key={index}
          style={{
            fontFamily: 'monospace',
            backgroundColor: 'var(--ocean-100)',
            padding: '0.1rem 0.35rem',
            borderRadius: '4px',
            fontWeight: 600,
            color: 'var(--ocean-950)',
            fontSize: '0.95em',
          }}
        >
          {math}
        </span>
      );
    }

    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={index} style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
          {part.slice(2, -2)}
        </strong>
      );
    }

    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }

    return part;
  });
}
