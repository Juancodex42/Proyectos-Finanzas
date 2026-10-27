import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles, CheckCircle2, FileText, X, RefreshCw, Wand2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import axios from 'axios';

const PonteAlDiaModal = ({
  isOpen,
  allWarningsList = [],
  onClose,
  apiBase,
  onOpenResolver,
  onRefresh,
  showToast,
  selectedYear
}) => {
  const navigate = useNavigate();
  const [ponteAlDiaStep, setPonteAlDiaStep] = useState(0);
  const [completedChecklistExchanges, setCompletedChecklistExchanges] = useState({});
  const [syncingAllApis, setSyncingAllApis] = useState(false);
  const [inModalUploading, setInModalUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [inModalUploadMsg, setInModalUploadMsg] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setPonteAlDiaStep(0);
      setCompletedChecklistExchanges({});
      setUploadSuccess(false);
      setInModalUploadMsg(null);
    }
  }, [isOpen]);

  const groupedExchanges = allWarningsList.reduce((acc, item) => {
    const ex = item.exchange || 'Otros Exchanges';
    if (!acc[ex]) acc[ex] = [];
    acc[ex].push(item);
    return acc;
  }, {});

  const checklistExchanges = Object.keys(groupedExchanges);
  const filteredSteps = checklistExchanges.filter((ex) => !completedChecklistExchanges[ex]);
  const totalSteps = filteredSteps.length;
  const safeStepIdx = totalSteps > 0 ? Math.min(ponteAlDiaStep, totalSteps - 1) : 0;
  const isFinished = totalSteps === 0;
  const currentExName = !isFinished ? filteredSteps[safeStepIdx] : null;
  const currentExItems = currentExName ? (groupedExchanges[currentExName] || []) : [];

  useEffect(() => {
    if (totalSteps > 0 && ponteAlDiaStep >= totalSteps) {
      setPonteAlDiaStep(totalSteps - 1);
    }
  }, [totalSteps, ponteAlDiaStep]);

  const handleInModalUpload = async (files) => {
    if (!files || files.length === 0) return;
    setInModalUploading(true);
    setUploadSuccess(false);
    setInModalUploadMsg(null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files[]', files[i]);
    }
    if (currentExName && currentExName !== 'Cartera Global') {
      formData.append('override_exchange', currentExName);
    }

    try {
      const uploadRes = await axios.post(`${apiBase}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (uploadRes.data && uploadRes.data.status === 'success') {
        const totalTx = uploadRes.data.total_transactions || 0;
        if (totalTx > 0) {
          setUploadSuccess(true);
          setInModalUploadMsg({
            type: 'success',
            text: `✓ Archivo cargado (${totalTx} operaciones nuevas). Conciliando ${currentExName}...`
          });
          if (showToast) showToast(`Archivo procesado con éxito (${totalTx} operaciones).`, 'success');
          if (onRefresh) onRefresh();
        } else {
          setUploadSuccess(false);
          const warnMsg = uploadRes.data.message || 'El archivo fue leído pero no contenía transacciones nuevas (o ya estaban importadas / en período certificado).';
          setInModalUploadMsg({ type: 'warning', text: `⚠️ ${warnMsg}` });
          if (showToast) showToast(warnMsg, 'warning');
        }
      } else {
        const errMsg = uploadRes.data?.message || 'Error en la subida.';
        setInModalUploadMsg({ type: 'error', text: `⚠️ ${errMsg}` });
      }
    } catch (err) {
      console.error(err);
      const errMsg = err.response?.data?.error || err.response?.data?.message || err.message || 'Error de red';
      setInModalUploadMsg({ type: 'error', text: `⚠️ ${errMsg}` });
    } finally {
      setInModalUploading(false);
    }
  };

  const handleApiSyncForExchange = async (exName) => {
    if (!exName) return;
    if (showToast) showToast(`⚡ Sincronizando API de ${exName}...`, 'info');
    setSyncingAllApis(true);
    try {
      const rawEx = exName.toLowerCase();
      const slug = rawEx.includes('binance') ? 'binance' : rawEx.includes('bitso') ? 'bitso' : rawEx.includes('ripio') ? 'ripio_trade' : rawEx.includes('bitget') ? 'bitget' : rawEx.includes('bybit') ? 'bybit' : rawEx.includes('okx') ? 'okx' : rawEx;
      const res = await axios.post(`${apiBase}/api_sync/${encodeURIComponent(slug)}`);
      if (res.data?.status === 'error') {
        throw new Error(res.data?.errors?.[0] || res.data?.error || 'Error de sincronización');
      }
      if (showToast) showToast(`✓ API de ${exName} sincronizada.`, 'success');
      setCompletedChecklistExchanges((prev) => ({ ...prev, [exName]: true }));
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error(err);
      if (showToast) showToast(err.message || `Error al sincronizar API de ${exName}`, 'error');
    } finally {
      setSyncingAllApis(false);
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
          zIndex: 2600,
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
            maxWidth: '820px',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--accent-amber-border)',
            boxShadow: 'var(--shadow-lg)',
            overflow: 'hidden'
          }}
        >
          {/* Header */}
          <div style={{ padding: '1.25rem 1.75rem', background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#FBBF24' }}>
                <Sparkles size={20} /> Asistente "Ponete al Día" — Checklist por Exchange
              </h3>
              <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                Resolución guiada paso a paso para dejar tu sub-ledger 100% conciliado.
              </p>
            </div>
            <button
              onClick={onClose}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Body */}
          <div style={{ padding: '1.5rem 1.75rem' }}>
            {isFinished ? (
              <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
                <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: 'var(--accent-emerald-subtle)', border: '1px solid var(--accent-emerald-border)', color: '#34D399', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem' }}>
                  <CheckCircle2 size={34} />
                </div>
                <h4 style={{ fontSize: '1.3rem', color: '#F8FAFC', margin: '0 0 0.4rem', fontWeight: 700 }}>
                  ¡Tu Contabilidad está 100% al Día! 🎉
                </h4>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', maxWidth: '520px', margin: '0 auto 1.5rem', lineHeight: 1.5 }}>
                  Completaste el checklist de todos los exchanges. Todos tus movimientos tienen consistencia FIFO y no quedan advertencias pendientes.
                </p>

                <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem' }}>
                  <button onClick={onClose} className="btn-outline">
                    Cerrar Asistente
                  </button>
                  <button
                    onClick={() => {
                      onClose();
                      navigate(selectedYear ? `/reports?year=${selectedYear}` : '/reports');
                    }}
                    className="btn-primary"
                  >
                    <FileText size={16} /> Ir a Descargar Excel Maestro →
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: '1.25rem', alignItems: 'start' }}>
                {/* Steps List */}
                <div style={{ background: '#0D131F', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '0.85rem' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.65rem' }}>
                    Pasos ({safeStepIdx + 1} de {totalSteps})
                  </div>

                  <div style={{ display: 'grid', gap: '0.4rem' }}>
                    {filteredSteps.map((exName, idx) => {
                      const isCurrent = idx === safeStepIdx;
                      const isCompleted = Boolean(completedChecklistExchanges[exName]);
                      const count = (groupedExchanges[exName] || []).length;

                      return (
                        <div
                          key={exName}
                          onClick={() => {
                            setPonteAlDiaStep(idx);
                            setUploadSuccess(false);
                            setInModalUploadMsg(null);
                          }}
                          style={{
                            padding: '0.55rem 0.75rem',
                            borderRadius: 'var(--radius-sm)',
                            background: isCurrent ? 'var(--brand-indigo-subtle)' : isCompleted ? 'rgba(16, 185, 129, 0.08)' : 'transparent',
                            border: isCurrent ? '1px solid var(--brand-indigo-border)' : isCompleted ? '1px solid var(--accent-emerald-border)' : '1px solid transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                            {isCompleted ? (
                              <CheckCircle2 size={14} color="#34D399" />
                            ) : (
                              <span style={{ width: '16px', height: '16px', borderRadius: '50%', background: isCurrent ? 'var(--brand-indigo)' : '#334155', color: '#fff', fontSize: '0.68rem', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                {idx + 1}
                              </span>
                            )}
                            <span style={{ fontSize: '0.82rem', fontWeight: isCurrent ? 700 : 500, color: isCurrent ? 'var(--brand-indigo-light)' : '#F8FAFC' }}>
                              {exName}
                            </span>
                          </div>

                          <span style={{ fontSize: '0.68rem', color: isCompleted ? '#34D399' : 'var(--accent-amber-light)' }}>
                            {isCompleted ? '✓' : count}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Active Step Actions */}
                <div>
                  {(() => {
                    const apiExchangesList = ['binance', 'bitget', 'bitso', 'bybit', 'ripio', 'okx'];
                    const isApiEx = apiExchangesList.some((name) => currentExName.toLowerCase().includes(name));

                    return (
                      <div style={{ background: '#0D131F', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)', padding: '1.15rem', marginBottom: '1rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem' }}>
                          <h4 style={{ margin: 0, fontSize: '1rem', color: isApiEx ? 'var(--brand-indigo-light)' : '#FBBF24', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                            {isApiEx ? '⚡ Exchange con Conexión API' : '📄 Exchange Sin API (Carga CSV / Manual)'}
                          </h4>
                          <span className="badge badge-amber" style={{ fontSize: '0.72rem' }}>
                            {currentExItems.length} advertencia(s)
                          </span>
                        </div>

                        <p style={{ margin: '0 0 1rem 0', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                          {isApiEx
                            ? `${currentExName} cuenta con sincronización API. El sistema puede recuperar compras y depósitos faltantes de forma automática.`
                            : `${currentExName} requiere cargar el extracto CSV/Excel o declarar saldos iniciales.`}
                        </p>

                        <div style={{ display: 'grid', gap: '0.65rem' }}>
                          {isApiEx && (
                            <button
                              disabled={syncingAllApis}
                              onClick={() => handleApiSyncForExchange(currentExName)}
                              className="btn-primary"
                              style={{ width: '100%', fontSize: '0.82rem' }}
                            >
                              <RefreshCw size={14} className={syncingAllApis ? 'spin' : ''} />
                              {syncingAllApis ? 'Sincronizando...' : `⚡ Sincronizar API de ${currentExName}`}
                            </button>
                          )}

                          <div
                            className="upload-zone-refined"
                            style={{ padding: '0.85rem' }}
                            onClick={() => {
                              const inputEl = document.getElementById(`ponteFileInput_${currentExName}`);
                              if (inputEl) inputEl.click();
                            }}
                            onDragOver={(e) => e.preventDefault()}
                            onDrop={(e) => {
                              e.preventDefault();
                              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                                handleInModalUpload(e.dataTransfer.files);
                              }
                            }}
                          >
                            <input
                              type="file"
                              id={`ponteFileInput_${currentExName}`}
                              multiple
                              hidden
                              onChange={(e) => {
                                handleInModalUpload(e.target.files);
                                e.target.value = '';
                              }}
                            />
                            <div style={{ fontSize: '0.82rem', color: '#F8FAFC', fontWeight: 600 }}>
                              📄 Subir Extracto CSV / Excel de {currentExName}
                            </div>
                          </div>

                          {inModalUploading && (
                            <div style={{ textAlign: 'center', color: 'var(--brand-indigo-light)', fontSize: '0.8rem' }}>
                              ⏳ Procesando archivo...
                            </div>
                          )}

                          {inModalUploadMsg && (
                            <div style={{ fontSize: '0.8rem', color: uploadSuccess || inModalUploadMsg.type === 'success' ? '#34D399' : inModalUploadMsg.type === 'warning' ? '#FBBF24' : '#FB7185', textAlign: 'center' }}>
                              {inModalUploadMsg.text}
                            </div>
                          )}

                          {currentExItems[0] && (
                            <button
                              onClick={() => {
                                onClose();
                                if (onOpenResolver) onOpenResolver(currentExItems[0]);
                              }}
                              className="chip active-amber"
                              style={{ justifyContent: 'center', padding: '0.5rem' }}
                            >
                              <Wand2 size={14} /> Ajuste Manual / Saldo Inicial para {currentExName}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })()}

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <button
                      type="button"
                      disabled={safeStepIdx === 0}
                      onClick={() => {
                        setUploadSuccess(false);
                        setInModalUploadMsg(null);
                        setPonteAlDiaStep((prev) => Math.max(0, prev - 1));
                      }}
                      className="btn-outline"
                      style={{ fontSize: '0.78rem', padding: '0.45rem 0.85rem', opacity: safeStepIdx === 0 ? 0.4 : 1 }}
                    >
                      Anterior
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setUploadSuccess(false);
                        setInModalUploadMsg(null);
                        setCompletedChecklistExchanges((prev) => ({ ...prev, [currentExName]: true }));
                        setPonteAlDiaStep((prev) => Math.min(prev, Math.max(0, totalSteps - 2)));
                      }}
                      className="btn-primary"
                      style={{ background: 'linear-gradient(135deg, #10B981, #059669)', fontSize: '0.82rem' }}
                    >
                      Marcar {currentExName} al Día <CheckCircle2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default PonteAlDiaModal;
