import React from 'react';
import { CheckCircle2, AlertTriangle, Sparkles, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const CalendarToast = ({ toast, onClose }) => {
  return (
    <AnimatePresence>
      {toast?.show && (
        <motion.div
          initial={{ opacity: 0, y: -20, scale: 0.92 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.92 }}
          style={{
            position: 'fixed',
            top: '1.25rem',
            right: '1.25rem',
            zIndex: 9999,
            background: toast.type === 'success' ? '#059669' : toast.type === 'error' ? '#DC2626' : toast.type === 'warning' ? '#D97706' : '#4F46E5',
            color: '#FFFFFF',
            padding: '0.75rem 1.25rem',
            borderRadius: 'var(--radius-md)',
            boxShadow: 'var(--shadow-lg)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            fontSize: '0.85rem',
            fontWeight: 600
          }}
        >
          {toast.type === 'success' && <CheckCircle2 size={18} />}
          {toast.type === 'error' && <AlertTriangle size={18} />}
          {toast.type === 'warning' && <AlertTriangle size={18} />}
          {toast.type === 'info' && <Sparkles size={18} />}
          <span>{toast.message}</span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', opacity: 0.8, marginLeft: '0.35rem' }}
          >
            <X size={14} />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CalendarToast;
