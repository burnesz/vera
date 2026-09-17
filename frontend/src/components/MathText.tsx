import React from 'react';
import katex from 'katex';

interface MathTextProps {
  content: string;
  className?: string;
}

interface TableBlock {
  type: 'table';
  headers: string[];
  aligns: ('left' | 'center' | 'right')[];
  rows: string[][];
}

interface TextBlock {
  type: 'text';
  text: string;
}

type ContentBlock = TableBlock | TextBlock;

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

        // Segmento de texto normal com potenciais tabelas, parágrafos e elementos inline
        return renderTextWithTables(section, sIdx);
      })}
    </div>
  );
};

// Divide uma linha delimitada por pipes em células, respeitando fórmulas de matemática inline
function parseTableRow(line: string): string[] {
  let trimmed = line.trim();
  if (trimmed.startsWith('|')) {
    trimmed = trimmed.slice(1);
  }
  if (trimmed.endsWith('|')) {
    trimmed = trimmed.slice(0, -1);
  }

  const cells: string[] = [];
  let currentCell = '';
  let inDollar = false;
  let inParen = false;

  for (let idx = 0; idx < trimmed.length; idx++) {
    const char = trimmed[idx];
    const prevChar = idx > 0 ? trimmed[idx - 1] : '';
    const nextChar = idx + 1 < trimmed.length ? trimmed[idx + 1] : '';

    if (char === '$' && prevChar !== '\\') {
      inDollar = !inDollar;
      currentCell += char;
    } else if (char === '\\' && nextChar === '(') {
      inParen = true;
      currentCell += char;
    } else if (char === '\\' && nextChar === ')') {
      inParen = false;
      currentCell += char;
    } else if (char === '|' && !inDollar && !inParen) {
      cells.push(currentCell.trim());
      currentCell = '';
    } else {
      currentCell += char;
    }
  }
  cells.push(currentCell.trim());

  return cells;
}

// Analisa um bloco de texto identificando tabelas Markdown e parágrafos de texto
function parseBlocks(text: string): ContentBlock[] {
  const allLines = text.split('\n');
  const blocks: ContentBlock[] = [];
  let currentTextLines: string[] = [];
  let i = 0;

  while (i < allLines.length) {
    const line = allLines[i];
    const nextLine = i + 1 < allLines.length ? allLines[i + 1] : null;
    const isHeaderCandidate = line.includes('|') && line.trim().length > 0;
    let isTableStart = false;
    let aligns: ('left' | 'center' | 'right')[] = [];
    let headers: string[] = [];

    if (isHeaderCandidate && nextLine && nextLine.includes('|')) {
      const delimCells = parseTableRow(nextLine);
      if (delimCells.length > 0 && delimCells.every((c) => /^:?-+:?$/.test(c))) {
        headers = parseTableRow(line);
        if (headers.length > 0) {
          isTableStart = true;
          aligns = delimCells.map((c) => {
            const leftColon = c.startsWith(':');
            const rightColon = c.endsWith(':');
            if (leftColon && rightColon) return 'center';
            if (rightColon) return 'right';
            return 'left';
          });
        }
      }
    }

    if (isTableStart) {
      if (currentTextLines.length > 0) {
        blocks.push({ type: 'text', text: currentTextLines.join('\n') });
        currentTextLines = [];
      }
      i += 2; // pula cabeçalho e delimitador
      const rows: string[][] = [];
      while (i < allLines.length) {
        const rowLine = allLines[i];
        if (!rowLine.trim() || !rowLine.includes('|')) {
          break; // término da tabela
        }
        rows.push(parseTableRow(rowLine));
        i++;
      }
      blocks.push({
        type: 'table',
        headers,
        aligns,
        rows,
      });
      continue;
    }

    currentTextLines.push(line);
    i++;
  }

  if (currentTextLines.length > 0) {
    blocks.push({ type: 'text', text: currentTextLines.join('\n') });
  }

  return blocks;
}

// Renderiza tabela estilizada
function renderTable(table: TableBlock, key: string) {
  return (
    <div key={key} className="math-table-wrapper">
      <table className="math-table">
        <thead>
          <tr>
            {table.headers.map((header, hIdx) => {
              const align = table.aligns[hIdx] || 'left';
              return (
                <th key={`th-${hIdx}`} style={{ textAlign: align }}>
                  {renderInlineTokens(header)}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, rIdx) => (
            <tr key={`tr-${rIdx}`}>
              {row.map((cell, cIdx) => {
                const align = table.aligns[cIdx] || 'left';
                return (
                  <td key={`td-${rIdx}-${cIdx}`} style={{ textAlign: align }}>
                    {renderInlineTokens(cell)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Renderiza texto contendo tabelas e parágrafos
function renderTextWithTables(text: string, sectionIdx: number) {
  const blocks = parseBlocks(text);

  return (
    <React.Fragment key={`sec-${sectionIdx}`}>
      {blocks.map((block, bIdx) => {
        if (block.type === 'table') {
          return renderTable(block, `tbl-${sectionIdx}-${bIdx}`);
        }
        return renderParagraphs(block.text, `${sectionIdx}-${bIdx}`);
      })}
    </React.Fragment>
  );
}

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
function renderParagraphs(text: string, keyPrefix: string | number) {
  const paragraphs = text.split(/\n\s*\n/);

  return (
    <React.Fragment key={`sec-para-${keyPrefix}`}>
      {paragraphs.map((para, pIdx) => {
        if (!para.trim()) return null;
        const lines = para.split('\n');

        return (
          <p key={`p-${keyPrefix}-${pIdx}`} style={{ marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
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
