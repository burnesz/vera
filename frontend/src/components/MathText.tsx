import React from 'react';
import katex from 'katex';

interface MathTextProps {
  content: string;
  className?: string;
}

export const MathText: React.FC<MathTextProps> = ({ content, className = '' }) => {
  if (!content) return null;

  // 1. Separar blocos de matemática (\[ ... \] ou $$ ... $$) do texto padrão
  const blockRegex = /(\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$)/g;
  const sections = content.split(blockRegex);

  return (
    <div className={`math-text-container ${className}`} style={{ lineHeight: 1.65, fontSize: '0.975rem' }}>
      {sections.map((section, sIdx) => {
        if (!section) return null;

        // Bloco LaTeX delimitado por \[ ... \]
        if (section.startsWith('\\[') && section.endsWith('\\]')) {
          const rawMath = section.slice(2, -2).trim();
          return renderKaTeX(rawMath, true, `block-${sIdx}`);
        }

        // Bloco LaTeX delimitado por $$ ... $$
        if (section.startsWith('$$') && section.endsWith('$$')) {
          const rawMath = section.slice(2, -2).trim();
          return renderKaTeX(rawMath, true, `block-${sIdx}`);
        }

        // Segmento de texto normal com potenciais parágrafos e elementos inline
        return renderParagraphs(section, sIdx);
      })}
    </div>
  );
};

// Renderiza uma expressão LaTeX com KaTeX (bloco ou inline)
function renderKaTeX(math: string, displayMode: boolean, key: string) {
  try {
    const html = katex.renderToString(math, {
      displayMode,
      throwOnError: false,
      output: 'htmlAndMathml',
    });

    if (displayMode) {
      return (
        <div
          key={key}
          className="katex-block-wrapper"
          style={{
            margin: '0.85rem 0',
            padding: '0.75rem 1rem',
            backgroundColor: 'var(--ocean-50)',
            borderRadius: 'var(--radius-md)',
            borderLeft: '4px solid var(--ocean-600)',
            overflowX: 'auto',
            fontSize: '1.05rem',
          }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      );
    }

    return (
      <span
        key={key}
        className="katex-inline-wrapper"
        style={{
          padding: '0 0.2rem',
          fontSize: '1.02em',
        }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    );
  } catch {
    return (
      <code key={key} style={{ backgroundColor: 'var(--ocean-100)', padding: '0.1rem 0.3rem', borderRadius: '4px' }}>
        {math}
      </code>
    );
  }
}

// Renderiza parágrafos de texto comum
function renderParagraphs(text: string, sectionIdx: number) {
  const paragraphs = text.split(/\n\s*\n/);

  return (
    <React.Fragment key={`sec-${sectionIdx}`}>
      {paragraphs.map((para, pIdx) => {
        if (!para.trim()) return null;
        const lines = para.split('\n');

        return (
          <p key={`p-${sectionIdx}-${pIdx}`} style={{ marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
            {lines.map((line, lIdx) => (
              <React.Fragment key={`l-${lIdx}`}>
                {renderInlineTokens(line)}
                {lIdx < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </React.Fragment>
  );
}

// Tokenizador recursivo para capturar inline math \(...\), $...$, **bold** e *italic*
function renderInlineTokens(text: string): React.ReactNode[] {
  // Regex captura:
  // 1. \( ... \)
  // 2. $ ... $
  // 3. ** ... **
  // 4. * ... *
  const inlineRegex = /(\\\([\s\S]*?\\\)|\$[^$]+?\$|\*\*[^*]+?\*\*|\*[^*]+?\*)/g;
  const parts = text.split(inlineRegex);

  return parts.map((part, index) => {
    if (!part) return null;

    // Inline LaTeX \( ... \)
    if (part.startsWith('\\(') && part.endsWith('\\)')) {
      const math = part.slice(2, -2).trim();
      return renderKaTeX(math, false, `inline-paren-${index}-${part.slice(0, 8)}`);
    }

    // Inline LaTeX $ ... $
    if (part.startsWith('$') && part.endsWith('$') && part.length > 2) {
      const math = part.slice(1, -1).trim();
      return renderKaTeX(math, false, `inline-dollar-${index}-${part.slice(0, 8)}`);
    }

    // Negrito ** ... ** (processa recursivamente para permitir fórmulas dentro do negrito)
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      const inner = part.slice(2, -2);
      return (
        <strong key={`bold-${index}`} style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
          {renderInlineTokens(inner)}
        </strong>
      );
    }

    // Itálico * ... * (processa recursivamente)
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      const inner = part.slice(1, -1);
      return <em key={`italic-${index}`}>{renderInlineTokens(inner)}</em>;
    }

    return part;
  });
}
