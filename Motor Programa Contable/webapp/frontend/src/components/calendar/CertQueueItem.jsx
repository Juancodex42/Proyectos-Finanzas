import React from 'react';
import { RefreshCw, Trash2, Database } from 'lucide-react';

const CertQueueItem = ({
  item,
  qIdx,
  onQueueItemChange,
  onRemoveQueueItem
}) => {
  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.7)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md)',
        padding: '1rem',
        display: 'grid',
        gap: '0.75rem'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#F8FAFC', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            #{qIdx + 1}: {item.filename}
          </span>
          {item.parsing ? (
            <span style={{ fontSize: '0.72rem', color: 'var(--brand-indigo-light)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <RefreshCw size={12} className="spin" /> Detectando datos...
            </span>
          ) : item.parsedSuccess ? (
            <span className="badge badge-emerald" style={{ fontSize: '0.68rem' }}>
              Auto-detectado
            </span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => onRemoveQueueItem(item.id)}
          style={{ background: 'none', border: 'none', color: '#EF4444', cursor: 'pointer', padding: '0.2rem' }}
          title="Quitar de la lista"
        >
          <Trash2 size={15} />
        </button>
      </div>

      {item.detected_transactions_count > 0 && (
        <div style={{
          background: 'rgba(59, 130, 246, 0.12)',
          border: '1px solid rgba(59, 130, 246, 0.35)',
          borderRadius: 'var(--radius-sm)',
          padding: '0.45rem 0.65rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '0.5rem',
          fontSize: '0.78rem',
          color: '#60A5FA'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <Database size={13} style={{ flexShrink: 0 }} />
            <span>Tablas del Anexo: <strong>{item.detected_transactions_count} operaciones oficiales</strong> detectadas.</span>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.65rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
            Título / Objeto del Dictamen
          </label>
          <input
            type="text"
            value={item.title}
            onChange={(e) => onQueueItemChange(item.id, 'title', e.target.value)}
            className="input-field"
            placeholder="Ej: Certificación Contable Anual 2024"
            style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
              Fecha Inicio (Desde) *
            </label>
            <input
              type="date"
              value={item.start_date}
              onChange={(e) => onQueueItemChange(item.id, 'start_date', e.target.value)}
              className="input-field"
              style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
              required
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
              Fecha Fin (Hasta) *
            </label>
            <input
              type="date"
              value={item.end_date}
              onChange={(e) => onQueueItemChange(item.id, 'end_date', e.target.value)}
              className="input-field"
              style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
              required
            />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
              Contador Emisor / Matrícula
            </label>
            <input
              type="text"
              value={item.cpa_name || ''}
              onChange={(e) => onQueueItemChange(item.id, 'cpa_name', e.target.value)}
              placeholder="Ej: C.P.N. Auditor de Muestra (M.P. 0001)"
              className="input-field"
              style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
              Fecha de Emisión
            </label>
            <input
              type="date"
              value={item.issue_date || ''}
              onChange={(e) => onQueueItemChange(item.id, 'issue_date', e.target.value)}
              className="input-field"
              style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
            />
          </div>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.2rem' }}>
            Notas / Observaciones del Dictamen
          </label>
          <input
            type="text"
            value={item.notes || ''}
            onChange={(e) => onQueueItemChange(item.id, 'notes', e.target.value)}
            placeholder="Observaciones de auditoría o resolución colegiada..."
            className="input-field"
            style={{ padding: '0.45rem 0.65rem', fontSize: '0.82rem' }}
          />
        </div>
      </div>
    </div>
  );
};

export default CertQueueItem;
