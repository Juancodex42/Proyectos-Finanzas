import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowRight } from 'lucide-react';

export function TaxEmptyState({ selectedYear }) {
    return (
        <div className="card-surface" style={{ padding: '3.5rem 2rem', textAlign: 'center', border: '1px solid var(--border-color)' }}>
            <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '16px',
                background: 'var(--brand-indigo-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 1.25rem auto',
                border: '1px solid var(--brand-indigo-border)'
            }}>
                <ShieldAlert size={30} color="#818CF8" />
            </div>
            <h3 style={{ margin: '0 0 0.5rem 0', color: '#F8FAFC', fontSize: '1.25rem', fontWeight: 700 }}>
                No se registraron operaciones contables para el ejercicio {selectedYear}
            </h3>
            <p style={{ margin: '0 auto 1.5rem auto', color: 'var(--text-secondary)', fontSize: '0.92rem', maxWidth: '620px', lineHeight: 1.6 }}>
                Para visualizar la liquidación impositiva y el cálculo de Ganancias e IIBB, importa tus extractos de exchanges o registra certificaciones contables emitidas por Contador Público (C.P.N.).
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <Link
                    to="/apis"
                    className="btn-primary"
                    style={{ padding: '0.65rem 1.4rem', fontSize: '0.88rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
                >
                    <span>Importar Operaciones / CSV</span>
                    <ArrowRight size={15} />
                </Link>
                <Link
                    to={selectedYear ? `/calendar?tab=certifications&year=${selectedYear}` : '/calendar?tab=certifications'}
                    className="btn-secondary"
                    style={{ padding: '0.65rem 1.4rem', fontSize: '0.88rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
                >
                    <span>Ir a Certificaciones CPN</span>
                </Link>
            </div>
        </div>
    );
}

export default TaxEmptyState;
