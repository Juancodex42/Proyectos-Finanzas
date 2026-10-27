import React, { useState } from 'react';
import {
  UploadCloud, RefreshCw, CheckCircle2, AlertTriangle, X,
  Database, ShieldCheck, ArrowRight, FileText
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const ReplacePeriodModal = ({
  isOpen,
  onClose,
  apiBase,
  onSuccess,
  showToast
}) => {
  const [step, setStep] = useState(1); // 1: upload, 2: preview & warning, 3: submitting
  const [file, setFile] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [previewData, setPreviewData] = useState(null);
  const [confirmedCheckbox, setConfirmedCheckbox] = useState(false);

  // Form override fields
  const [formFields, setFormFields] = useState({
    title: '',
    start_date: '',
    end_date: '',
    cpa_name: '',
    issue_date: new Date().toISOString().split('T')[0],
    notes: ''
  });

  const handleReset = () => {
    setStep(1);
    setFile(null);
    setLoadingPreview(false);
    setSubmitting(false);
    setErrorMsg('');
    setPreviewData(null);
    setConfirmedCheckbox(false);
    setFormFields({
      title: '',
      start_date: '',
      end_date: '',
      cpa_name: '',
      issue_date: new Date().toISOString().split('T')[0],
      notes: ''
    });
  };

  const handleFileSelect = async (selectedFile) => {
    if (!selectedFile) return;
    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setErrorMsg('El archivo debe ser un documento PDF del dictamen contable.');
      return;
    }

    setFile(selectedFile);
    setErrorMsg('');
    setLoadingPreview(true);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('filename', selectedFile.name);

      const res = await axios.post(`${apiBase}/certifications/preview_pdf`, formData);
      if (res.data && res.data.success) {
        const data = res.data;
        setPreviewData(data);
        const cpa = data.cpa_info || {};
        setFormFields({
          title: cpa.title || `Certificación y Anexo ${selectedFile.name.replace('.pdf', '')}`,
          start_date: cpa.start_date || '',
          end_date: cpa.end_date || '',
          cpa_name: cpa.cpa_name || '',
          issue_date: cpa.issue_date || new Date().toISOString().split('T')[0],
          notes: `Reemplazo oficial con ${data.transactions_count || 0} operaciones auditadas.`
        });
        setStep(2);
      } else {
        setErrorMsg(res.data?.error || 'No se pudieron extraer las transacciones del anexo.');
      }
    } catch (err) {
      console.error('Error previewing PDF:', err);
      const msg = err.response?.data?.error || err.message || 'Error de conexión al analizar el PDF.';
      setErrorMsg(msg);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleConfirmReplace = async (e) => {
    e.preventDefault();
    if (!confirmedCheckbox) {
      setErrorMsg('Debes tildar la casilla de confirmación para proceder con el reemplazo.');
      return;
    }
    if (!formFields.start_date || !formFields.end_date) {
      setErrorMsg('Las fechas de inicio y fin son obligatorias.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');

    try {
      const payload = new FormData();
      payload.append('file', file);
      payload.append('title', formFields.title || 'Dictamen Oficial y Reemplazo');
      payload.append('start_date', formFields.start_date);
      payload.append('end_date', formFields.end_date);
      if (formFields.issue_date) payload.append('issue_date', formFields.issue_date);
      if (formFields.cpa_name) payload.append('cpa_name', formFields.cpa_name);
      if (formFields.notes) payload.append('notes', formFields.notes);

      const res = await axios.post(`${apiBase}/certifications`, payload);
      if (res.data && res.data.success) {
        if (showToast) {
          showToast(
            `¡Reemplazo exitoso! Se aplicó el anexo oficial con ${previewData?.transactions_count || 0} transacciones auditadas.`,
            'success'
          );
        }
        window.dispatchEvent(new Event('certifications_updated'));
        if (onSuccess) onSuccess();
        handleReset();
        onClose();
      } else {
        setErrorMsg(res.data?.error || 'Error al guardar la certificación de reemplazo.');
      }
    } catch (err) {
      console.error('Error submitting replacement:', err);
      setErrorMsg(err.response?.data?.error || err.message || 'Error al ejecutar el reemplazo.');
    } finally {
      setSubmitting(false);
    }
  };

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
          zIndex: 2500,
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
            maxWidth: step === 2 ? '860px' : '560px',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '1.75rem',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            boxShadow: 'var(--shadow-lg)'
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#60A5FA', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Database size={22} />
              Reemplazo Oficial de Transacciones con Dictamen CPA
            </h3>
            <button
              onClick={() => { handleReset(); onClose(); }}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={18} />
            </button>
          </div>

          {errorMsg && (
            <div style={{ background: 'var(--accent-rose-subtle)', border: '1px solid var(--accent-rose-border)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', marginBottom: '1rem', color: 'var(--accent-rose-light)', fontSize: '0.82rem' }}>
              {errorMsg}
            </div>
          )}

          {step === 1 && (
            <div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '1rem' }}>
                Este asistente extrae automáticamente las tablas de operaciones del Anexo de tu Certificación Contable en PDF y reemplaza los movimientos provisorios del período por las transacciones oficiales certificadas.
              </p>

              <div
                className="upload-zone-refined"
                style={{ padding: '2rem 1.5rem', textAlign: 'center', cursor: 'pointer' }}
                onClick={() => document.getElementById('replacePdfFileInput').click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                    handleFileSelect(e.dataTransfer.files[0]);
                  }
                }}
              >
                <input
                  id="replacePdfFileInput"
                  type="file"
                  accept=".pdf"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      handleFileSelect(e.target.files[0]);
                    }
                    e.target.value = '';
                  }}
                />
                {loadingPreview ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', color: 'var(--brand-indigo-light)' }}>
                    <RefreshCw size={32} className="spin" />
                    <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Extrayendo tablas del Anexo del PDF...</span>
                  </div>
                ) : (
                  <div>
                    <UploadCloud size={38} color="var(--brand-indigo-light)" style={{ margin: '0 auto 0.5rem' }} />
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#F8FAFC' }}>
                      Arrastrá o seleccioná el PDF del Dictamen Contable
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      Debe contener tablas vectoriales de operaciones certificadas
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {step === 2 && previewData && (
            <form onSubmit={handleConfirmReplace}>
              {/* Summary Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.85rem', marginBottom: '1.25rem' }}>
                <div style={{ background: 'rgba(59, 130, 246, 0.12)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: 'var(--radius-sm)', padding: '0.75rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Operaciones en Anexo</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#60A5FA' }}>
                    {previewData.transactions_count || 0}
                  </div>
                </div>

                <div style={{ background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: 'var(--radius-sm)', padding: '0.75rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Provisorias a Reemplazar</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 800, color: '#FBBF24' }}>
                    {previewData.provisional_to_replace_count || 0}
                  </div>
                </div>

                <div style={{ background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: 'var(--radius-sm)', padding: '0.75rem' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Período Detectado</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.35rem', flexWrap: 'wrap' }}>
                    <input
                      type="date"
                      value={formFields.start_date ? formFields.start_date.slice(0, 10) : ''}
                      onChange={(e) => setFormFields((prev) => ({ ...prev, start_date: e.target.value }))}
                      style={{
                        background: '#0D131F',
                        border: '1px solid rgba(16, 185, 129, 0.4)',
                        borderRadius: '4px',
                        color: '#34D399',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        padding: '0.2rem 0.4rem'
                      }}
                    />
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>→</span>
                    <input
                      type="date"
                      value={formFields.end_date ? formFields.end_date.slice(0, 10) : ''}
                      onChange={(e) => setFormFields((prev) => ({ ...prev, end_date: e.target.value }))}
                      style={{
                        background: '#0D131F',
                        border: '1px solid rgba(16, 185, 129, 0.4)',
                        borderRadius: '4px',
                        color: '#34D399',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        padding: '0.2rem 0.4rem'
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Warning Callout */}
              <div style={{
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.35)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.85rem',
                marginBottom: '1.25rem',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.65rem'
              }}>
                <AlertTriangle size={18} color="#EF4444" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ fontSize: '0.8rem', color: '#FCA5A5', lineHeight: 1.45 }}>
                  <strong>Aviso de Reemplazo Atómico:</strong> Las operaciones provisorias existentes dentro del rango seleccionado ({formFields.start_date} al {formFields.end_date}) serán eliminadas e invalidadas para evitar duplicaciones con las transacciones certificadas del dictamen.
                </div>
              </div>

              {/* Preview Table of First 50 */}
              {previewData.transactions_preview && previewData.transactions_preview.length > 0 && (
                <div style={{ marginBottom: '1.25rem' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-secondary)', marginBottom: '0.4rem' }}>
                    Vista Previa del Anexo ({previewData.transactions_preview.length} de {previewData.transactions_count} operaciones):
                  </div>
                  <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
                    <table className="table-ledger" style={{ fontSize: '0.75rem' }}>
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Exchange</th>
                          <th>Tipo</th>
                          <th>Moneda</th>
                          <th>Monto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.transactions_preview.map((tx, idx) => (
                          <tr key={idx}>
                            <td className="font-mono">{tx.Fecha || tx.fecha}</td>
                            <td>{tx.Exchange || tx.exchange}</td>
                            <td>{tx['Tipo de Operación'] || tx.tipo}</td>
                            <td className="font-mono">{tx.Moneda || tx.moneda}</td>
                            <td className="font-mono">{tx.Cantidad || tx.monto || tx.Monto || '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Checkbox Confirmation */}
              <div style={{ background: '#0D131F', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', marginBottom: '1.25rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', cursor: 'pointer', fontSize: '0.82rem', color: '#F8FAFC' }}>
                  <input
                    type="checkbox"
                    checked={confirmedCheckbox}
                    onChange={(e) => setConfirmedCheckbox(e.target.checked)}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <span>
                    Confirmo que deseo reemplazar las operaciones provisorias con las transacciones del Anexo Oficial CPA.
                  </span>
                </label>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="btn-outline"
                  disabled={submitting}
                >
                  ← Cambiar Archivo
                </button>
                <div style={{ display: 'flex', gap: '0.65rem' }}>
                  <button
                    type="button"
                    onClick={() => { handleReset(); onClose(); }}
                    className="btn-outline"
                    disabled={submitting}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={submitting || !confirmedCheckbox}
                    style={{
                      background: 'linear-gradient(135deg, #2563EB, #1D4ED8)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      opacity: (!confirmedCheckbox || submitting) ? 0.6 : 1
                    }}
                  >
                    {submitting ? (
                      <>
                        <RefreshCw size={14} className="spin" /> Reemplazando transacciones...
                      </>
                    ) : (
                      <>
                        <ShieldCheck size={14} /> Confirmar Reemplazo Oficial
                      </>
                    )}
                  </button>
                </div>
              </div>
            </form>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default ReplacePeriodModal;
