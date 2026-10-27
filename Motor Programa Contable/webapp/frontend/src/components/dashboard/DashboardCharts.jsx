import React from 'react';
import {
    AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    PieChart, Pie, Cell
} from 'recharts';

const PIE_COLORS = ['#4F46E5', '#10B981', '#F59E0B', '#06B6D4', '#818CF8', '#FB7185', '#64748B'];

const CustomAreaTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        const val = payload[0].value;
        return (
            <div style={{
                backgroundColor: '#182238',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '8px',
                padding: '0.75rem 1rem',
                boxShadow: '0 12px 28px rgba(0, 0, 0, 0.55)',
                fontSize: '13px'
            }}>
                <div style={{ color: '#94A3B8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.35rem', fontWeight: 600 }}>
                    Período: {label}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, color: '#F8FAFC', fontSize: '14px' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#818CF8', display: 'inline-block' }} />
                    <span style={{ color: '#94A3B8', fontWeight: 500 }}>Capital Acumulado:</span>
                    <span style={{ color: val >= 0 ? '#34D399' : '#FB7185' }} className="tabular-nums">
                        {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(val || 0)}
                    </span>
                </div>
            </div>
        );
    }
    return null;
};

const CustomBarTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        const buys = payload.find(p => p.dataKey === 'buys')?.value || 0;
        const sells = payload.find(p => p.dataKey === 'sells')?.value || 0;
        const net = sells - buys;
        return (
            <div style={{
                backgroundColor: '#182238',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '8px',
                padding: '0.75rem 1rem',
                boxShadow: '0 12px 28px rgba(0, 0, 0, 0.55)',
                fontSize: '13px',
                minWidth: '220px'
            }}>
                <div style={{ color: '#94A3B8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', fontWeight: 600 }}>
                    Fecha: {label}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94A3B8' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10B981', display: 'inline-block' }} />
                            Compras:
                        </span>
                        <strong style={{ color: '#F8FAFC' }} className="tabular-nums">
                            {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(buys)}
                        </strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94A3B8' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#818CF8', display: 'inline-block' }} />
                            Ventas:
                        </span>
                        <strong style={{ color: '#F8FAFC' }} className="tabular-nums">
                            {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(sells)}
                        </strong>
                    </div>
                    <div style={{ marginTop: '0.25rem', paddingTop: '0.35rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)', display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center' }}>
                        <span style={{ color: '#94A3B8', fontSize: '12px' }}>Flujo Neto:</span>
                        <strong style={{ color: net >= 0 ? '#34D399' : '#FB7185' }} className="tabular-nums">
                            {net >= 0 ? '+' : ''}{new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(net)}
                        </strong>
                    </div>
                </div>
            </div>
        );
    }
    return null;
};

const CustomPieTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
        const item = payload[0];
        return (
            <div style={{
                backgroundColor: '#182238',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                borderRadius: '8px',
                padding: '0.6rem 0.85rem',
                boxShadow: '0 12px 28px rgba(0, 0, 0, 0.55)',
                fontSize: '13px'
            }}>
                <div style={{ color: '#F8FAFC', fontWeight: 700 }}>{item.name}</div>
                <div style={{ color: '#94A3B8', fontSize: '12px', marginTop: '0.2rem' }}>
                    Volumen: <strong style={{ color: '#818CF8' }} className="tabular-nums">
                        {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(item.value)}
                    </strong>
                </div>
            </div>
        );
    }
    return null;
};

export function DashboardCharts({
    equityCurve = [],
    dailyVol = [],
    exchangeDist = [],
    equityInterval,
    setEquityInterval
}) {
    return (
        <>
            {/* EQUITY CURVE CHART */}
            <div className="card-surface" style={{ padding: '1.5rem', marginBottom: '1.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#818CF8' }} />
                            <h2 style={{ margin: 0, fontSize: '1.15rem', color: '#F8FAFC', fontWeight: 700 }}>
                                Curva de Equity (Ganancia Acumulada)
                            </h2>
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                            Evolución continua del capital neto obtenido en pesos argentinos.
                        </p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Intervalo:</span>
                        <select
                            value={equityInterval}
                            onChange={(e) => setEquityInterval(e.target.value)}
                            className="input-field"
                            style={{ padding: '0.35rem 0.75rem', fontSize: '0.85rem', width: 'auto', fontWeight: 600 }}
                        >
                            <option value="daily">Diario</option>
                            <option value="weekly">Semanal</option>
                            <option value="monthly">Mensual</option>
                            <option value="yearly">Anual</option>
                        </select>
                    </div>
                </div>

                {equityCurve.length > 0 ? (
                    <div style={{ height: '320px' }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={equityCurve} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                                <defs>
                                    <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.35} />
                                        <stop offset="95%" stopColor="#4F46E5" stopOpacity={0.0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                                <XAxis dataKey="period" stroke="#64748B" tick={{ fontSize: 11, fill: '#94A3B8' }} />
                                <YAxis stroke="#64748B" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: '#94A3B8' }} />
                                <Tooltip content={<CustomAreaTooltip />} />
                                <Area
                                    type="monotone"
                                    dataKey="equity"
                                    name="Capital Neto Acumulado (ARS)"
                                    stroke="#818CF8"
                                    strokeWidth={2.5}
                                    fill="url(#equityGradient)"
                                    activeDot={{ r: 6, fill: '#818CF8', stroke: '#090D14', strokeWidth: 2 }}
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                ) : (
                    <div style={{ padding: '3rem 1rem', textAlign: 'center', background: 'var(--bg-panel)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                        <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '0.9rem' }}>
                            Sin datos suficientes para proyectar la curva de equity en el período seleccionado.
                        </p>
                    </div>
                )}
            </div>

            {/* CHARTS GRID (2 COLUMNS: VOLUME & PLATFORMS) */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
                <div className="card-surface" style={{ padding: '1.5rem' }}>
                    <div style={{ marginBottom: '1.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10B981' }} />
                            <h2 style={{ margin: 0, fontSize: '1.1rem', color: '#F8FAFC', fontWeight: 700 }}>
                                Volumen de Compras vs Ventas (ARS)
                            </h2>
                        </div>
                        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                            Comparativa de flujos operativos por fecha.
                        </p>
                    </div>

                    {dailyVol.length > 0 ? (
                        <div style={{ height: '280px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={dailyVol} margin={{ top: 15, right: 15, left: 10, bottom: 5 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
                                    <XAxis dataKey="day" stroke="#64748B" tick={{ fontSize: 11, fill: '#94A3B8' }} />
                                    <YAxis stroke="#64748B" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: '#94A3B8' }} />
                                    <Tooltip content={<CustomBarTooltip />} />
                                    <Legend wrapperStyle={{ fontSize: '12px', color: '#94A3B8', paddingTop: '10px' }} />
                                    <Bar dataKey="buys" name="Compras Fiat" fill="#10B981" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="sells" name="Ventas Fiat" fill="#818CF8" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div style={{ padding: '3rem 1rem', textAlign: 'center', background: 'var(--bg-panel)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                            <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '0.9rem' }}>Sin datos diarios registrados.</p>
                        </div>
                    )}
                </div>

                <div className="card-surface" style={{ padding: '1.5rem' }}>
                    <div style={{ marginBottom: '1.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#06B6D4' }} />
                            <h2 style={{ margin: 0, fontSize: '1.1rem', color: '#F8FAFC', fontWeight: 700 }}>
                                Distribución por Plataforma / Exchange
                            </h2>
                        </div>
                        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
                            Concentración de volumen operado en pesos.
                        </p>
                    </div>

                    {exchangeDist.length > 0 ? (
                        <div style={{ height: '280px' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={exchangeDist}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={55}
                                        outerRadius={85}
                                        paddingAngle={4}
                                        dataKey="value"
                                    >
                                        {exchangeDist.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} stroke="#121A2B" strokeWidth={2} />
                                        ))}
                                    </Pie>
                                    <Tooltip content={<CustomPieTooltip />} />
                                    <Legend wrapperStyle={{ fontSize: '12px', color: '#94A3B8', paddingTop: '10px' }} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    ) : (
                        <div style={{ padding: '3rem 1rem', textAlign: 'center', background: 'var(--bg-panel)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                            <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '0.9rem' }}>Sin exchanges registrados.</p>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

export default DashboardCharts;
