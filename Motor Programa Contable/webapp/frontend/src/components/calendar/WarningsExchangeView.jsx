import React from 'react';
import { ChevronDown, ChevronUp, Wand2 } from 'lucide-react';
import GapCard from './GapCard';

const WarningsExchangeView = ({
  exchangeNames = [],
  groupedExchanges = {},
  filteredNames = [],
  selectedExchangeFilter,
  setSelectedExchangeFilter,
  expandedExchanges,
  toggleExchangeExpand,
  exchangeLimits,
  loadMoreForExchange,
  onResolve
}) => {
  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Filtrar Exchange:</span>
        <select
          value={selectedExchangeFilter}
          onChange={(e) => setSelectedExchangeFilter(e.target.value)}
          className="input-field"
          style={{ width: 'auto', padding: '0.35rem 0.65rem', fontSize: '0.82rem' }}
        >
          <option value="ALL">Todos los Exchanges ({exchangeNames.length})</option>
          {exchangeNames.map((name) => (
            <option key={name} value={name}>
              {name} ({groupedExchanges[name]?.length || 0})
            </option>
          ))}
        </select>
      </div>

      {filteredNames.map((exName) => {
        const items = groupedExchanges[exName] || [];
        const isExpanded = expandedExchanges[exName] !== false;
        const limit = exchangeLimits[exName] || 10;
        const visibleItems = items.slice(0, limit);

        return (
          <div
            key={exName}
            style={{
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              background: '#0D131F'
            }}
          >
            <div
              onClick={() => toggleExchangeExpand(exName)}
              style={{
                padding: '0.75rem 1rem',
                background: 'rgba(255, 255, 255, 0.02)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <span className="badge badge-slate" style={{ fontSize: '0.82rem', fontWeight: 700 }}>
                  {exName}
                </span>
                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  {items.length} operación(es) con déficit
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                <button
                  className="btn-primary"
                  style={{
                    background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                    border: 'none',
                    padding: '0.25rem 0.65rem',
                    fontSize: '0.74rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.3rem'
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (items[0] && onResolve) onResolve(items[0]);
                  }}
                >
                  <Wand2 size={12} /> Resolver primer lote
                </button>
                {isExpanded ? <ChevronUp size={16} color="var(--text-muted)" /> : <ChevronDown size={16} color="var(--text-muted)" />}
              </div>
            </div>

            {isExpanded && (
              <div style={{ padding: '0.75rem', display: 'grid', gap: '0.65rem' }}>
                {visibleItems.map((item, i) => (
                  <GapCard
                    key={`${item.tx_hash || item.id || item.date}-${i}`}
                    item={item}
                    idx={i}
                    keyPrefix={exName}
                    onResolve={onResolve}
                  />
                ))}

                {items.length > limit && (
                  <button
                    type="button"
                    className="btn-outline"
                    onClick={() => loadMoreForExchange(exName)}
                    style={{ margin: '0.4rem auto 0 auto', fontSize: '0.78rem', padding: '0.35rem 0.85rem' }}
                  >
                    Ver más ({items.length - limit} restantes)
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default WarningsExchangeView;
