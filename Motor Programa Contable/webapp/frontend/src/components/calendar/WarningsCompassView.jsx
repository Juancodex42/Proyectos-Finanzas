import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import GapCard from './GapCard';

const WarningsCompassView = ({
  diagnosticCategories,
  expandedCategories,
  toggleCategoryExpand,
  categoryLimits,
  loadMoreForCategory,
  onResolve
}) => {
  return (
    <div style={{ display: 'grid', gap: '1.25rem' }}>
      {diagnosticCategories.map((catGroup) => {
        if (catGroup.items.length === 0) return null;
        const CatIcon = catGroup.icon;
        const isExpanded = expandedCategories[catGroup.id] !== false;
        const limit = categoryLimits[catGroup.id] || 10;
        const visibleItems = catGroup.items.slice(0, limit);

        return (
          <div
            key={catGroup.id}
            style={{
              border: `1px solid ${catGroup.color}40`,
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              background: 'rgba(13, 19, 31, 0.6)'
            }}
          >
            <div
              onClick={() => toggleCategoryExpand(catGroup.id)}
              style={{
                padding: '0.9rem 1.15rem',
                background: catGroup.bg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: 'pointer',
                userSelect: 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '6px',
                  background: 'rgba(0,0,0,0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: catGroup.color
                }}>
                  <CatIcon size={18} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#F8FAFC' }}>
                      {catGroup.title}
                    </span>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '0.1rem 0.5rem',
                        borderRadius: 'var(--radius-full)',
                        backgroundColor: catGroup.color,
                        color: '#000'
                      }}
                    >
                      {catGroup.items.length}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                    {catGroup.description}
                  </div>
                </div>
              </div>
              <div>
                {isExpanded ? <ChevronUp size={18} color="var(--text-muted)" /> : <ChevronDown size={18} color="var(--text-muted)" />}
              </div>
            </div>

            {isExpanded && (
              <div style={{ padding: '0.85rem', display: 'grid', gap: '0.65rem' }}>
                {visibleItems.map((item, idx) => (
                  <GapCard
                    key={`${catGroup.id}-${item.tx_hash || item.id || item.date}-${idx}`}
                    item={item}
                    idx={idx}
                    keyPrefix={catGroup.id}
                    onResolve={onResolve}
                  />
                ))}

                {catGroup.items.length > limit && (
                  <button
                    type="button"
                    className="btn-outline"
                    onClick={() => loadMoreForCategory(catGroup.id)}
                    style={{ margin: '0.5rem auto 0 auto', fontSize: '0.78rem', padding: '0.35rem 0.85rem' }}
                  >
                    Ver más ({catGroup.items.length - limit} restantes)
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

export default WarningsCompassView;
