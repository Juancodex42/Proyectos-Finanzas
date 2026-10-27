import React from 'react';
import { Calendar, Clock, AlertTriangle, ShieldCheck } from 'lucide-react';

/**
 * DateRangeSelector Component
 * Column 2 of Reports page: date inputs and quick presets.
 */
export function DateRangeSelector({
    dateRange,
    setDateRange,
    datesInverted,
    latestCertDate,
    handlePreset,
    formatDateDisplay
}) {
    return (
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', borderRadius: '1rem', height: '100%', overflow: 'hidden' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#f8fafc' }}>
                2. Rango Temporal
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 1rem 0' }}>
                Elige las fechas límite para las operaciones contables.
            </p>

            <div style={{ display: 'grid', gap: '1.25rem', marginBottom: '1rem' }}>
                <div>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '600' }}>
                        Fecha de Inicio
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', borderRadius: '0.5rem', padding: '0.75rem' }}>
                        <Calendar
                            size={18}
                            color="#38bdf8"
                            style={{ marginRight: '0.75rem', cursor: 'pointer' }}
                            title="Abrir calendario visual"
                            onClick={(e) => {
                                const inp = e.currentTarget.parentElement.querySelector('input[type="date"]');
                                if (inp && typeof inp.showPicker === 'function') { try { inp.showPicker(); } catch { void 0; } }
                            }}
                        />
                        <input
                            type="date"
                            style={{ background: 'transparent', border: 'none', color: 'white', flex: 1, outline: 'none', fontSize: '0.95rem' }}
                            value={dateRange.start ? dateRange.start.split(' ')[0] : ''}
                            onChange={e => setDateRange({ ...dateRange, start: e.target.value })}
                        />
                    </div>
                    {dateRange.start && dateRange.start.includes(' ') && (
                        <div style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: '600' }}>
                            <Clock size={12} />
                            <span>Inicio exacto: {formatDateDisplay(dateRange.start)}</span>
                        </div>
                    )}
                </div>

                <div>
                    <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: '600' }}>
                        Fecha de Fin
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center', background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-color)', borderRadius: '0.5rem', padding: '0.75rem' }}>
                        <Calendar
                            size={18}
                            color="#38bdf8"
                            style={{ marginRight: '0.75rem', cursor: 'pointer' }}
                            title="Abrir calendario visual"
                            onClick={(e) => {
                                const inp = e.currentTarget.parentElement.querySelector('input[type="date"]');
                                if (inp && typeof inp.showPicker === 'function') { try { inp.showPicker(); } catch { void 0; } }
                            }}
                        />
                        <input
                            type="date"
                            style={{ background: 'transparent', border: 'none', color: 'white', flex: 1, outline: 'none', fontSize: '0.95rem' }}
                            value={dateRange.end ? dateRange.end.split(' ')[0] : ''}
                            onChange={e => setDateRange({ ...dateRange, end: e.target.value })}
                        />
                    </div>
                    {dateRange.end && dateRange.end.includes(' ') && (
                        <div style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '0.3rem', fontWeight: '600' }}>
                            <Clock size={12} />
                            <span>Fin exacto: {formatDateDisplay(dateRange.end)}</span>
                        </div>
                    )}
                </div>
            </div>

            {datesInverted && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', borderRadius: '0.5rem', marginBottom: '1.25rem' }}>
                    <AlertTriangle size={16} color="#f87171" style={{ flexShrink: 0 }} />
                    <span style={{ color: '#fca5a5', fontSize: '0.8rem', fontWeight: '600' }}>
                        La fecha de inicio debe ser anterior o igual a la fecha de fin.
                    </span>
                </div>
            )}

            <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '1.25rem', marginTop: '1.25rem' }}>
                <button
                    onClick={() => handlePreset('last_cert')}
                    disabled={!latestCertDate}
                    title={latestCertDate ? `Establecer fecha de inicio en la última certificación (${formatDateDisplay(latestCertDate)})` : 'No hay certificaciones registradas'}
                    style={{
                        width: '100%',
                        padding: '0.65rem 0.75rem',
                        background: latestCertDate ? 'rgba(56, 189, 248, 0.12)' : 'rgba(30, 41, 59, 0.4)',
                        border: latestCertDate ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid var(--border-color)',
                        color: latestCertDate ? '#38bdf8' : 'var(--text-secondary)',
                        borderRadius: '0.5rem',
                        fontSize: '0.85rem',
                        cursor: latestCertDate ? 'pointer' : 'not-allowed',
                        transition: 'all 0.2s',
                        fontWeight: '600',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '0.5rem',
                        marginBottom: '1.25rem',
                        opacity: latestCertDate ? 1 : 0.65
                    }}
                >
                    <ShieldCheck size={16} color={latestCertDate ? "#38bdf8" : "var(--text-secondary)"} />
                    {latestCertDate
                        ? `Desde Últ. Certificación (${formatDateDisplay(latestCertDate)})`
                        : 'Sin Certificación Previa'}
                </button>

                <h4 style={{ fontSize: '0.9rem', color: '#f8fafc', margin: '0 0 0.75rem 0', fontWeight: '700' }}>Atajos Rápidos</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <button
                        onClick={() => handlePreset('current_month')}
                        style={{ padding: '0.6rem', background: 'rgba(30, 41, 59, 0.6)', border: '1px solid var(--border-color)', color: '#cbd5e1', borderRadius: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500' }}
                    >
                        Mes Actual
                    </button>
                    <button
                        onClick={() => handlePreset('last_month')}
                        style={{ padding: '0.6rem', background: 'rgba(30, 41, 59, 0.6)', border: '1px solid var(--border-color)', color: '#cbd5e1', borderRadius: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500' }}
                    >
                        Mes Anterior
                    </button>
                    <button
                        onClick={() => handlePreset('last_90')}
                        style={{ padding: '0.6rem', background: 'rgba(30, 41, 59, 0.6)', border: '1px solid var(--border-color)', color: '#cbd5e1', borderRadius: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500' }}
                    >
                        Últimos 90 Días
                    </button>
                    <button
                        onClick={() => handlePreset('all')}
                        style={{ padding: '0.6rem', background: 'rgba(30, 41, 59, 0.6)', border: '1px solid var(--border-color)', color: '#cbd5e1', borderRadius: '0.5rem', fontSize: '0.85rem', cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500' }}
                    >
                        Todo el Histórico
                    </button>
                </div>
            </div>
        </div>
    );
}

export default DateRangeSelector;
