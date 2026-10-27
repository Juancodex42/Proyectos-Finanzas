import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Landmark, Sliders, AlertCircle } from 'lucide-react';
import axios from 'axios';
import config from '../../config';
import BankReconcilerModal from './BankReconcilerModal';

export default function OperationalExportConfig({
    selectedExchanges,
    dateRange,
    operationalOptions,
    setOperationalOptions
}) {
    const [loadingDefaults, setLoadingDefaults] = useState(false);
    const [bankSummary, setBankSummary] = useState({});
    const [bankCount, setBankCount] = useState(0);
    const [showBankModal, setShowBankModal] = useState(false);

    const fetchOperationalDefaults = useCallback(async (signal) => {
        const isSignal = signal instanceof AbortSignal;
        setLoadingDefaults(true);
        try {
            const res = await axios.post(`${config.API_URL}/api/reports/operational-defaults`, {
                exchanges: selectedExchanges,
                dateStart: dateRange?.start || '',
                dateEnd: dateRange?.end || ''
            }, isSignal ? { signal } : {});
            if (isSignal && signal.aborted) return;
            const d = res.data || {};
            if (d.success) {
                setOperationalOptions({
                    existencia_inicial_usd: d.existencia_inicial_usd ?? 0,
                    existencia_inicial_ars: d.existencia_inicial_ars ?? 0,
                    garantia_total_usdt: d.garantia_total_usdt ?? 0,
                    saldo_bancos_final_ars: d.saldo_bancos_final_ars ?? 0,
                    cotizacion_cierre_usdt: d.cotizacion_cierre_usdt ?? 0
                });
                setBankSummary(d.bank_summary_by_category || {});
                setBankCount(d.bank_movements_count || 0);
            }
        } catch (err) {
            if (err.name === 'AbortError' || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
            console.error('Error fetching operational defaults:', err);
        } finally {
            if (!(isSignal && signal.aborted)) {
                setLoadingDefaults(false);
            }
        }
    }, [selectedExchanges, dateRange?.start, dateRange?.end, setOperationalOptions]);

    useEffect(() => {
        const controller = new AbortController();
        fetchOperationalDefaults(controller.signal);
        return () => controller.abort();
    }, [fetchOperationalDefaults]);

    const handleChange = (field, val) => {
        setOperationalOptions(prev => ({
            ...prev,
            [field]: val === '' ? 0 : (parseFloat(val) || 0)
        }));
    };

    const pendingCount = bankSummary?.PENDIENTE?.count || 0;

    return (
        <div style={{
            background: 'rgba(15, 23, 42, 0.75)',
            border: '1px solid rgba(6, 182, 212, 0.35)',
            borderRadius: '0.75rem',
            padding: '0.9rem 1rem',
            marginBottom: '1rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.75rem'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Sliders size={15} /> Parámetros de Stock Inicial y Cierre Bancario
                </span>
                <button
                    type="button"
                    onClick={() => fetchOperationalDefaults()}
                    disabled={loadingDefaults}
                    style={{
                        background: 'rgba(30, 41, 59, 0.8)',
                        border: '1px solid rgba(148, 163, 184, 0.25)',
                        color: '#cbd5e1',
                        padding: '0.25rem 0.55rem',
                        borderRadius: '0.4rem',
                        fontSize: '0.73rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.3rem'
                    }}
                >
                    <RefreshCw size={12} className={loadingDefaults ? 'spin' : ''} /> Autocalcular
                </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
                <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                        Stock Inicial USD (USDT)
                    </label>
                    <input
                        type="number"
                        step="0.01"
                        value={operationalOptions.existencia_inicial_usd ?? 0}
                        onChange={e => handleChange('existencia_inicial_usd', e.target.value)}
                        style={{ width: '100%', padding: '0.4rem 0.55rem', borderRadius: '0.4rem', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.8rem', boxSizing: 'border-box' }}
                    />
                </div>
                <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                        Saldo Inicial Bancos ($ ARS)
                    </label>
                    <input
                        type="number"
                        step="0.01"
                        value={operationalOptions.existencia_inicial_ars ?? 0}
                        onChange={e => handleChange('existencia_inicial_ars', e.target.value)}
                        style={{ width: '100%', padding: '0.4rem 0.55rem', borderRadius: '0.4rem', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.8rem', boxSizing: 'border-box' }}
                    />
                </div>
                <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                        Saldo Real Bancos Cierre ($)
                    </label>
                    <input
                        type="number"
                        step="0.01"
                        value={operationalOptions.saldo_bancos_final_ars ?? 0}
                        onChange={e => handleChange('saldo_bancos_final_ars', e.target.value)}
                        style={{ width: '100%', padding: '0.4rem 0.55rem', borderRadius: '0.4rem', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.8rem', boxSizing: 'border-box' }}
                    />
                </div>
                <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                        Garantía Merchant (USDT)
                    </label>
                    <input
                        type="number"
                        step="0.01"
                        value={operationalOptions.garantia_total_usdt ?? 0}
                        onChange={e => handleChange('garantia_total_usdt', e.target.value)}
                        style={{ width: '100%', padding: '0.4rem 0.55rem', borderRadius: '0.4rem', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.8rem', boxSizing: 'border-box' }}
                    />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: '#94a3b8', marginBottom: '0.2rem' }}>
                        Cotización USDT de Cierre ($ ARS / USDT)
                    </label>
                    <input
                        type="number"
                        step="0.01"
                        value={operationalOptions.cotizacion_cierre_usdt ?? 0}
                        onChange={e => handleChange('cotizacion_cierre_usdt', e.target.value)}
                        style={{ width: '100%', padding: '0.4rem 0.55rem', borderRadius: '0.4rem', background: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.8rem', boxSizing: 'border-box' }}
                    />
                </div>
            </div>

            <div style={{
                paddingTop: '0.55rem',
                borderTop: '1px solid rgba(255,255,255,0.06)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '0.5rem',
                flexWrap: 'wrap'
            }}>
                <div style={{ fontSize: '0.74rem', color: '#cbd5e1' }}>
                    <span>Extractos en período: <strong>{bankCount}</strong> movs.</span>
                    {pendingCount > 0 && (
                        <span style={{ color: '#fbbf24', marginLeft: '0.4rem', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                            <AlertCircle size={12} /> {pendingCount} sin clasificar
                        </span>
                    )}
                </div>
                <button
                    type="button"
                    onClick={() => setShowBankModal(true)}
                    style={{
                        background: 'rgba(14, 165, 233, 0.16)',
                        border: '1px solid rgba(56, 189, 248, 0.45)',
                        color: '#38bdf8',
                        padding: '0.38rem 0.7rem',
                        borderRadius: '0.45rem',
                        fontSize: '0.76rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.35rem'
                    }}
                >
                    <Landmark size={14} /> Conciliar Extractos y Cuentas Propias
                </button>
            </div>

            <BankReconcilerModal
                show={showBankModal}
                onClose={() => setShowBankModal(false)}
                dateRange={dateRange}
                onUpdated={fetchOperationalDefaults}
            />
        </div>
    );
}
