import React from 'react';
import { UploadCloud, Layers, CheckCircle2, ShieldCheck } from 'lucide-react';

export function HomeWorkflowExplainer() {
    const supportedFormats = [
        'Binance Spot', 'Binance P2P', 'Bitso Alpha', 'Fiwind',
        'Ripio Classic', 'Ripio Trade', 'Planilla Consolidada'
    ];

    return (
        <div className="card-surface" style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
                <div style={{ marginBottom: '1.5rem' }}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: 'var(--brand-indigo-light)', fontSize: 'var(--text-xs)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '0.5rem' }}>
                        <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--brand-indigo)' }} />
                        Flujo de Auditoría Contable
                    </div>
                    <h3 style={{ fontSize: '1.2rem', fontWeight: '700', color: 'var(--text-primary)', margin: '0 0 0.4rem 0' }}>
                        Pipeline de Normalización FIFO
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-xs)', margin: 0, lineHeight: '1.5' }}>
                        Procesa extractos sin alterar la veracidad de los datos originales. El motor homologa columnas y clasifica por lotes fiscales.
                    </p>
                </div>

                {/* STEPS LIST */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem 1.15rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-panel)' }}>
                        <div style={{ width: '38px', height: '38px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--brand-indigo-subtle)', border: '1px solid var(--brand-indigo-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: 'var(--brand-indigo-light)' }}>
                            <UploadCloud size={20} />
                        </div>
                        <div>
                            <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: '700', margin: '0 0 0.2rem 0', color: 'var(--text-primary)' }}>
                                1. Ingestión Multi-Exchange
                            </h4>
                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.4' }}>
                                Detección heurística de formato: CSVs y Excels de Binance, Bitso, Fiwind, Ripio o plantillas manuales.
                            </p>
                        </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem 1.15rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--bg-panel)' }}>
                        <div style={{ width: '38px', height: '38px', borderRadius: 'var(--radius-sm)', backgroundColor: 'rgba(6, 182, 212, 0.15)', border: '1px solid rgba(6, 182, 212, 0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: '#06b6d4' }}>
                            <Layers size={20} />
                        </div>
                        <div>
                            <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: '700', margin: '0 0 0.2rem 0', color: 'var(--text-primary)' }}>
                                2. Conciliación & Anti-Duplicados
                            </h4>
                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.4' }}>
                                Normalización automática de fechas, pares cripto/fiat y hash criptográfico anti-duplicados.
                            </p>
                        </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', padding: '1rem 1.15rem', border: '1px solid var(--accent-emerald-border)', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--accent-emerald-subtle)' }}>
                        <div style={{ width: '38px', height: '38px', borderRadius: 'var(--radius-sm)', backgroundColor: 'rgba(16, 185, 129, 0.2)', border: '1px solid var(--accent-emerald-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: 'var(--accent-emerald-light)' }}>
                            <CheckCircle2 size={20} />
                        </div>
                        <div>
                            <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: '700', margin: '0 0 0.2rem 0', color: 'var(--text-primary)' }}>
                                3. Asignación FIFO & Certificación
                            </h4>
                            <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.4' }}>
                                Generación de planilla de ganancias de capital lista para presentación contable.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* COMPATIBILITY CHIPS */}
            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: 'var(--text-2xs)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: '600', marginBottom: '0.75rem' }}>
                    <ShieldCheck size={14} color="var(--brand-indigo-light)" /> Formatos Homologados
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {supportedFormats.map(ex => (
                        <span
                            key={ex}
                            className="badge badge-slate"
                            style={{ fontSize: 'var(--text-2xs)', padding: '0.25rem 0.55rem' }}
                        >
                            {ex}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default HomeWorkflowExplainer;
