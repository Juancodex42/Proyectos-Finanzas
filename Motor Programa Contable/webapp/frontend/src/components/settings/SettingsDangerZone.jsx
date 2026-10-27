import React from 'react';
import { Trash2, AlertTriangle } from 'lucide-react';

export function SettingsDangerZone({
    selectedEx,
    onDeleteExchange,
    showAddModal,
    setShowAddModal,
    newExchangeName,
    setNewExchangeName,
    handleCreateExchange
}) {
    return (
        <>
            {showAddModal && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(9, 13, 20, 0.8)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div className="card-surface" style={{ padding: '2rem', width: '420px', background: '#121A2B', border: '1px solid rgba(255,255,255,0.12)', boxShadow: '0 20px 40px rgba(0,0,0,0.6)' }}>
                        <h3 style={{ color: '#F8FAFC', marginBottom: '0.5rem', fontSize: '1.1rem', fontWeight: 600 }}>Nuevo Exchange Personalizado</h3>
                        <p style={{ fontSize: '13px', color: '#94A3B8', marginBottom: '1.25rem' }}>Define un nuevo perfil para procesar extractos CSV o Excel no estándar.</p>

                        <label style={{ display: 'block', color: '#94A3B8', fontSize: '12px', fontWeight: 500, marginBottom: '0.4rem' }}>
                            Nombre de la Plataforma:
                        </label>
                        <input
                            type="text"
                            className="input-field"
                            placeholder="Ej: KuCoin, Lemon Cash, P2P Privado..."
                            value={newExchangeName}
                            onChange={e => setNewExchangeName(e.target.value)}
                            style={{ width: '100%', boxSizing: 'border-box', marginBottom: '1.5rem' }}
                        />
                        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
                            <button onClick={() => setShowAddModal(false)} className="btn-secondary" style={{ padding: '0.5rem 1rem', fontSize: '13px' }}>
                                Cancelar
                            </button>
                            <button onClick={handleCreateExchange} className="btn-primary" style={{ padding: '0.5rem 1.25rem', fontSize: '13px' }}>
                                Crear Perfil
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {selectedEx && selectedEx.type === 'CUSTOM_CSV' && (
                <div style={{
                    marginTop: '1.75rem',
                    padding: '1rem 1.25rem',
                    borderRadius: '8px',
                    background: 'rgba(244, 63, 94, 0.06)',
                    border: '1px solid rgba(244, 63, 94, 0.25)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '1rem'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                        <AlertTriangle size={16} color="#FB7185" />
                        <div>
                            <div style={{ fontSize: '13px', fontWeight: 600, color: '#FB7185' }}>Zona de Peligro</div>
                            <div style={{ fontSize: '12px', color: '#94A3B8' }}>Eliminar el perfil personalizado de {selectedEx.name}.</div>
                        </div>
                    </div>
                    <button
                        onClick={() => onDeleteExchange(selectedEx.id)}
                        style={{
                            background: 'rgba(244, 63, 94, 0.1)',
                            border: '1px solid rgba(244, 63, 94, 0.25)',
                            color: '#FB7185',
                            padding: '0.4rem 0.8rem',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            fontSize: '12px',
                            fontWeight: 500
                        }}
                    >
                        <Trash2 size={13} /> Eliminar Perfil
                    </button>
                </div>
            )}
        </>
    );
}

export default SettingsDangerZone;
