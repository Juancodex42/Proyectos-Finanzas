import { useState, useEffect } from 'react';
import { Save, AlertTriangle, Plus, Trash2 } from 'lucide-react';
import axios from 'axios';
import config from '../config';
import SettingsIntegritySection, { DEFAULT_MAPPING_FIELDS } from '../components/settings/SettingsIntegritySection';
import SettingsDangerZone from '../components/settings/SettingsDangerZone';

function Settings() {
    const [exchanges, setExchanges] = useState([]);
    const [selectedExchangeId, setSelectedExchangeId] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);
    const [showAddModal, setShowAddModal] = useState(false);
    const [newExchangeName, setNewExchangeName] = useState('');

    const fetchExchanges = async (signal) => {
        const isSignal = signal instanceof AbortSignal;
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get(`${config.API_URL}/api/exchanges`, isSignal ? { signal } : {});
            const data = res.data || [];
            setExchanges(data);
            if (data.length > 0) setSelectedExchangeId(prev => prev || data[0].id);
        } catch (err) {
            if (err.name === 'AbortError' || err.name === 'CanceledError' || err.code === 'ERR_CANCELED') return;
            console.error("Error loading exchanges", err);
            setError("No se pudo conectar con el servidor Backend (puerto 5000). Asegúrate de que el servicio esté ejecutándose.");
        } finally {
            if (!(isSignal && signal.aborted)) setLoading(false);
        }
    };

    useEffect(() => {
        const controller = new AbortController();
        fetchExchanges(controller.signal);
        return () => controller.abort();
    }, []);

    const selectedEx = exchanges.find(e => e.id === selectedExchangeId);

    const handleCreateExchange = async () => {
        if (!newExchangeName.trim()) return;
        try {
            await axios.post(`${config.API_URL}/api/exchanges`, {
                name: newExchangeName,
                mapping: {
                    fecha: 'Fecha',
                    tipo_operacion: 'Tipo',
                    moneda: 'Moneda',
                    monto_compra_cripto: 'Compra',
                    monto_venta_cripto: 'Venta',
                    cotizacion_compra: 'Cotizacion Compra',
                    cotizacion_venta: 'Cotizacion Venta',
                    monto_ars: 'Monto ARS',
                    comentarios: 'Notas'
                }
            });
            setNewExchangeName('');
            setShowAddModal(false);
            fetchExchanges();
        } catch {
            alert("Error al crear el exchange");
        }
    };

    const handleDeleteExchange = async (id) => {
        if (!window.confirm("¿Seguro que deseas eliminar este exchange?")) return;
        try {
            await axios.delete(`${config.API_URL}/api/exchanges/${id}`);
            setSelectedExchangeId('');
            fetchExchanges();
        } catch {
            alert("Error al eliminar el exchange");
        }
    };

    const handleUpdateMappingField = async (field, value) => {
        if (!selectedEx) return;
        setSaving(true);
        const updatedMapping = { ...selectedEx.mapping, [field]: value };
        try {
            await axios.put(`${config.API_URL}/api/exchanges/${selectedEx.id}/mapping`, {
                mapping: updatedMapping,
                dateFormat: selectedEx.dateFormat
            });
            setExchanges(exchanges.map(e => e.id === selectedEx.id ? { ...e, mapping: updatedMapping } : e));
        } catch {
            alert("Error guardando mapeo");
        }
        setSaving(false);
    };

    const handleUpdateDateFormat = async (dateFormat) => {
        if (!selectedEx) return;
        setSaving(true);
        try {
            await axios.put(`${config.API_URL}/api/exchanges/${selectedEx.id}/mapping`, {
                mapping: selectedEx.mapping,
                dateFormat
            });
            setExchanges(exchanges.map(e => e.id === selectedEx.id ? { ...e, dateFormat } : e));
        } catch {
            alert("Error guardando formato de fecha");
        }
        setSaving(false);
    };

    if (loading) {
        return (
            <div style={{ color: '#94A3B8', padding: '3rem', textAlign: 'center', fontSize: '14px' }}>
                Cargando configuración de esquemas y mapeos...
            </div>
        );
    }

    return (
        <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.35rem' }}>
                        <h2 style={{ color: '#F8FAFC', fontSize: '1.75rem', fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                            Esquemas y Mapeos de Ingesta
                        </h2>
                        <span className="badge-indigo" style={{ padding: '0.2rem 0.6rem', fontSize: '11px', fontWeight: 600 }}>
                            Parser v2.0
                        </span>
                    </div>
                    <p style={{ color: '#94A3B8', margin: 0, fontSize: '14px' }}>
                        Normalización de columnas, formatos de fecha y equivalencias contables por exchange.
                    </p>
                </div>
                <button className="btn-primary" style={{ padding: '0.65rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '13px' }} onClick={() => setShowAddModal(true)}>
                    <Plus size={16} /> AGREGAR EXCHANGE
                </button>
            </div>

            {error && (
                <div style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', color: '#FB7185', padding: '1rem 1.25rem', borderRadius: '8px', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}><AlertTriangle size={18} color="#F43F5E" /><span style={{ fontSize: '14px' }}>{error}</span></div>
                    <button onClick={fetchExchanges} className="btn-secondary" style={{ padding: '0.4rem 0.9rem', fontSize: '12px' }}>Reintentar</button>
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1.5rem' }}>
                <div className="card-surface" style={{ padding: '1rem', height: 'fit-content' }}>
                    <div style={{ color: '#64748B', fontSize: '11px', fontWeight: 700, letterSpacing: '0.05em', marginBottom: '0.75rem', textTransform: 'uppercase', padding: '0 0.5rem' }}>
                        Plataformas Configuradas
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                        {exchanges.map(ex => {
                            const isSelected = selectedExchangeId === ex.id;
                            return (
                                <button
                                    key={ex.id} onClick={() => setSelectedExchangeId(ex.id)}
                                    style={{
                                        background: isSelected ? 'rgba(79, 70, 229, 0.15)' : 'transparent', color: isSelected ? '#F8FAFC' : '#94A3B8',
                                        border: `1px solid ${isSelected ? 'rgba(79, 70, 229, 0.35)' : 'transparent'}`,
                                        borderLeft: isSelected ? '3px solid #4F46E5' : '1px solid transparent',
                                        padding: '0.65rem 0.85rem', textAlign: 'left', borderRadius: '6px', cursor: 'pointer',
                                        fontWeight: isSelected ? 600 : 500, fontSize: '13px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'all 0.15s ease'
                                    }}
                                >
                                    <span>{ex.name}</span>
                                    <span style={{ fontSize: '10px', fontWeight: 600, padding: '0.15rem 0.4rem', borderRadius: '4px', background: isSelected ? 'rgba(79, 70, 229, 0.25)' : 'rgba(255,255,255,0.04)', color: isSelected ? '#A5B4FC' : '#64748B' }}>{ex.type}</span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {selectedEx ? (
                    <div className="card-surface" style={{ padding: '1.75rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                            <div>
                                <h3 style={{ fontSize: '1.35rem', fontWeight: 700, margin: 0, color: '#F8FAFC' }}>Esquema: <span style={{ color: '#818CF8' }}>{selectedEx.name}</span></h3>
                                <p style={{ fontSize: '12px', color: '#64748B', margin: '0.2rem 0 0 0' }}>Modo de Integración: {selectedEx.type}</p>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                {saving && <span style={{ color: '#34D399', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '0.35rem' }}><Save size={13} /> Guardando cambios...</span>}
                                {selectedEx.type === 'CUSTOM_CSV' && (
                                    <button onClick={() => handleDeleteExchange(selectedEx.id)} style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.25)', color: '#FB7185', padding: '0.4rem 0.8rem', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '12px', fontWeight: 500 }}>
                                        <Trash2 size={13} /> Eliminar Perfil
                                    </button>
                                )}
                            </div>
                        </div>

                        <SettingsIntegritySection selectedEx={selectedEx} defaultFields={DEFAULT_MAPPING_FIELDS} handleUpdateDateFormat={handleUpdateDateFormat} handleUpdateMappingField={handleUpdateMappingField} />
                        <SettingsDangerZone selectedEx={selectedEx} onDeleteExchange={handleDeleteExchange} showAddModal={showAddModal} setShowAddModal={setShowAddModal} newExchangeName={newExchangeName} setNewExchangeName={setNewExchangeName} handleCreateExchange={handleCreateExchange} />
                    </div>
                ) : (
                    <div className="card-surface" style={{ padding: '3rem', textAlign: 'center', color: '#94A3B8', fontSize: '14px' }}>
                        Selecciona una plataforma del panel izquierdo para configurar sus mapeos o agrega un nuevo perfil.
                        <SettingsDangerZone selectedEx={null} onDeleteExchange={handleDeleteExchange} showAddModal={showAddModal} setShowAddModal={setShowAddModal} newExchangeName={newExchangeName} setNewExchangeName={setNewExchangeName} handleCreateExchange={handleCreateExchange} />
                    </div>
                )}
            </div>
        </div>
    );
}

export default Settings;
