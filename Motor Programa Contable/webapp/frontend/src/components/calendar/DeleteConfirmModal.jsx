import React from 'react';
import { Trash2, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const DeleteConfirmModal = ({
  isOpen,
  title = '',
  onClose,
  onConfirm,
  deleting = false
}) => {
  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(9, 13, 20, 0.85)',
          backdropFilter: 'blur(8px)',
          zIndex: 3000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '1.5rem'
        }}
      >
        <motion.div
          initial={{ scale: 0.94, y: 15 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.94, y: 15 }}
          className="card-surface"
          style={{
            width: '100%',
            maxWidth: '440px',
            padding: '1.75rem',
            border: '1px solid var(--accent-rose-border)',
            boxShadow: 'var(--shadow-lg)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem', marginBottom: '1.25rem' }}>
            <div style={{
              background: 'var(--accent-rose-subtle)',
              border: '1px solid var(--accent-rose-border)',
              borderRadius: 'var(--radius-md)',
              padding: '0.65rem',
              color: 'var(--accent-rose-light)',
              flexShrink: 0
            }}>
              <Trash2 size={22} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: '#F8FAFC' }}>
                ¿Eliminar certificación?
              </h3>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                ¿Confirmás la eliminación de <strong style={{ color: '#F8FAFC' }}>"{title}"</strong>?
              </p>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                ⚠️ Al eliminar esta certificación, se removerán las operaciones oficiales asociadas y el período volverá al estado provisorio.
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', marginTop: '1.25rem' }}>
            <button
              type="button"
              disabled={deleting}
              onClick={onClose}
              className="btn-outline"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={onConfirm}
              style={{
                background: 'linear-gradient(135deg, #EF4444, #DC2626)',
                border: 'none',
                color: '#FFFFFF',
                padding: '0.55rem 1.15rem',
                borderRadius: 'var(--radius-md)',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: deleting ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem'
              }}
            >
              {deleting ? (
                <>
                  <RefreshCw size={14} className="spin" /> Eliminando...
                </>
              ) : (
                <>
                  <Trash2 size={14} /> Sí, Eliminar
                </>
              )}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default DeleteConfirmModal;
