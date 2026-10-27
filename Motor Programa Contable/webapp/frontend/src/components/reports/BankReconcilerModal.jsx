import React, { useState, useEffect } from 'react';
import { X, Upload, CheckCircle2, AlertCircle, Settings, RefreshCw, Save } from 'lucide-react';
import axios from 'axios';
import config from '../../config';

const CATEGORY_OPTIONS = [
    { value: 'P2P_MATCHED', label: 'P2P Conciliado (Neutro en Banco)', color: '#10b981' },
    { value: 'PASE_PROPIO', label: 'Pase Propio entre Cuentas Operativas (Neutro)', color: '#38bdf8' },
    { value: 'RETIRO', label: 'Retiro a Cuenta Personal Externa (-Caja / -Capital)', color: '#f59e0b' },
    { value: 'INYECCION', label: 'Inyección desde Cuenta Personal (+Caja / +Capital)', color: '#8b5cf6' },
    { value: 'GASTO_ARBITRAJE', label: 'Gasto / Impuesto Bancario Arbitraje (Deducible)', color: '#ec4899' },
    { value: 'GASTO_PERSONAL', label: 'Gasto Común / Consumo Personal (Retiro)', color: '#fb923c' },
    { value: 'PRESTAMO', label: 'Préstamo de Tercero Recibido (+Caja / +Capital)', color: '#6366f1' },
    { value: 'DEVOLUCION_PRESTAMO', label: 'Devolución Préstamo (-Caja / -Capital)', color: '#94a3b8' },
    { value: 'RENDIMIENTO', label: 'Rendimiento FCI / Intereses (+Caja)', color: '#2dd4bf' },
    { value: 'PENDIENTE', label: 'Pendiente de Revisión', color: '#ef4444' }
];

export default function BankReconcilerModal({ show, onClose, dateRange, onUpdated }) {
    const [activeTab, setActiveTab] = useState('movements');
    const [movements, setMovements] = useState([]);
    const [filterCat, setFilterCat] = useState('ALL');
    const [showAllRows, setShowAllRows] = useState(false);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [savingSettings, setSavingSettings] = useState(false);
    const [uploadSummary, setUploadSummary] = useState(null);

    const [settingsForm, setSettingsForm] = useState({
        owner_names: '',
        owner_cuits: '',
        operational_accounts: '',
        personal_external_accounts: '',
        personal_expense_threshold_ars: 0
    });

    const fetchMovementsAndSettings = async () => {
        setLoading(true);
        try {
            const [movRes, setRes] = await Promise.all([
                axios.get(`${config.API_URL}/api/bank/movements`, {
                    params: { dateStart: dateRange?.start || '', dateEnd: dateRange?.end || '' }
                }),
                axios.get(`${config.API_URL}/api/bank/settings`)
            ]);
            setMovements(movRes.data?.movements || []);
            const s = setRes.data?.settings;
            if (s) {
                setSettingsForm({
                    owner_names: (s.owner_names || []).join(', '),
                    owner_cuits: (s.owner_cuits || []).join(', '),
                    operational_accounts: (s.operational_accounts || []).join(', '),
                    personal_external_accounts: (s.personal_external_accounts || []).join(', '),
                    personal_expense_threshold_ars: s.personal_expense_threshold_ars ?? 25000
                });
            }
        } catch (err) {
            console.error('Error loading bank movements/settings:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (show) {
            setShowAllRows(false);
            fetchMovementsAndSettings();
        }
    }, [show, dateRange?.start, dateRange?.end]);

    if (!show) return null;

    const handleBankUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploading(true);
        setUploadSummary(null);
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await axios.post(`${config.API_URL}/api/bank/upload`, formData);
            if (res.data?.success) {
                setUploadSummary(res.data.summary);
                await fetchMovementsAndSettings();
                if (onUpdated) onUpdated();
            } else {
                alert(res.data?.error || 'Error al procesar extracto bancario.');
            }
        } catch (err) {
            alert(err.response?.data?.error || 'Error al subir el extracto bancario.');
        } finally {
            setUploading(false);
            e.target.value = '';
        }
    };

    const handleCategoryChange = async (txHash, newCategory) => {
        try {
            await axios.post(`${config.API_URL}/api/bank/classify`, {
                tx_hash: txHash,
                categoria: newCategory
            });
            setMovements(prev => prev.map(m => m.tx_hash === txHash ? { ...m, categoria: newCategory } : m));
            if (onUpdated) onUpdated();
        } catch (err) {
            alert('No se pudo actualizar la clasificación del movimiento.');
        }
    };

    const handleSaveSettings = async () => {
        setSavingSettings(true);
        try {
            const payload = {
                owner_names: settingsForm.owner_names.split(',').map(s => s.trim()).filter(Boolean),
                owner_cuits: settingsForm.owner_cuits.split(',').map(s => s.trim()).filter(Boolean),
                operational_accounts: settingsForm.operational_accounts.split(',').map(s => s.trim()).filter(Boolean),
                personal_external_accounts: settingsForm.personal_external_accounts.split(',').map(s => s.trim()).filter(Boolean),
                personal_expense_threshold_ars: parseFloat(settingsForm.personal_expense_threshold_ars) || 25000
            };
            await axios.post(`${config.API_URL}/api/bank/settings`, payload);
            if (onUpdated) onUpdated();
            alert('Configuración de cuentas operativas y personales guardada.');
        } catch (err) {
            alert('Error al guardar la configuración.');
        } finally {
            setSavingSettings(false);
        }
    };

    const filteredMovements = filterCat === 'ALL'
        ? movements
        : movements.filter(m => m.categoria === filterCat);

    const visibleMovements = showAllRows ? filteredMovements : filteredMovements.slice(0, 150);

    return (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(2, 6, 23, 0.82)', backdropFilter: 'blur(6px)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem' }}>
            <div className="glass-card" style={{ width: '100%', maxWidth: '1050px', maxHeight: '88vh', display: 'flex', flexDirection: 'column', borderRadius: '1rem', border: '1px solid rgba(56, 189, 248, 0.25)', background: '#0f172a', overflow: 'hidden' }}>
                <div style={{ padding: '1.1rem 1.5rem', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '1.15rem', color: '#f8fafc', fontWeight: 700 }}>
                            Conciliador de Extractos Bancarios y Cuentas Propias
                        </h3>
                        <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', color: '#94a3b8' }}>
                            Distingue Pases Operativos, Retiros/Inyecciones a tu cuenta personal, Gastos de Arbitraje (Ley 25.413/SIRCREB) y Gastos Comunes.
                        </p>
                    </div>
                    <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                        <X size={22} />
                    </button>
                </div>

                <div style={{ padding: '0.75rem 1.5rem', background: 'rgba(15, 23, 42, 0.9)', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                            onClick={() => setActiveTab('movements')}
                            style={{ padding: '0.45rem 0.9rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, background: activeTab === 'movements' ? 'var(--accent-cyan)' : 'rgba(30,41,59,0.7)', color: activeTab === 'movements' ? '#0f172a' : '#cbd5e1' }}
                        >
                            Movimientos Conciliados ({movements.length})
                        </button>
                        <button
                            onClick={() => setActiveTab('settings')}
                            style={{ padding: '0.45rem 0.9rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.35rem', background: activeTab === 'settings' ? 'var(--accent-cyan)' : 'rgba(30,41,59,0.7)', color: activeTab === 'settings' ? '#0f172a' : '#cbd5e1' }}
                        >
                            <Settings size={14} /> Reglas de Cuentas Propias y Gastos
                        </button>
                    </div>

                    <label style={{ background: '#0284c7', color: '#fff', padding: '0.45rem 0.95rem', borderRadius: '0.5rem', fontSize: '0.82rem', fontWeight: 600, cursor: uploading ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        {uploading ? <RefreshCw size={15} className="spin" /> : <Upload size={15} />}
                        {uploading ? 'Procesando Extracto...' : 'Subir Extracto (MP / Lemon / Banco)'}
                        <input type="file" accept=".csv,.xlsx,.xls" onChange={handleBankUpload} style={{ display: 'none' }} disabled={uploading} />
                    </label>
                </div>

                {uploadSummary && (
                    <div style={{ margin: '0.75rem 1.5rem 0', padding: '0.65rem 1rem', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.35)', borderRadius: '0.5rem', fontSize: '0.8rem', color: '#a7f3d0', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <CheckCircle2 size={16} color="#10b981" />
                        <span>
                            Extracto procesado: <strong>{uploadSummary.total_movements}</strong> movimientos ({uploadSummary.auto_reconciled} autoliquidados, {uploadSummary.pending_count} pendientes, {uploadSummary.synced_to_ledger || 0} sincronizados al libro).
                        </span>
                    </div>
                )}

                <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.5rem' }}>
                    {activeTab === 'settings' ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '760px' }}>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', color: '#e2e8f0', fontWeight: 600, marginBottom: '0.3rem' }}>
                                    Tus Nombres / Apellidos (para detectar transferencias propias):
                                </label>
                                <input
                                    type="text"
                                    value={settingsForm.owner_names}
                                    onChange={e => setSettingsForm({ ...settingsForm, owner_names: e.target.value })}
                                    style={{ width: '100%', padding: '0.55rem', borderRadius: '0.4rem', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.85rem' }}
                                />
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', color: '#e2e8f0', fontWeight: 600, marginBottom: '0.3rem' }}>
                                    Tu CUIT / CUIL (sin guiones, separados por coma):
                                </label>
                                <input
                                    type="text"
                                    value={settingsForm.owner_cuits}
                                    onChange={e => setSettingsForm({ ...settingsForm, owner_cuits: e.target.value })}
                                    style={{ width: '100%', padding: '0.55rem', borderRadius: '0.4rem', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.85rem' }}
                                />
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', color: '#38bdf8', fontWeight: 600, marginBottom: '0.3rem' }}>
                                    Cuentas Operativas de Arbitraje (Transferencias propias entre estas = PASE PROPIO neutro):
                                </label>
                                <input
                                    type="text"
                                    value={settingsForm.operational_accounts}
                                    onChange={e => setSettingsForm({ ...settingsForm, operational_accounts: e.target.value })}
                                    style={{ width: '100%', padding: '0.55rem', borderRadius: '0.4rem', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.85rem' }}
                                />
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', color: '#f59e0b', fontWeight: 600, marginBottom: '0.3rem' }}>
                                    Tus Cuentas Personales Externas (Bancos/Alias fuera del arbitraje = RETIRO si sale / INYECCIÓN si entra):
                                </label>
                                <input
                                    type="text"
                                    value={settingsForm.personal_external_accounts}
                                    onChange={e => setSettingsForm({ ...settingsForm, personal_external_accounts: e.target.value })}
                                    style={{ width: '100%', padding: '0.55rem', borderRadius: '0.4rem', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.85rem' }}
                                />
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', color: '#e2e8f0', fontWeight: 600, marginBottom: '0.3rem' }}>
                                    Umbral de Gasto Común/Personal automático en cuenta operativa ($ ARS):
                                </label>
                                <input
                                    type="number"
                                    value={settingsForm.personal_expense_threshold_ars}
                                    onChange={e => setSettingsForm({ ...settingsForm, personal_expense_threshold_ars: e.target.value })}
                                    style={{ width: '220px', padding: '0.55rem', borderRadius: '0.4rem', background: '#1e293b', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.85rem' }}
                                />
                                <span style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>
                                    Nota: Los impuestos/cargos bancarios (Ley 25.413, SIRCREB, comisiones) se detectan antes de este umbral como Gasto de Arbitraje deducible.
                                </span>
                            </div>
                            <button
                                onClick={handleSaveSettings}
                                disabled={savingSettings}
                                className="btn-primary"
                                style={{ alignSelf: 'flex-start', padding: '0.6rem 1.2rem', borderRadius: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
                            >
                                <Save size={15} /> {savingSettings ? 'Guardando...' : 'Guardar Reglas de Clasificación'}
                            </button>
                        </div>
                    ) : (
                        <div>
                            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.8rem', alignItems: 'center', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Filtrar categoría:</span>
                                {['ALL', 'PENDIENTE', 'PASE_PROPIO', 'RETIRO', 'INYECCION', 'GASTO_ARBITRAJE', 'GASTO_PERSONAL', 'P2P_MATCHED'].map(cat => (
                                    <button
                                        key={cat}
                                        onClick={() => { setFilterCat(cat); setShowAllRows(false); }}
                                        style={{ padding: '0.25rem 0.6rem', borderRadius: '0.4rem', border: '1px solid #334155', fontSize: '0.74rem', cursor: 'pointer', background: filterCat === cat ? '#38bdf8' : '#1e293b', color: filterCat === cat ? '#0f172a' : '#cbd5e1', fontWeight: filterCat === cat ? 700 : 500 }}
                                    >
                                        {cat === 'ALL' ? 'Todos' : cat}
                                    </button>
                                ))}
                            </div>

                            {loading ? (
                                <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Cargando movimientos bancarios...</p>
                            ) : filteredMovements.length === 0 ? (
                                <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b', border: '1px dashed #334155', borderRadius: '0.75rem' }}>
                                    <AlertCircle size={28} style={{ marginBottom: '0.5rem', opacity: 0.6 }} />
                                    <p style={{ margin: 0, fontSize: '0.88rem' }}>No hay movimientos bancarios registrados para este filtro. Subí tu extracto CSV/Excel arriba a la derecha.</p>
                                </div>
                            ) : (
                                <>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                                        <thead>
                                            <tr style={{ background: '#1e293b', color: '#94a3b8', textAlign: 'left' }}>
                                                <th style={{ padding: '0.55rem' }}>Fecha</th>
                                                <th style={{ padding: '0.55rem' }}>Banco</th>
                                                <th style={{ padding: '0.55rem' }}>Flujo</th>
                                                <th style={{ padding: '0.55rem' }}>Monto ARS</th>
                                                <th style={{ padding: '0.55rem' }}>Descripción / Contraparte</th>
                                                <th style={{ padding: '0.55rem' }}>Clasificación Contable</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {visibleMovements.map(m => (
                                                <tr key={m.tx_hash} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                                                    <td style={{ padding: '0.5rem', whiteSpace: 'nowrap', color: '#cbd5e1' }}>{String(m.fecha).slice(0, 16)}</td>
                                                    <td style={{ padding: '0.5rem', color: '#94a3b8', fontWeight: 600 }}>{m.banco}</td>
                                                    <td style={{ padding: '0.5rem', color: m.tipo_movimiento === 'CREDITO' ? '#34d399' : '#f87171', fontWeight: 700 }}>
                                                        {m.tipo_movimiento === 'CREDITO' ? '+ ENTRADA' : '- SALIDA'}
                                                    </td>
                                                    <td style={{ padding: '0.5rem', fontWeight: 700, color: '#f8fafc' }}>
                                                        ${Number(m.monto_ars || 0).toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                                                    </td>
                                                    <td style={{ padding: '0.5rem', color: '#cbd5e1' }}>
                                                        <div>{m.descripcion || '-'}</div>
                                                        {m.nota_auditoria && <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{m.nota_auditoria}</div>}
                                                    </td>
                                                    <td style={{ padding: '0.5rem' }}>
                                                        <select
                                                            value={m.categoria || 'PENDIENTE'}
                                                            onChange={e => handleCategoryChange(m.tx_hash, e.target.value)}
                                                            style={{ padding: '0.35rem 0.5rem', borderRadius: '0.4rem', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem', width: '100%' }}
                                                        >
                                                            {CATEGORY_OPTIONS.map(opt => (
                                                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                            ))}
                                                        </select>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {filteredMovements.length > 150 && !showAllRows && (
                                        <div style={{ marginTop: '0.75rem', textAlign: 'center' }}>
                                            <button
                                                type="button"
                                                onClick={() => setShowAllRows(true)}
                                                className="btn-secondary"
                                                style={{ padding: '0.45rem 1rem', fontSize: '0.78rem' }}
                                            >
                                                {`Mostrar todos los movimientos (${filteredMovements.length})`}
                                            </button>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
