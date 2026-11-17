import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Sparkles, Square, CheckCircle2, XCircle, Download, ChevronDown, ChevronRight } from 'lucide-react';
import { MathText } from '../components/MathText';
import { adminIneditasService } from '../services/adminIneditasService';
import type { HabilidadeAtiva, Lote, PedidoLote } from '../services/adminIneditasService';

const CHAVE_LOTE = 'vera_admin_lote_ineditas';
const MINUTOS_POR_QUESTAO = 11; // média do Experimento 2 por questão aprovada, com geração e validação

const ROTULO_STATUS: Record<PedidoLote['status'], string> = {
  aguardando: 'Aguardando',
  gerando: 'Gerando',
  aprovada: 'Aprovada',
  reprovada: 'Reprovada',
  nao_gerado: 'Não gerada',
};

const lerLoteSalvo = (): string | null => {
  try {
    return localStorage.getItem(CHAVE_LOTE);
  } catch {
    return null;
  }
};

const salvarLote = (id: string | null) => {
  try {
    if (id) localStorage.setItem(CHAVE_LOTE, id);
    else localStorage.removeItem(CHAVE_LOTE);
  } catch {
    /* sem armazenamento local: o acompanhamento só não sobrevive a um recarregamento */
  }
};

export const AdminIneditasPage: React.FC = () => {
  const [habilidades, setHabilidades] = useState<HabilidadeAtiva[]>([]);
  const [selecionadas, setSelecionadas] = useState<Set<string>>(new Set());
  const [quantidade, setQuantidade] = useState(1);
  const [maxTentativas, setMaxTentativas] = useState(5);
  const [lote, setLote] = useState<Lote | null>(null);
  const [loteId, setLoteId] = useState<string | null>(lerLoteSalvo);
  const [escolhidas, setEscolhidas] = useState<Set<string>>(new Set());
  const [abertas, setAbertas] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    adminIneditasService
      .habilidades()
      .then(setHabilidades)
      .catch((e) => setErro(e.message));
  }, []);

  const atualizar = useCallback(async (id: string) => {
    try {
      setLote(await adminIneditasService.consultarLote(id));
    } catch (e: any) {
      if (e.status === 404) {
        salvarLote(null);
        setLoteId(null);
        setLote(null);
      } else {
        setErro(e.message);
      }
    }
  }, []);

  useEffect(() => {
    if (!loteId) return;
    atualizar(loteId);
  }, [loteId, atualizar]);

  const emAndamento = lote?.status === 'em_andamento';
  useEffect(() => {
    if (!loteId || !emAndamento) return;
    const t = window.setInterval(() => atualizar(loteId), 5000);
    return () => window.clearInterval(t);
  }, [loteId, emAndamento, atualizar]);

  const aprovadas = useMemo(
    () => (lote?.pedidos || []).filter((p) => p.status === 'aprovada' && p.questao).map((p) => p.questao!),
    [lote]
  );
  const pendentesDeImportar = aprovadas.filter((q) => !q.no_acervo);

  const alternar = (conjunto: Set<string>, valor: string, setter: (s: Set<string>) => void) => {
    const novo = new Set(conjunto);
    if (novo.has(valor)) novo.delete(valor);
    else novo.add(valor);
    setter(novo);
  };

  const todasMarcadas = habilidades.length > 0 && selecionadas.size === habilidades.length;
  const totalPedidos = selecionadas.size * quantidade;

  const gerar = async () => {
    setErro(null);
    setAviso(null);
    setEnviando(true);
    try {
      const pedido = todasMarcadas ? 'all' : Array.from(selecionadas).sort();
      const r = await adminIneditasService.criarLote(pedido, quantidade, maxTentativas);
      salvarLote(r.id);
      setEscolhidas(new Set());
      setLoteId(r.id);
    } catch (e: any) {
      setErro(e.message);
    } finally {
      setEnviando(false);
    }
  };

  const cancelar = async () => {
    if (!loteId) return;
    try {
      setLote(await adminIneditasService.cancelarLote(loteId));
      setAviso('Cancelamento pedido: o lote para depois da questão em andamento.');
    } catch (e: any) {
      setErro(e.message);
    }
  };

  const importar = async (ids: string[]) => {
    if (!loteId || ids.length === 0) return;
    setErro(null);
    setEnviando(true);
    try {
      const r = await adminIneditasService.importar(loteId, ids);
      setAviso(
        `${r.importadas.length} questão(ões) adicionada(s) ao acervo` +
          (r.ja_existiam.length ? `; ${r.ja_existiam.length} já estava(m) nele.` : '.')
      );
      setEscolhidas(new Set());
      await atualizar(loteId);
    } catch (e: any) {
      setErro(e.message);
    } finally {
      setEnviando(false);
    }
  };

  const progresso = lote && lote.total ? Math.round((100 * lote.feitos) / lote.total) : 0;

  return (
    <div style={{ padding: '1.5rem', maxWidth: 1100, width: '100%', margin: '0 auto', display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: '1.25rem' }}>
      {erro && (
        <div role="alert" className="card" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)', padding: '0.85rem 1rem' }}>
          {erro}
        </div>
      )}
      {aviso && (
        <div className="card" style={{ background: 'var(--color-success-bg)', padding: '0.85rem 1rem' }}>
          {aviso}
        </div>
      )}

      {/* Novo lote */}
      <section className="card" style={{ padding: '1.25rem' }}>
        <h2 style={{ margin: '0 0 0.35rem', fontSize: '1.1rem' }}>Novo lote</h2>
        <p style={{ margin: '0 0 1rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
          Cada questão é gerada pelo Qwen 2.5, com o cálculo feito por código, e validada pelo Qwen3. Só as aprovadas
          podem entrar no acervo dos simulados, e é você quem decide quais entram.
        </p>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          <input
            type="checkbox"
            checked={todasMarcadas}
            onChange={() => setSelecionadas(todasMarcadas ? new Set() : new Set(habilidades.map((h) => h.codigo)))}
          />
          Todas as habilidades ativas ({habilidades.length})
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(78px, 1fr))', gap: '0.35rem', marginBottom: '1rem' }}>
          {habilidades.map((h) => (
            <label key={h.codigo} title={h.descricao} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.875rem' }}>
              <input
                type="checkbox"
                checked={selecionadas.has(h.codigo)}
                onChange={() => alternar(selecionadas, h.codigo, setSelecionadas)}
              />
              {h.codigo}
            </label>
          ))}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Questões por habilidade</label>
            <input className="form-control" type="number" min={1} max={10} value={quantidade}
              onChange={(e) => setQuantidade(Math.min(10, Math.max(1, Number(e.target.value) || 1)))} style={{ width: 110 }} />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label className="form-label">Tentativas por questão</label>
            <input className="form-control" type="number" min={1} max={10} value={maxTentativas}
              onChange={(e) => setMaxTentativas(Math.min(10, Math.max(1, Number(e.target.value) || 1)))} style={{ width: 110 }} />
          </div>
          <button className="btn btn-primary" disabled={!totalPedidos || enviando || emAndamento} onClick={gerar}>
            {enviando ? <Loader2 size={18} className="spin" /> : <Sparkles size={18} />}
            Gerar {totalPedidos || ''} questão(ões)
          </button>
          {totalPedidos > 0 && (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Estimativa: cerca de {(Math.ceil(((totalPedidos * MINUTOS_POR_QUESTAO) / 60) * 10) / 10).toLocaleString('pt-BR')} h
              ({MINUTOS_POR_QUESTAO} min por questão)
            </span>
          )}
        </div>
        {emAndamento && (
          <p style={{ margin: '0.75rem 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Há um lote em andamento; um novo só pode começar quando ele terminar.
          </p>
        )}
      </section>

      {/* Andamento */}
      {lote && (
        <section className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
              Lote {lote.status === 'em_andamento' ? 'em andamento' : lote.status === 'concluido' ? 'concluído' : lote.status}
            </h2>
            {emAndamento && (
              <button className="btn btn-outline btn-sm" onClick={cancelar}>
                <Square size={16} /> Cancelar
              </button>
            )}
          </div>
          <div style={{ margin: '0.75rem 0', height: 10, background: 'var(--surface-subtle)', borderRadius: 999, overflow: 'hidden' }}>
            <div style={{ width: `${progresso}%`, height: '100%', background: 'var(--ocean-600)', transition: 'width .4s' }} />
          </div>
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.875rem' }}>
            {lote.feitos} de {lote.total} feitas · {lote.aprovadas} aprovada(s)
            {lote.erro && <span style={{ color: 'var(--color-danger)' }}> · {lote.erro}</span>}
          </p>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.35rem' }}>#</th>
                  <th style={{ padding: '0.35rem' }}>Habilidade</th>
                  <th style={{ padding: '0.35rem' }}>Situação</th>
                  <th style={{ padding: '0.35rem' }}>Tentativas</th>
                </tr>
              </thead>
              <tbody>
                {lote.pedidos.map((p) => (
                  <tr key={p.n} style={{ borderTop: '1px solid var(--border-light)' }}>
                    <td style={{ padding: '0.35rem' }}>{p.n}</td>
                    <td style={{ padding: '0.35rem' }}>{p.habilidade}</td>
                    <td style={{ padding: '0.35rem' }}>
                      {p.status === 'gerando' && <Loader2 size={14} className="spin" style={{ verticalAlign: 'middle' }} />}{' '}
                      {ROTULO_STATUS[p.status]}
                    </td>
                    <td style={{ padding: '0.35rem' }}>
                      {p.tentativas}/{lote.max_tentativas}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Aprovadas */}
      {lote && aprovadas.length > 0 && (
        <section className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Questões aprovadas</h2>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button className="btn btn-outline btn-sm" disabled={!escolhidas.size || enviando}
                onClick={() => importar(Array.from(escolhidas))}>
                <Download size={16} /> Adicionar selecionadas ({escolhidas.size})
              </button>
              <button className="btn btn-primary btn-sm" disabled={!pendentesDeImportar.length || enviando}
                onClick={() => importar(pendentesDeImportar.map((q) => q.id))}>
                <Download size={16} /> Adicionar todas ({pendentesDeImportar.length})
              </button>
            </div>
          </div>
          <p style={{ margin: '0 0 0.75rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            A validação automática não barra todos os erros de conteúdo. Revise cada questão antes de adicioná-la.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: '0.6rem' }}>
            {aprovadas.map((q) => {
              const aberta = abertas.has(q.id);
              return (
                <div key={q.id} style={{ border: '1px solid var(--border-light)', borderRadius: 10, padding: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <input type="checkbox" disabled={q.no_acervo} checked={escolhidas.has(q.id)}
                      onChange={() => alternar(escolhidas, q.id, setEscolhidas)} aria-label={`Selecionar questão ${q.id}`} />
                    <button className="btn btn-ghost btn-sm" onClick={() => alternar(abertas, q.id, setAbertas)}
                      style={{ padding: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.4rem', flex: 1, justifyContent: 'flex-start', minWidth: 0, overflow: 'hidden' }}>
                      {aberta ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                      <strong>{q.habilidade_codigo}</strong>
                      <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {q.enunciado.split('\n')[0]}
                      </span>
                    </button>
                    {q.no_acervo ? (
                      <span className="badge badge-success"><CheckCircle2 size={13} /> No acervo</span>
                    ) : (
                      <span className="badge badge-warning"><XCircle size={13} /> Fora do acervo</span>
                    )}
                  </div>
                  {aberta && (
                    <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.6rem', fontSize: '0.925rem' }}>
                      <MathText content={q.enunciado} />
                      <ol style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: '0.25rem' }}>
                        {Object.entries(q.alternativas).sort().map(([letra, texto]) => (
                          <li key={letra} style={{ display: 'flex', gap: '0.4rem', alignItems: 'baseline', fontWeight: letra === q.gabarito ? 700 : 400, color: letra === q.gabarito ? 'var(--color-success)' : undefined }}>
                            <span>{letra})</span>
                            <MathText content={texto} />
                          </li>
                        ))}
                      </ol>
                      <div style={{ background: 'var(--surface-subtle)', borderRadius: 8, padding: '0.6rem 0.75rem' }}>
                        <strong>Gabarito {q.gabarito}</strong>
                        <MathText content={q.justificativa} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
      <style>{`.spin { animation: spin 0.8s linear infinite; } @keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
    </div>
  );
};
