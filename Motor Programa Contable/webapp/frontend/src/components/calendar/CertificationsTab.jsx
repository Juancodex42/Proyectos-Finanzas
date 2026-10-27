import React from 'react';
import {
  ShieldCheck, AlertTriangle, Clock, CheckCircle2,
  UploadCloud, Download, Trash2, Plus, Database
} from 'lucide-react';
import CalendarMonthGrid from './CalendarMonthGrid';
import {
  formatPeriodBoundary,
  formatPeriodRange,
  renderIssueDateBadge
} from './calendarUtils';

const CertificationsTab = ({
  certData = { certifications: [], summary: {} },
  certificationsList = [],
  selectedYear,
  setSelectedYear,
  availableYears = [],
  activeBrackets = [],
  monthlyCustody = {},
  apiBase = '',
  onOpenAddCertification,
  onOpenReplacePeriodModal,
  onDeleteClick
}) => {
  const summary = certData.summary || {};

  return (
    <>
      {/* KPI Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <div className="card-surface" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Estado Auditado
            </span>
            {summary.status === 'up_to_date' ? (
              <span className="badge badge-emerald">
                <CheckCircle2 size={12} /> Certificado al Día
              </span>
            ) : (
              <span className="badge badge-amber">
                <AlertTriangle size={12} /> Certificación Pendiente
              </span>
            )}
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 700, color: summary.status === 'up_to_date' ? '#34D399' : '#FBBF24' }}>
            {summary.status === 'up_to_date' ? 'Período Cubierto' : 'Certificación Pendiente'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {summary.status === 'up_to_date'
              ? 'Tus movimientos están respaldados formalmente.'
              : 'Se requiere subir dictamen contable para actualizar cobertura.'}
          </div>
        </div>

        <div className="card-surface" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Último Período Certificado
            </span>
            <ShieldCheck size={18} color="var(--brand-indigo-light)" />
          </div>
          <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-primary)' }} className="font-mono">
            {summary.latest_end_date ? (
              <span>Hasta {formatPeriodBoundary(summary.latest_end_date)}</span>
            ) : (
              <span style={{ color: 'var(--text-muted)' }}>Sin registros</span>
            )}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {(summary.total_count || certificationsList.length) > 0
              ? `${summary.total_count || certificationsList.length} certificación(es) registrada(s)`
              : 'No se han cargado certificados aún'}
          </div>
        </div>

        <div className="card-surface" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Período Sin Certificar
            </span>
            <Clock size={18} color={summary.uncertified_days ? '#FBBF24' : '#34D399'} />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: 700, color: summary.uncertified_days ? '#FBBF24' : '#34D399' }} className="font-mono">
            {summary.uncertified_days !== null && summary.uncertified_days !== undefined
              ? `${summary.uncertified_days} Días`
              : 'Pendiente'}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {summary.uncertified_days === 0
              ? 'Todas las operaciones están respaldadas formalmente.'
              : 'Días transcurridos desde el último período certificado.'}
          </div>
        </div>
      </div>

      {/* Month Timeline Grid */}
      <CalendarMonthGrid
        mode="certifications"
        selectedYear={selectedYear}
        setSelectedYear={setSelectedYear}
        availableYears={availableYears}
        certificationsList={certificationsList}
        activeBrackets={activeBrackets}
        monthlyCustody={monthlyCustody}
        onOpenAddCertification={onOpenAddCertification}
      />

      {/* Table Header Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ShieldCheck size={18} color="var(--brand-indigo-light)" />
          Listado de Dictámenes Oficiales C.P.N. ({certificationsList.length})
        </h3>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {onOpenReplacePeriodModal && (
            <button
              onClick={onOpenReplacePeriodModal}
              className="btn-secondary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                borderColor: 'rgba(59, 130, 246, 0.4)',
                color: '#60A5FA',
                fontSize: '0.82rem',
                padding: '0.4rem 0.85rem'
              }}
              title="Reemplazar transacciones provisorias con el anexo oficial de un dictamen CPA"
            >
              <Database size={15} />
              Reemplazo Oficial CPA
            </button>
          )}

          <button
            onClick={() => onOpenAddCertification && onOpenAddCertification()}
            className="btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.82rem', padding: '0.4rem 0.85rem' }}
          >
            <Plus size={15} />
            Nueva Certificación
          </button>
        </div>
      </div>

      {/* Certifications Dense Table */}
      <div className="sticky-table-container">
        <table className="table-ledger">
          <thead>
            <tr>
              <th>Título / Objeto del Dictamen</th>
              <th>Período Cubierto</th>
              <th>Contador / Matrícula</th>
              <th>Fecha Emisión</th>
              <th>Documento PDF</th>
              <th style={{ textAlign: 'right', width: '90px' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {certificationsList.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '3.5rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <UploadCloud size={40} style={{ margin: '0 auto 0.75rem', opacity: 0.6, color: 'var(--brand-indigo-light)' }} />
                  <h4 style={{ fontSize: '1.1rem', color: '#F8FAFC', margin: '0 0 0.25rem' }}>No hay certificaciones contables registradas</h4>
                  <p style={{ fontSize: '0.85rem', margin: '0 0 1.25rem' }}>Subí tus dictámenes contables en PDF para auditar tus transacciones.</p>
                  <button onClick={() => onOpenAddCertification && onOpenAddCertification()} className="btn-primary">
                    + Registrar Primer Certificado
                  </button>
                </td>
              </tr>
            ) : (
              certificationsList.map((cert) => (
                <tr key={cert.id}>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <ShieldCheck size={15} color="var(--brand-indigo-light)" style={{ flexShrink: 0 }} />
                      <span>{cert.title}</span>
                    </div>
                    {cert.notes && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 400, marginTop: '0.15rem', paddingLeft: '1.35rem' }}>
                        {cert.notes}
                      </div>
                    )}
                  </td>
                  <td className="font-mono">
                    <span className="badge badge-indigo" style={{ fontSize: '0.72rem' }}>
                      {formatPeriodRange(cert.start_date, cert.end_date)}
                    </span>
                  </td>
                  <td>
                    {cert.cpa_name ? (
                      <span style={{ fontWeight: 600, color: '#F8FAFC' }}>
                        {cert.cpa_name}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Sin asignar</span>
                    )}
                  </td>
                  <td className="font-mono">
                    {renderIssueDateBadge(cert.issue_date, cert.created_at)}
                  </td>
                  <td>
                    {cert.file_path ? (
                      <a
                        href={`${apiBase}/certifications/download/${cert.id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--brand-indigo-light)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', textDecoration: 'none', fontWeight: 600, fontSize: '0.82rem' }}
                      >
                        <Download size={13} /> Descargar PDF
                      </a>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>Sin archivo</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      onClick={() => onDeleteClick && onDeleteClick(cert.id, cert.title)}
                      style={{
                        background: 'var(--accent-rose-subtle)',
                        border: '1px solid var(--accent-rose-border)',
                        color: 'var(--accent-rose-light)',
                        padding: '0.35rem 0.55rem',
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        transition: 'all 150ms ease'
                      }}
                      title="Eliminar certificación"
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );
};

export default CertificationsTab;
