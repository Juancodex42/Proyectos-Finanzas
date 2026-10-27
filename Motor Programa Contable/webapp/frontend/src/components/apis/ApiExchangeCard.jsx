import React from 'react';
import { CheckCircle, AlertCircle, Save, Shield, Info } from 'lucide-react';

export function ApiExchangeCard({
    ex,
    envKeys,
    apiStatuses,
    statusLoading,
    isEditing,
    setEditingEx,
    formData,
    setFormData,
    handleSaveKey
}) {
    const hasKey = !!envKeys[ex.keyName];
    const rawStatus = apiStatuses?.[ex.statusKey] || apiStatuses?.[ex.id] || apiStatuses?.statuses?.[ex.statusKey] || apiStatuses?.statuses?.[ex.id];
    const status = (typeof rawStatus === 'object' && rawStatus !== null ? rawStatus.status : rawStatus) || (hasKey ? 'unknown' : 'unconfigured');

    let badgeColor = '#64748B';
    let badgeBg = 'rgba(100, 116, 139, 0.12)';
    let statusText = 'SIN CONFIGURAR';

    if (statusLoading) {
        badgeColor = '#94A3B8';
        badgeBg = 'rgba(148, 163, 184, 0.1)';
        statusText = 'VERIFICANDO...';
    } else if (status === 'online') {
        badgeColor = '#10B981';
        badgeBg = 'rgba(16, 185, 129, 0.12)';
        statusText = 'ONLINE / AUTORIZADA';
    } else if (status === 'expired') {
        badgeColor = '#EF4444';
        badgeBg = 'rgba(239, 68, 68, 0.12)';
        statusText = 'CLAVE INVÁLIDA O VENCIDA';
    } else if (status === 'unconfigured') {
        badgeColor = '#64748B';
        badgeBg = 'rgba(100, 116, 139, 0.12)';
        statusText = 'SIN CONFIGURAR';
    } else if (status === 'offline') {
        badgeColor = '#F59E0B';
        badgeBg = 'rgba(245, 158, 11, 0.12)';
        statusText = 'ERROR DE RED / TIMEOUT';
    }

    return (
        <div className="card-surface" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ width: '38px', height: '38px', borderRadius: '8px', background: 'rgba(79, 70, 229, 0.1)', border: '1px solid rgba(79, 70, 229, 0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: '#818CF8', fontSize: '13px' }}>
                        {ex.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                            <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: '#F8FAFC' }}>
                                {ex.name}
                            </h3>
                            <span style={{ fontSize: '10px', padding: '0.15rem 0.5rem', borderRadius: '4px', background: badgeBg, color: badgeColor, fontWeight: 700, letterSpacing: '0.04em' }}>
                                {statusText}
                            </span>
                        </div>
                        <span style={{ fontSize: '12px', color: '#64748B', display: 'block', marginTop: '0.15rem' }}>
                            {hasKey ? 'Credenciales de lectura guardadas localmente' : 'Sin credenciales configuradas'}
                        </span>
                    </div>
                </div>
                <button
                    className={isEditing ? "btn-secondary" : (hasKey ? "btn-outline" : "btn-primary")}
                    style={{ padding: '0.5rem 1.1rem', fontSize: '12px' }}
                    onClick={() => {
                        if (isEditing) setEditingEx(null);
                        else {
                            setEditingEx(ex.id);
                            setFormData({ key: '', secret: '', password: '' });
                        }
                    }}
                >
                    {isEditing ? 'CANCELAR' : (hasKey ? 'MODIFICAR CLAVES' : 'CONECTAR API')}
                </button>
            </div>

            {(ex.id === 'okx' || ex.id === 'bybit') && (
                <div style={{
                    fontSize: '12px',
                    color: '#94A3B8',
                    background: 'rgba(79, 70, 229, 0.08)',
                    padding: '0.6rem 0.85rem',
                    borderRadius: '6px',
                    borderLeft: '3px solid #4F46E5',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                }}>
                    <Info size={15} color="#818CF8" style={{ flexShrink: 0 }} />
                    <span><strong>Aviso P2P:</strong> La extracción P2P vía API en {ex.name} requiere rol de Comerciante (Merchant). Para usuarios minoristas, importa tu extracto CSV/Excel en la sección Cargar Archivos.</span>
                </div>
            )}

            {ex.id === 'binance' && (
                <div style={{
                    fontSize: '12px',
                    color: '#94A3B8',
                    background: 'rgba(79, 70, 229, 0.08)',
                    padding: '0.6rem 0.85rem',
                    borderRadius: '6px',
                    borderLeft: '3px solid #4F46E5',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem'
                }}>
                    <Info size={15} color="#818CF8" style={{ flexShrink: 0 }} />
                    <span><strong>Binance Spot & P2P:</strong> Con estas mismas credenciales se sincronizan automáticamente Spot, P2P y Depósitos/Retiros. Nota: La API de Binance limita la extracción P2P a los últimos 180 días (6 meses). Para operaciones P2P más antiguas, expórtalas en Excel/CSV desde la web de Binance y súbelas en la sección Archivos.</span>
                </div>
            )}

            {isEditing && (
                <div style={{
                    background: '#090D14',
                    padding: '1.25rem',
                    borderRadius: '8px',
                    marginTop: '0.25rem',
                    border: '1px solid rgba(255,255,255,0.08)'
                }}>
                    <div style={{
                        fontSize: '13px',
                        color: '#94A3B8',
                        marginBottom: '1.25rem',
                        display: 'flex',
                        gap: '0.6rem',
                        alignItems: 'flex-start',
                        background: 'rgba(255,255,255,0.03)',
                        padding: '0.75rem',
                        borderRadius: '6px'
                    }}>
                        <Shield size={16} color="#10B981" style={{ flexShrink: 0, marginTop: '2px' }} />
                        <span>Genera una clave API con permisos exclusivos de lectura (<strong>Read-only</strong>). Tus credenciales se almacenan localmente y nunca se envían a servidores externos.</span>
                    </div>

                    <div style={{ display: 'grid', gap: '1rem' }}>
                        <div>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#94A3B8', marginBottom: '0.35rem' }}>API Key</label>
                            <input
                                type="text"
                                className="input-field"
                                placeholder={hasKey ? envKeys[ex.keyName] : "Ingresa tu API Key pública"}
                                value={formData.key}
                                onChange={e => setFormData({ ...formData, key: e.target.value })}
                                style={{ width: '100%', boxSizing: 'border-box' }}
                            />
                        </div>
                        <div>
                            <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#94A3B8', marginBottom: '0.35rem' }}>Secret Key</label>
                            <input
                                type="password"
                                className="input-field"
                                placeholder={hasKey ? "••••••••••••••••" : "Ingresa tu Secret Key privada"}
                                value={formData.secret}
                                onChange={e => setFormData({ ...formData, secret: e.target.value })}
                                style={{ width: '100%', boxSizing: 'border-box' }}
                            />
                        </div>
                        {ex.needsPassword && (
                            <div>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: '#94A3B8', marginBottom: '0.35rem' }}>API Password / Passphrase</label>
                                <input
                                    type="password"
                                    className="input-field"
                                    placeholder={hasKey ? "••••••••••••••••" : `Passphrase configurada en ${ex.name}`}
                                    value={formData.password}
                                    onChange={e => setFormData({ ...formData, password: e.target.value })}
                                    style={{ width: '100%', boxSizing: 'border-box' }}
                                />
                            </div>
                        )}
                        <button
                            className="btn-primary"
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '0.4rem',
                                padding: '0.65rem 1.25rem',
                                fontSize: '13px',
                                marginTop: '0.5rem',
                                width: 'fit-content'
                            }}
                            onClick={() => handleSaveKey(ex)}
                        >
                            <Save size={14} /> Guardar Credenciales
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ApiExchangeCard;
