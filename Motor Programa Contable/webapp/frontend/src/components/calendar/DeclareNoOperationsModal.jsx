import React, { useState } from 'react';
import { ShieldCheck, CheckCircle2, X, AlertCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const REASON_OPTIONS = [
  { id: 'no_ops', label: 'No operé más en este exchange (cuenta al día / sin movimientos)' },
  { id: 'closed', label: 'Plataforma cerrada permanentemente (ej. Paxful, LocalBitcoins)' },
  { id: 'fiat_only', label: 'Solo transferencias de dinero fiat / pesos ARS (sin compras cripto)' },
  { id: 'other', label: 'Otro motivo (especificar)' }
];

const DeclareNoOperationsModal = ({
  isOpen,
  onClose,
  exchange,
  lastDate,
  apiBase,
  onSuccess
}) => {
  const [selectedReasonId, setSelectedReasonId] = useState('no_ops');
  const [customReason, setCustomReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg(null);

    let finalReason = '';
    let status = 'NO_OPERATIONS';

    if (selectedReasonId === 'closed') {
      finalReason = 'Plataforma cerrada permanentemente';
      status = 'CLOSED';
    } else if (selectedReasonId === 'fiat_only') {
      finalReason = 'Solo movimientos fiat / bancarios (sin trading cripto)';
    } else if (selectedReasonId === 'other') {
      finalReason = customReason.trim() || 'Declarado sin operaciones posteriores';
    } else {
      finalReason = 'Sin operaciones posteriores a la fecha registrada';
    }

    try {
      const baseUrl = (apiBase || '').replace(/\/api\/?$/, '');
      const targetEndpoint = `${baseUrl}/api/audit/declarations`;
      const res = await axios.post(targetEndpoint, {
        exchange,
        status,
        reason: finalReason,
        effective_date: lastDate
      });

      if (res.data && (res.data.success || res.data.status === 'success')) {
        if (onSuccess) onSuccess(exchange);
        onClose();
      } else {
        setErrorMsg(res.data?.error || 'No se pudo guardar la declaración.');
      }
    } catch (err) {
      console.error('Error al guardar declaración de auditoría:', err);
      setErrorMsg(err.response?.data?.error || 'Error de conexión al guardar la declaración.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '1rem'
        }}
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2 }}
          style={{
            background: 'var(--surface-color, #131B2E)',
            border: '1px solid var(--border-color, rgba(255, 255, 255, 0.1))',
            borderRadius: 'var(--radius-lg, 12px)',
            maxWidth: '520px',
            width: '100%',
            overflow: 'hidden',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
            background: 'rgba(16, 185, 129, 0.06)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#34D399',
                padding: '0.45rem',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <ShieldCheck size={20} />
              </div>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC' }}>
                  Declarar Período Sin Operaciones
                </h3>
                <span style={{ fontSize: '0.78rem', color: '#94A3B8' }}>
                  Eximir {exchange} de alertas de atraso
                </span>
              </div>
            </div>
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94A3B8',
                cursor: 'pointer',
                padding: '0.25rem',
                borderRadius: '4px'
              }}
            >
              <X size={18} />
            </button>
          </div>

          {/* Form Content */}
          <form onSubmit={handleSubmit} style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
              borderRadius: '8px',
              padding: '0.9rem 1rem',
              fontSize: '0.82rem',
              color: '#E2E8F0',
              lineHeight: 1.5
            }}>
              Última operación registrada en <strong>{exchange}</strong>: <span style={{ color: '#FBBF24', fontFamily: 'monospace' }}>{lastDate || '-'}</span>.
              <br />
              Al confirmar, el sistema dará por conciliado este período y <strong>no volverá a mostrarte la alerta de extracto desactualizado</strong>.
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, color: '#CBD5E1', marginBottom: '0.6rem', display: 'block' }}>
                Motivo de la declaración:
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {REASON_OPTIONS.map((opt) => (
                  <label
                    key={opt.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.6rem',
                      padding: '0.6rem 0.8rem',
                      borderRadius: '6px',
                      background: selectedReasonId === opt.id ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                      border: selectedReasonId === opt.id ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(255, 255, 255, 0.06)',
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                      color: selectedReasonId === opt.id ? '#F8FAFC' : '#94A3B8',
                      transition: 'all 120ms ease'
                    }}
                  >
                    <input
                      type="radio"
                      name="declare_reason"
                      checked={selectedReasonId === opt.id}
                      onChange={() => setSelectedReasonId(opt.id)}
                      style={{ accentColor: '#10B981' }}
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {selectedReasonId === 'other' && (
              <div>
                <input
                  type="text"
                  placeholder="Detallá el motivo..."
                  value={customReason}
                  onChange={(e) => setCustomReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.6rem 0.8rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-color, rgba(255, 255, 255, 0.15))',
                    background: '#0B1120',
                    color: '#FFF',
                    fontSize: '0.82rem'
                  }}
                />
              </div>
            )}

            {errorMsg && (
              <div style={{
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: '6px',
                padding: '0.6rem 0.8rem',
                fontSize: '0.78rem',
                color: '#FCA5A5',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}>
                <AlertCircle size={15} />
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Footer Buttons */}
            <div style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '0.75rem',
              marginTop: '0.5rem',
              borderTop: '1px solid var(--border-subtle, rgba(255, 255, 255, 0.08))',
              paddingTop: '1rem'
            }}>
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                style={{
                  padding: '0.55rem 1rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color, rgba(255, 255, 255, 0.15))',
                  background: 'transparent',
                  color: '#94A3B8',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={submitting}
                style={{
                  padding: '0.55rem 1.25rem',
                  borderRadius: '6px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #10B981, #059669)',
                  color: '#FFFFFF',
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  cursor: submitting ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  boxShadow: '0 2px 8px rgba(16, 185, 129, 0.35)',
                  opacity: submitting ? 0.7 : 1
                }}
              >
                <CheckCircle2 size={15} />
                {submitting ? 'Guardando...' : 'Confirmar Declaración'}
              </button>
            </div>
          </form>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default DeclareNoOperationsModal;
