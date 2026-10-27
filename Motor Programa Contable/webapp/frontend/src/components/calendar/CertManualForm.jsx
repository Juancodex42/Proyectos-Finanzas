import React from 'react';
import { Sparkles } from 'lucide-react';

const CertManualForm = ({
  formData,
  onInputChange,
  autoDetectedMsg
}) => {
  return (
    <div style={{ display: 'grid', gap: '0.85rem', marginBottom: '1.5rem' }}>
      {autoDetectedMsg && (
        <div style={{
          background: 'rgba(79, 70, 229, 0.12)',
          border: '1px solid rgba(79, 70, 229, 0.3)',
          borderRadius: 'var(--radius-md)',
          padding: '0.65rem 0.85rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.8rem',
          color: 'var(--brand-indigo-light)',
          fontWeight: 600
        }}>
          <Sparkles size={14} style={{ flexShrink: 0 }} />
          <span>{autoDetectedMsg}</span>
        </div>
      )}

      <div>
        <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
          Título / Descripción
        </label>
        <input
          type="text"
          name="title"
          value={formData.title}
          onChange={onInputChange}
          placeholder="Ej: Certificación Contable Anual 2024"
          className="input-field"
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
            Fecha Inicio (Desde) *
          </label>
          <input
            type="date"
            name="start_date"
            value={formData.start_date}
            onChange={onInputChange}
            className="input-field"
            required
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
            Fecha Fin (Hasta) *
          </label>
          <input
            type="date"
            name="end_date"
            value={formData.end_date}
            onChange={onInputChange}
            className="input-field"
            required
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.85rem' }}>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
            Fecha de Emisión
          </label>
          <input
            type="date"
            name="issue_date"
            value={formData.issue_date}
            onChange={onInputChange}
            className="input-field"
          />
        </div>
        <div>
          <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
            Contador Emisor / Matrícula
          </label>
          <input
            type="text"
            name="cpa_name"
            value={formData.cpa_name}
            onChange={onInputChange}
            placeholder="Ej: CPN Carlos Gómez (Mat. 1234)"
            className="input-field"
          />
        </div>
      </div>

      <div>
        <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
          Observaciones / Notas
        </label>
        <textarea
          name="notes"
          value={formData.notes}
          onChange={onInputChange}
          rows="2"
          placeholder="Notas sobre el alcance del informe o legalización..."
          className="input-field"
        />
      </div>
    </div>
  );
};

export default CertManualForm;
