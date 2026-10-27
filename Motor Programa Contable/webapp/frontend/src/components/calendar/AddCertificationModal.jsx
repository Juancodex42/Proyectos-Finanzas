import React, { useState, useEffect } from 'react';
import { ShieldCheck, UploadCloud, RefreshCw, CheckCircle2, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import CertQueueItem from './CertQueueItem';
import CertManualForm from './CertManualForm';
import { parseCertificationPdfFile, extractDatesFromFilename } from './certUploadUtils';

const AddCertificationModal = ({
  isOpen,
  onClose,
  apiBase,
  onSuccess,
  initialFormData
}) => {
  const [fileQueue, setFileQueue] = useState([]);
  const [formData, setFormData] = useState({
    title: '',
    start_date: '',
    end_date: '',
    issue_date: new Date().toISOString().split('T')[0],
    cpa_name: '',
    notes: '',
    file: null
  });
  const [submitting, setSubmitting] = useState(false);
  const [autoDetectedMsg, setAutoDetectedMsg] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  const isParsing = fileQueue.some((item) => item.parsing);
  const isDisabled = submitting || isParsing;

  useEffect(() => {
    if (initialFormData) {
      setFormData((prev) => ({
        ...prev,
        ...initialFormData
      }));
    }
  }, [initialFormData]);

  const handleReset = () => {
    setFileQueue([]);
    setFormData({
      title: '',
      start_date: '',
      end_date: '',
      issue_date: new Date().toISOString().split('T')[0],
      cpa_name: '',
      notes: '',
      file: null
    });
    setSubmitting(false);
    setAutoDetectedMsg('');
    setErrorMessage('');
    setSuccessMessage('');
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const parseSingleFile = async (fileItem) => {
    try {
      const parsed = await parseCertificationPdfFile(fileItem, apiBase);
      setFileQueue((prev) => {
        const nextQueue = prev.map((item) => {
          if (item.id === fileItem.id) {
            if (!parsed) return { ...item, parsing: false };
            return {
              ...item,
              title: parsed.title || item.title,
              start_date: parsed.start_date || item.start_date,
              end_date: parsed.end_date || item.end_date,
              full_start_date: parsed.full_start_date || item.full_start_date || '',
              full_end_date: parsed.full_end_date || item.full_end_date || '',
              cpa_name: parsed.cpa_name,
              issue_date: parsed.issue_date || item.issue_date,
              detection_source: parsed.detection_source,
              latest_tx_info: parsed.latest_tx_info,
              detected_transactions_count: parsed.detected_transactions_count,
              provisional_to_replace_count: parsed.provisional_to_replace_count,
              parsing: false,
              parsedSuccess: parsed.parsedSuccess
            };
          }
          return item;
        });

        if (nextQueue.length === 1 && nextQueue[0].id === fileItem.id && parsed) {
          const first = nextQueue[0];
          setFormData((fPrev) => ({
            ...fPrev,
            file: first.file,
            title: first.title,
            start_date: first.start_date,
            end_date: first.end_date,
            cpa_name: first.cpa_name,
            issue_date: first.issue_date
          }));
          if (parsed.full_start_date && parsed.full_end_date) {
            setAutoDetectedMsg(`✨ Período detectado: ${parsed.full_start_date} al ${parsed.full_end_date}`);
          } else if (parsed.start_date && parsed.end_date) {
            setAutoDetectedMsg(`✨ Período detectado: ${parsed.start_date} al ${parsed.end_date}`);
          } else {
            setAutoDetectedMsg('✨ Archivo procesado.');
          }
        }
        return nextQueue;
      });
    } catch (err) {
      console.error('Error in parseSingleFile:', err);
      setFileQueue((prev) =>
        prev.map((item) => (item.id === fileItem.id ? { ...item, parsing: false } : item))
      );
    }
  };

  const handleFilesAdd = (selectedFiles) => {
    if (!selectedFiles || selectedFiles.length === 0) return;
    const newItems = Array.from(selectedFiles).map((file, idx) => {
      const baseName = file.name.replace(/\.[^/.]+$/, '');
      const fnParsed = extractDatesFromFilename(file.name);
      return {
        id: `${Date.now()}-${idx}-${Math.random()}`,
        file,
        filename: file.name,
        title: fnParsed?.title || `Certificación ${baseName}`,
        start_date: fnParsed?.start_date || '',
        end_date: fnParsed?.end_date || '',
        full_start_date: fnParsed?.start_date ? `${fnParsed.start_date} 00:00:00` : '',
        full_end_date: fnParsed?.end_date ? `${fnParsed.end_date} 23:59:59` : '',
        cpa_name: '',
        issue_date: new Date().toISOString().split('T')[0],
        notes: '',
        parsing: true,
        parsedSuccess: !!fnParsed,
        detection_source: fnParsed ? 'Nombre de archivo' : '',
        latest_tx_info: null,
        detected_transactions_count: 0,
        provisional_to_replace_count: 0
      };
    });

    setFileQueue((prev) => [...prev, ...newItems]);
    newItems.forEach((item) => parseSingleFile(item));
  };

  const handleQueueItemChange = (id, field, value) => {
    setFileQueue((prev) =>
      prev.map((item) => {
        if (item.id !== id) return item;
        const updated = { ...item, [field]: value };
        if (field === 'start_date') updated.full_start_date = value;
        if (field === 'end_date') updated.full_end_date = value;
        return updated;
      })
    );
  };

  const handleRemoveQueueItem = (id) => {
    setFileQueue((prev) => {
      const next = prev.filter((item) => item.id !== id);
      if (next.length === 0) {
        setFormData((fPrev) => ({ ...fPrev, file: null }));
        setAutoDetectedMsg('');
      }
      return next;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (isParsing || submitting) return;
    setErrorMessage('');
    setSuccessMessage('');

    if (fileQueue.length > 0) {
      for (let i = 0; i < fileQueue.length; i++) {
        const item = fileQueue[i];
        if (!item.start_date || !item.end_date) {
          setErrorMessage(`Por favor, ingresá la Fecha Inicio y Fecha Fin para "${item.filename}".`);
          return;
        }
        if (new Date(item.start_date) > new Date(item.end_date)) {
          setErrorMessage(`La fecha de inicio debe ser anterior o igual a la de fin para "${item.filename}".`);
          return;
        }
      }

      setSubmitting(true);
      let successCount = 0;
      const remainingStillPending = [];

      try {
        for (let i = 0; i < fileQueue.length; i++) {
          const item = fileQueue[i];
          const payload = new FormData();
          payload.append('title', item.title || `Certificación ${item.filename}`);
          payload.append('start_date', item.full_start_date || item.start_date);
          payload.append('end_date', item.full_end_date || item.end_date);
          if (item.issue_date) payload.append('issue_date', item.issue_date);
          if (item.cpa_name) payload.append('cpa_name', item.cpa_name);
          if (item.notes) payload.append('notes', item.notes);
          if (item.file) payload.append('file', item.file);

          try {
            const res = await fetch(`${apiBase}/certifications`, { method: 'POST', body: payload });
            const result = await res.json();
            if (res.ok && result.success) {
              successCount++;
            } else {
              remainingStillPending.push({ ...item, error: result.error || 'Error al guardar certificación.' });
            }
          } catch {
            remainingStillPending.push({ ...item, error: 'Error de red al guardar este archivo.' });
          }
        }

        setFileQueue(remainingStillPending);

        if (successCount > 0) {
          window.dispatchEvent(new Event('certifications_updated'));
          if (onSuccess) onSuccess();
        }

        if (remainingStillPending.length === 0) {
          setSuccessMessage(`¡${successCount} certificación(es) registrada(s) con éxito!`);
          setTimeout(() => {
            handleReset();
            onClose();
          }, 800);
        } else {
          if (successCount > 0) {
            setSuccessMessage(`Se registraron ${successCount} certificación(es) correctamente.`);
          }
          const firstErr = remainingStillPending[0]?.error || 'Error al registrar las certificaciones.';
          setErrorMessage(`Quedaron ${remainingStillPending.length} certificación(es) pendientes: ${firstErr}`);
        }
      } catch (err) {
        console.error(err);
        setErrorMessage('Error de red al guardar las certificaciones.');
      } finally {
        setSubmitting(false);
      }
      return;
    }

    // Manual single entry
    if (!formData.start_date || !formData.end_date) {
      setErrorMessage('Por favor, ingresá las fechas de inicio y fin de la certificación.');
      return;
    }
    if (new Date(formData.start_date) > new Date(formData.end_date)) {
      setErrorMessage('La fecha de inicio debe ser anterior o igual a la fecha de fin.');
      return;
    }

    setSubmitting(true);
    try {
      const payload = new FormData();
      payload.append('title', formData.title || 'Certificación Contable');
      payload.append('start_date', formData.start_date);
      payload.append('end_date', formData.end_date);
      if (formData.issue_date) payload.append('issue_date', formData.issue_date);
      if (formData.cpa_name) payload.append('cpa_name', formData.cpa_name);
      if (formData.notes) payload.append('notes', formData.notes);
      if (formData.file) payload.append('file', formData.file);

      const res = await fetch(`${apiBase}/certifications`, { method: 'POST', body: payload });
      const result = await res.json();
      if (res.ok && result.success) {
        setSuccessMessage('¡Certificación registrada con éxito!');
        window.dispatchEvent(new Event('certifications_updated'));
        if (onSuccess) onSuccess();
        setTimeout(() => {
          handleReset();
          onClose();
        }, 800);
      } else {
        setErrorMessage(result.error || 'Error al guardar la certificación.');
      }
    } catch (err) {
      console.error(err);
      setErrorMessage('Error de conexión con el servidor.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(9, 13, 20, 0.85)', backdropFilter: 'blur(8px)', zIndex: 2000,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem'
        }}
      >
        <motion.div
          initial={{ scale: 0.94, y: 15 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.94, y: 15 }}
          className="card-surface"
          style={{
            width: '100%', maxWidth: fileQueue.length > 0 ? '780px' : '620px',
            maxHeight: '90vh', overflowY: 'auto', padding: '2rem',
            border: '1px solid var(--border-strong)', boxShadow: 'var(--shadow-lg)'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ShieldCheck size={22} color="var(--brand-indigo-light)" />
                Registrar Certificaciones Contables
              </h3>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                Podés seleccionar uno o varios archivos PDF para procesar por lote.
              </p>
            </div>
            <button
              onClick={() => { handleReset(); onClose(); }}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>
          </div>

          {errorMessage && (
            <div style={{ background: 'var(--accent-rose-subtle)', border: '1px solid var(--accent-rose-border)', borderRadius: 'var(--radius-sm)', padding: '0.75rem', marginBottom: '1.25rem', color: 'var(--accent-rose-light)', fontSize: '0.85rem' }}>
              {errorMessage}
            </div>
          )}

          {successMessage && (
            <div style={{ background: 'var(--accent-emerald-subtle)', border: '1px solid var(--accent-emerald-border)', borderRadius: 'var(--radius-sm)', padding: '0.75rem', marginBottom: '1.25rem', color: 'var(--accent-emerald-light)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle2 size={18} /> {successMessage}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Upload Zone */}
            <div style={{ marginBottom: '1.5rem' }}>
              <div
                className={`upload-zone-refined ${isDragging ? 'dragging' : ''}`}
                style={{ padding: '1.5rem', textAlign: 'center', cursor: 'pointer' }}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (e.dataTransfer.files) handleFilesAdd(e.dataTransfer.files);
                }}
                onClick={() => document.getElementById('certMultiFileInput').click()}
              >
                <input
                  id="certMultiFileInput"
                  type="file"
                  accept=".pdf"
                  multiple
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    handleFilesAdd(e.target.files);
                    e.target.value = '';
                  }}
                />
                <UploadCloud size={36} color="var(--brand-indigo-light)" style={{ margin: '0 auto 0.5rem' }} />
                <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                  Arrastrá aquí tus certificaciones contables en PDF o hacé click para explorar
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                  Soporta selección de múltiples archivos PDF simultáneos
                </div>
              </div>
            </div>

            {/* Multiple files queue list */}
            {fileQueue.length > 0 ? (
              <div style={{ display: 'grid', gap: '1rem', marginBottom: '1.5rem', maxHeight: '420px', overflowY: 'auto', paddingRight: '0.3rem' }}>
                {fileQueue.map((item, qIdx) => (
                  <CertQueueItem
                    key={item.id}
                    item={item}
                    qIdx={qIdx}
                    onQueueItemChange={handleQueueItemChange}
                    onRemoveQueueItem={handleRemoveQueueItem}
                  />
                ))}
              </div>
            ) : (
              /* Single Manual Entry Form */
              <CertManualForm
                formData={formData}
                onInputChange={handleInputChange}
                autoDetectedMsg={autoDetectedMsg}
              />
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
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
                disabled={isDisabled}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  opacity: isDisabled ? 0.6 : 1,
                  cursor: isDisabled ? 'not-allowed' : 'pointer',
                  transition: 'opacity 0.2s ease'
                }}
              >
                {isParsing ? (
                  <>
                    <RefreshCw size={15} className="spin" /> Cargando...
                  </>
                ) : submitting ? (
                  <>
                    <RefreshCw size={15} className="spin" /> Guardando...
                  </>
                ) : (
                  <>
                    <ShieldCheck size={15} />
                    {fileQueue.length > 1
                      ? `Guardar ${fileQueue.length} Certificaciones`
                      : 'Guardar Certificación'}
                  </>
                )}
              </button>
            </div>
          </form>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default AddCertificationModal;
