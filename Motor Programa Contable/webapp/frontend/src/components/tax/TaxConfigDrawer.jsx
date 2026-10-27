import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export const DEFAULT_TAX_SETTINGS = {
    year: new Date().getFullYear(),
    ganancias_deduccion: 0,
    ganancias_alicuota: 15,
    iibb_tramo1_limite: 3255000000,
    iibb_tramo1_alicuota: 5.0,
    iibb_tramo2_limite: 26970000000,
    iibb_tramo2_alicuota: 6.0,
    iibb_tramo3_alicuota: 7.0,
    iibb_base_calculo: 'diferencial',
    iibb_provincia: 'Catamarca',
    ganancias_estimadas_fallback_pct: 15.0,
    usd_ars_exchange_rate: 1000.0
};

export const resolveIibbBracket = (baseVal, reportData) => {
    const cfg = reportData?.config_aplicada || reportData?.settings || {};
    if (cfg.iibb_provincia && cfg.iibb_provincia !== 'Catamarca') {
        return {
            tramo_iibb: 1,
            alicuota_iibb: Number(cfg.iibb_alicuota_t1 ?? cfg.iibb_tramo1_alicuota ?? 3.0)
        };
    }
    const t1 = Number(cfg.iibb_umbral_t1 || cfg.iibb_tramo1_limite || DEFAULT_TAX_SETTINGS.iibb_tramo1_limite);
    const t2 = Number(cfg.iibb_umbral_t2 || cfg.iibb_tramo2_limite || DEFAULT_TAX_SETTINGS.iibb_tramo2_limite);
    const a1 = Number(cfg.iibb_alicuota_t1 ?? cfg.iibb_tramo1_alicuota ?? DEFAULT_TAX_SETTINGS.iibb_tramo1_alicuota);
    const a2 = Number(cfg.iibb_alicuota_t2 ?? cfg.iibb_tramo2_alicuota ?? DEFAULT_TAX_SETTINGS.iibb_tramo2_alicuota);
    const a3 = Number(cfg.iibb_alicuota_t3 ?? cfg.iibb_tramo3_alicuota ?? DEFAULT_TAX_SETTINGS.iibb_tramo3_alicuota);
    const val = Number(baseVal || 0);
    if (val <= t1) return { tramo_iibb: 1, alicuota_iibb: a1 };
    if (val <= t2) return { tramo_iibb: 2, alicuota_iibb: a2 };
    return { tramo_iibb: 3, alicuota_iibb: a3 };
};

export function TaxConfigDrawer({
    show,
    onClose,
    settingsForm,
    setSettingsForm,
    handleSaveSettings,
    savingSettings,
    paymentModalOpen = false,
    onClosePaymentModal,
    onSubmitPayment
}) {
    const [paymentForm, setPaymentForm] = useState({
        periodo: '',
        impuesto: 'IIBB',
        monto_ars: '',
        comprobante: ''
    });

    if (!show && !paymentModalOpen) return null;

    const handlePaymentSubmit = (e) => {
        e.preventDefault();
        if (onSubmitPayment) onSubmitPayment(paymentForm);
        if (onClosePaymentModal) onClosePaymentModal();
    };

    return (
        <AnimatePresence>
            {show && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    style={{
                        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                        background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)',
                        display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '1.5rem'
                    }}
                >
                    <motion.div
                        initial={{ scale: 0.95, y: 15 }}
                        animate={{ scale: 1, y: 0 }}
                        exit={{ scale: 0.95, y: 15 }}
                        className="card-surface"
                        style={{
                            width: '100%', maxWidth: '680px',
                            padding: '1.75rem 2rem', boxShadow: 'var(--shadow-lg)',
                            border: '1px solid var(--border-strong)',
                            maxHeight: '90vh', overflowY: 'auto'
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                                <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#818CF8' }} />
                                <h2 style={{ fontSize: '1.25rem', color: '#F8FAFC', margin: 0, fontWeight: 700 }}>
                                    Parámetros Fiscales ({settingsForm.year})
                                </h2>
                            </div>
                            <button
                                onClick={onClose}
                                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.2rem', padding: '0.2rem' }}
                            >
                                ✕
                            </button>
                        </div>

                        <form onSubmit={handleSaveSettings}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.25rem', marginBottom: '1.75rem' }}>
                                <div className="panel-surface" style={{ padding: '1.1rem' }}>
                                    <h4 style={{ color: '#818CF8', margin: '0 0 0.85rem 0', fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                        Configuración General & Tipo de Cambio
                                    </h4>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                        <div>
                                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>
                                                Tipo de Cambio USD/ARS ($)
                                            </label>
                                            <input
                                                type="number"
                                                value={settingsForm.usd_ars_exchange_rate}
                                                onChange={(e) => setSettingsForm({ ...settingsForm, usd_ars_exchange_rate: Number(e.target.value) })}
                                                className="input-field"
                                            />
                                        </div>
                                        <div>
                                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>
                                                Margen Fallback Estimado (%)
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={settingsForm.ganancias_estimadas_fallback_pct}
                                                onChange={(e) => setSettingsForm({ ...settingsForm, ganancias_estimadas_fallback_pct: Number(e.target.value) })}
                                                className="input-field"
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="panel-surface" style={{ padding: '1.1rem', border: '1px solid var(--accent-amber-border)' }}>
                                    <h4 style={{ color: '#FBBF24', margin: '0 0 0.85rem 0', fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                        Impuesto Cedular / Ganancias
                                    </h4>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                                        <div>
                                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>
                                                Deducción Especial / MNI ($)
                                            </label>
                                            <input
                                                type="number"
                                                value={settingsForm.ganancias_deduccion}
                                                onChange={(e) => setSettingsForm({ ...settingsForm, ganancias_deduccion: Number(e.target.value) })}
                                                className="input-field"
                                            />
                                        </div>
                                        <div>
                                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>
                                                Alícuota Impositiva (%)
                                            </label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={settingsForm.ganancias_alicuota}
                                                onChange={(e) => setSettingsForm({ ...settingsForm, ganancias_alicuota: Number(e.target.value) })}
                                                className="input-field"
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="panel-surface" style={{ padding: '1.1rem', border: '1px solid var(--brand-indigo-border)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                                        <h4 style={{ color: '#818CF8', margin: 0, fontSize: '0.9rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                            Ingresos Brutos (IIBB)
                                        </h4>
                                        <select
                                            value={settingsForm.iibb_provincia}
                                            onChange={(e) => setSettingsForm({ ...settingsForm, iibb_provincia: e.target.value })}
                                            className="input-field"
                                            style={{ width: 'auto', padding: '0.25rem 0.6rem', fontSize: '0.8rem', fontWeight: 600, color: '#818CF8' }}
                                        >
                                            <option value="Catamarca">Catamarca (Escala Progresiva)</option>
                                            <option value="General">Régimen Simplificado (Flat Rate)</option>
                                        </select>
                                    </div>

                                    {settingsForm.iibb_provincia === 'Catamarca' ? (
                                        <>
                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                                                <div>
                                                    <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Límite Tramo 1 ($)</label>
                                                    <input type="number" value={settingsForm.iibb_tramo1_limite} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_tramo1_limite: Number(e.target.value) })} className="input-field" />
                                                </div>
                                                <div>
                                                    <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Alícuota Tramo 1 (%)</label>
                                                    <input type="number" step="0.1" value={settingsForm.iibb_tramo1_alicuota} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_tramo1_alicuota: Number(e.target.value) })} className="input-field" />
                                                </div>
                                            </div>
                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '0.75rem' }}>
                                                <div>
                                                    <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Límite Tramo 2 ($)</label>
                                                    <input type="number" value={settingsForm.iibb_tramo2_limite} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_tramo2_limite: Number(e.target.value) })} className="input-field" />
                                                </div>
                                                <div>
                                                    <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Alícuota Tramo 2 (%)</label>
                                                    <input type="number" step="0.1" value={settingsForm.iibb_tramo2_alicuota} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_tramo2_alicuota: Number(e.target.value) })} className="input-field" />
                                                </div>
                                            </div>
                                            <div style={{ marginBottom: '0.75rem' }}>
                                                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Alícuota Tramo 3 (&gt; Tramo 2) (%)</label>
                                                <input type="number" step="0.1" value={settingsForm.iibb_tramo3_alicuota} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_tramo3_alicuota: Number(e.target.value) })} className="input-field" />
                                            </div>
                                        </>
                                    ) : (
                                        <div style={{ marginBottom: '0.75rem' }}>
                                            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Alícuota Plana / Única (%)</label>
                                            <input type="number" step="0.1" value={settingsForm.iibb_tramo1_alicuota} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_tramo1_alicuota: Number(e.target.value) })} className="input-field" />
                                        </div>
                                    )}

                                    <div>
                                        <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '0.35rem', fontWeight: 500 }}>Base de Cálculo IIBB</label>
                                        <select value={settingsForm.iibb_base_calculo} onChange={(e) => setSettingsForm({ ...settingsForm, iibb_base_calculo: e.target.value })} className="input-field">
                                            <option value="diferencial">Base Imponible Diferencial (Ganancia Neta / Spread)</option>
                                            <option value="bruto">Monto Bruto de Ventas Total</option>
                                        </select>
                                    </div>
                                </div>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', borderTop: '1px solid var(--border-color)', paddingTop: '1.25rem' }}>
                                <button type="button" onClick={onClose} className="btn-secondary">Cancelar</button>
                                <button type="submit" disabled={savingSettings} className="btn-primary">
                                    {savingSettings ? 'Guardando...' : 'Guardar Parámetros'}
                                </button>
                            </div>
                        </form>
                    </motion.div>
                </motion.div>
            )}

            {paymentModalOpen && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    style={{
                        position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.75)',
                        display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1001, padding: '1.5rem'
                    }}
                >
                    <div className="card-surface" style={{ width: '100%', maxWidth: '460px', padding: '1.5rem' }}>
                        <h3 style={{ margin: '0 0 1rem 0', color: '#F8FAFC' }}>Registrar Pago Impositivo</h3>
                        <form onSubmit={handlePaymentSubmit} style={{ display: 'grid', gap: '0.85rem' }}>
                            <input
                                type="text"
                                placeholder="Período (ej. 2026-01)"
                                value={paymentForm.periodo}
                                onChange={(e) => setPaymentForm({ ...paymentForm, periodo: e.target.value })}
                                className="input-field"
                            />
                            <input
                                type="number"
                                step="0.01"
                                placeholder="Monto ARS"
                                value={paymentForm.monto_ars}
                                onChange={(e) => setPaymentForm({ ...paymentForm, monto_ars: e.target.value })}
                                className="input-field"
                            />
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
                                <button type="button" onClick={onClosePaymentModal} className="btn-secondary">Cancelar</button>
                                <button type="submit" className="btn-primary">Guardar Pago</button>
                            </div>
                        </form>
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

export default TaxConfigDrawer;
