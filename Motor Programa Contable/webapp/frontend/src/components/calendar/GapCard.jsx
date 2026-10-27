import React from 'react';
import { Link2, Search, HelpCircle, AlertTriangle, Wand2, Compass } from 'lucide-react';

const GapCard = ({ item, onResolve, keyPrefix = 'gap', idx = 0 }) => {
  const cat = item.category || 'unknown';
  const catConfig = {
    probable_match: { label: 'Transferencia Probable', color: '#10B981', bg: 'rgba(16, 185, 129, 0.15)', icon: Link2 },
    missing_data: { label: 'Falta Extracto', color: '#F59E0B', bg: 'rgba(245, 158, 11, 0.15)', icon: Search },
    unknown: { label: 'Origen a Investigar', color: '#818CF8', bg: 'rgba(129, 140, 248, 0.15)', icon: HelpCircle }
  }[cat] || { label: 'Pendiente', color: '#F59E0B', bg: 'rgba(245, 158, 11, 0.15)', icon: AlertTriangle };
  const CatIcon = catConfig.icon;

  return (
    <div
      key={`${keyPrefix}-${idx}`}
      style={{
        background: 'rgba(15, 23, 42, 0.85)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: '1rem 1.15rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.65rem'
      }}
    >
      {/* Top Row: Operation details + Resolve button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
          <span className="badge badge-slate" style={{ fontSize: '0.75rem', fontWeight: 700 }}>
            {item.exchange}
          </span>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.25rem',
              fontSize: '0.68rem',
              fontWeight: 700,
              padding: '0.15rem 0.5rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: catConfig.bg,
              color: catConfig.color
            }}
          >
            <CatIcon size={11} /> {catConfig.label}
          </span>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }} className="font-mono">
            {item.date ? item.date.split(' ')[0] : ''}
          </span>
          <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F8FAFC' }}>
            Venta de {item.sold_qty} {item.coin}
            <span style={{ color: '#FB7185', marginLeft: '0.4rem', fontWeight: 600, fontSize: '0.82rem' }}>
              (Déficit: {item.deficit ? (Number(item.deficit) < 0.0001 && Number(item.deficit) > 0 ? Number(item.deficit).toFixed(8) : Number(item.deficit).toFixed(4)) : 0} {item.coin})
            </span>
          </span>
        </div>

        <button
          className="btn-primary"
          style={{
            background: 'linear-gradient(135deg, #F59E0B, #D97706)',
            border: 'none',
            padding: '0.35rem 0.75rem',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.35rem',
            color: '#fff',
            fontWeight: 600
          }}
          onClick={() => onResolve && onResolve(item)}
        >
          <Wand2 size={13} />
          Resolver →
        </button>
      </div>

      {/* Clues Section */}
      {item.clues && item.clues.length > 0 && (
        <div
          style={{
            padding: '0.65rem 0.85rem',
            backgroundColor: 'rgba(11, 17, 32, 0.7)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid rgba(148, 163, 184, 0.12)'
          }}
        >
          <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--brand-indigo-light)', marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            <Compass size={13} /> Pistas Sugeridas de Búsqueda (Hipótesis orientativas, no certeza):
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.45rem', fontStyle: 'italic' }}>
            * Deducciones probabilísticas para orientar tu búsqueda; no constituyen certeza contable hasta cargar el extracto o confirmar el movimiento.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {item.clues.map((clue, cIdx) => (
              <div key={cIdx} style={{ fontSize: '0.78rem', color: '#CBD5E1', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem', lineHeight: 1.4 }}>
                <span style={{ display: 'flex', alignItems: 'flex-start', gap: '0.4rem' }}>
                  <span>{clue.icon || '•'}</span>
                  <span>{clue.message}</span>
                </span>
                {clue.confidence && (
                  <span
                    style={{
                      fontSize: '0.62rem',
                      textTransform: 'uppercase',
                      padding: '0.1rem 0.45rem',
                      borderRadius: '3px',
                      fontWeight: 700,
                      flexShrink: 0,
                      backgroundColor: (clue.confidence === 'certera' || clue.confidence === '100% certera')
                        ? 'rgba(99, 102, 241, 0.3)'
                        : clue.confidence === 'alta'
                          ? 'rgba(16, 185, 129, 0.2)'
                          : clue.confidence === 'media'
                            ? 'rgba(245, 158, 11, 0.2)'
                            : 'rgba(148, 163, 184, 0.2)',
                      color: (clue.confidence === 'certera' || clue.confidence === '100% certera')
                        ? '#A5B4FC'
                        : clue.confidence === 'alta'
                          ? '#34D399'
                          : clue.confidence === 'media'
                            ? '#FBBF24'
                            : '#94A3B8',
                      border: (clue.confidence === 'certera' || clue.confidence === '100% certera')
                        ? '1px solid rgba(129, 140, 248, 0.4)'
                        : 'none'
                    }}
                  >
                    {(clue.confidence === 'certera' || clue.confidence === '100% certera') ? '100% Certera' : clue.confidence}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Action Callout */}
      {item.recommended_action && (
        <div
          style={{
            padding: '0.5rem 0.85rem',
            backgroundColor: 'rgba(79, 70, 229, 0.08)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid rgba(79, 70, 229, 0.22)',
            fontSize: '0.78rem',
            color: '#E2E8F0',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.45rem'
          }}
        >
          <span style={{ color: 'var(--brand-indigo-light)', fontWeight: 700, whiteSpace: 'nowrap' }}>
            📋 Qué buscar y dónde:
          </span>
          <span>{item.recommended_action}</span>
        </div>
      )}
    </div>
  );
};

export default GapCard;
