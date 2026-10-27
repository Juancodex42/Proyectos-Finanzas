import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, ArrowRight } from 'lucide-react';

export function HomeGapsCard({ gaps = [], gapsModes }) {
    if (!gaps || gaps.length === 0) return null;

    const hasGlobalMode = gapsModes?.global?.total_gaps !== undefined;
    const realGapsCount = hasGlobalMode ? Number(gapsModes.global.total_gaps) : gaps.length;
    const globalGapsList = Array.isArray(gapsModes?.global?.gaps) ? gapsModes.global.gaps : [];
    const cardsToRender = (hasGlobalMode && realGapsCount > 0 && globalGapsList.length > 0) ? globalGapsList : gaps;
    const isLocalOnly = hasGlobalMode && realGapsCount === 0 && gaps.length > 0;

    return (
        <div style={{
            backgroundColor: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid var(--accent-amber-border)',
            borderRadius: 'var(--radius-lg)',
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem',
            boxShadow: 'var(--shadow-sm)'
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                    <div style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'rgba(245, 158, 11, 0.2)',
                        border: '1px solid var(--accent-amber-border)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--accent-amber-light)'
                    }}>
                        <Compass size={18} />
                    </div>
                    <div>
                        <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: '700', margin: 0, color: 'var(--accent-amber-light)' }}>
                            Brújula de Trazabilidad: {isLocalOnly
                                ? `0 Inconsistencias Globales (${gaps.length} desfasaje${gaps.length === 1 ? '' : 's'} local${gaps.length === 1 ? '' : 'es'} por exchange)`
                                : hasGlobalMode
                                    ? `${realGapsCount} Inconsistencias Globales`
                                    : `${gaps.length} faltante(s) de historial contable detectado(s)`}
                        </h3>
                        <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: '0.15rem 0 0 0' }}>
                            {isLocalOnly
                                ? 'Criterio Patrimonial Real (AFIP): No tenés faltantes patrimoniales globales. Las tarjetas inferiores corresponden a desfasajes locales entre exchanges (transferencias pendientes de conciliar):'
                                : hasGlobalMode
                                    ? `Criterio Patrimonial Real (AFIP): Tenés ${realGapsCount} ventas sin compra registrada en el sistema (pendientes de conciliar con extractos de Fiwind/OKX).`
                                    : 'Ventas sin lotes de compra previos registrados. Completa el historial para un cómputo fiscal certero:'}
                        </p>
                    </div>
                </div>
                <Link
                    to={cardsToRender?.[0]?.date ? `/calendar?tab=warnings&year=${String(cardsToRender[0].date).slice(0, 4)}` : '/calendar?tab=warnings'}
                    className="btn-secondary"
                    style={{
                        borderColor: 'var(--accent-amber-border)',
                        color: 'var(--accent-amber-light)',
                        backgroundColor: 'rgba(245, 158, 11, 0.12)',
                        fontSize: 'var(--text-xs)',
                        padding: '0.4rem 0.85rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        textDecoration: 'none'
                    }}
                >
                    <span>Resolver en Calendario</span>
                    <ArrowRight size={14} />
                </Link>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.65rem' }}>
                {cardsToRender.slice(0, 3).map((gap, idx) => (
                    <div
                        key={idx}
                        style={{
                            backgroundColor: 'var(--bg-panel)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--radius-sm)',
                            padding: '0.65rem 0.85rem',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.25rem'
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: 'var(--text-xs)' }}>
                                {gap.exchange}
                            </span>
                            <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                                {gap.date ? gap.date.split(' ')[0] : ''}
                            </span>
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent-rose-light)' }}>
                            Déficit: <strong>{Number(gap.deficit ?? gap.amount_missing ?? 0).toFixed(4)} {gap.coin}</strong> (Venta: {gap.sold_qty} {gap.coin})
                        </div>
                        {gap.clues && gap.clues[0] && (
                            <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--brand-indigo-light)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {gap.clues[0].icon || '💡'} {gap.clues[0].message}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default HomeGapsCard;
