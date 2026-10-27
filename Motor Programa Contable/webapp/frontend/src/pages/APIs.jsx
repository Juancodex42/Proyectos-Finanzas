import { useState, useEffect, useCallback } from 'react';
import { Plug, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';
import config from '../config';
import ApiExchangeCard from '../components/apis/ApiExchangeCard';

const DEFAULT_API_EXCHANGES = [
    { id: 'binance', name: 'Binance', keyName: 'BINANCE_API_KEY', secretName: 'BINANCE_API_SECRET', statusKey: 'binance' },
    { id: 'bitso', name: 'Bitso', keyName: 'BITSO_API_KEY', secretName: 'BITSO_API_SECRET', statusKey: 'bitso' },
    { id: 'ripio_trade', name: 'Ripio Trade', keyName: 'RIPIO_API_KEY', secretName: 'RIPIO_API_SECRET', statusKey: 'ripio_trade' },
    { id: 'okx', name: 'OKX', keyName: 'OKX_API_KEY', secretName: 'OKX_API_SECRET', statusKey: 'okx', needsPassword: true },
    { id: 'bybit', name: 'Bybit', keyName: 'BYBIT_API_KEY', secretName: 'BYBIT_API_SECRET', statusKey: 'bybit' },
    { id: 'bitget', name: 'Bitget', keyName: 'BITGET_API_KEY', secretName: 'BITGET_API_SECRET', statusKey: 'bitget', needsPassword: true }
];

function APIs() {
    const [envKeys, setEnvKeys] = useState({});
    const [apiStatuses, setApiStatuses] = useState({});
    const [bgSyncEnabled, setBgSyncEnabled] = useState(false);
    const [editingEx, setEditingEx] = useState(null);
    const [formData, setFormData] = useState({ key: '', secret: '', password: '' });
    const [syncing, setSyncing] = useState(false);
    const [statusLoading, setStatusLoading] = useState(true);
    const [syncResults, setSyncResults] = useState(null);
    const [serverError, setServerError] = useState(null);

    const [dynamicExchanges, setDynamicExchanges] = useState(DEFAULT_API_EXCHANGES);

    const loadKeys = useCallback(async (forceStatusRefresh = false) => {
        if (forceStatusRefresh) {
            setStatusLoading(true);
        }
        setServerError(null);
        try {
            const [envRes, schRes, exRes] = await Promise.all([
                axios.get(`${config.API_URL}/api/env`),
                axios.get(`${config.API_URL}/api/scheduler/status`).catch(() => ({ data: { enabled: false } })),
                axios.get(`${config.API_URL}/api/exchanges`)
            ]);
            setEnvKeys(envRes.data || {});
            setBgSyncEnabled(schRes.data ? schRes.data.enabled : false);

            const fetched = exRes.data || [];
            if (fetched.length > 0) {
                const customApiExchanges = fetched.filter(ex => ex.type === 'CUSTOM_API').map(ex => ({
                    id: ex.id,
                    name: ex.name,
                    keyName: `${ex.id.toUpperCase()}_API_KEY`,
                    secretName: `${ex.id.toUpperCase()}_API_SECRET`,
                    statusKey: ex.id
                }));
                setDynamicExchanges([...DEFAULT_API_EXCHANGES, ...customApiExchanges]);
            } else {
                setDynamicExchanges(DEFAULT_API_EXCHANGES);
            }

            const statusUrl = forceStatusRefresh 
                ? `${config.API_URL}/api/status?refresh=true` 
                : `${config.API_URL}/api/status`;
            const statusRes = await axios.get(statusUrl);
            setApiStatuses(statusRes.data || {});
        } catch (err) {
            console.error("Error cargando configuración", err);
            setServerError("No se pudo conectar con el backend local. Asegúrate de que el servidor Flask esté corriendo en el puerto 5000.");
        } finally {
            setStatusLoading(false);
        }
    }, []);

    useEffect(() => {
        loadKeys();
    }, [loadKeys]);

    const handleSaveKey = async (ex) => {
        if (!formData.key?.trim() || !formData.secret?.trim()) {
            alert("Completa los campos requeridos");
            return;
        }

        const payload = {
            [ex.keyName]: formData.key,
            [ex.secretName]: formData.secret
        };

        if (ex.needsPassword && formData.password) {
            payload[`${ex.id.toUpperCase()}_API_PASSWORD`] = formData.password;
        }

        try {
            await axios.post(`${config.API_URL}/api/env`, payload);
            alert(`Credenciales de ${ex.name} guardadas con éxito.`);
            setEditingEx(null);
            setFormData({ key: '', secret: '', password: '' });
            await loadKeys(true);
        } catch (err) {
            console.error("Error guardando credenciales", err);
            alert("Error al guardar credenciales en el archivo .env.");
        }
    };

    const handleToggleScheduler = async () => {
        try {
            const nextState = !bgSyncEnabled;
            await axios.post(`${config.API_URL}/api/scheduler/toggle`, { enabled: nextState });
            setBgSyncEnabled(nextState);
        } catch (err) {
            console.error("Error alternando programador de sincronización", err);
            alert("Error al cambiar el estado de sincronización en segundo plano.");
        }
    };

    const handleSyncNow = async () => {
        setSyncing(true);
        setSyncResults(null);
        try {
            const res = await axios.post(`${config.API_URL}/api/sync`);
            setSyncResults(res.data);
            await loadKeys(true);
        } catch (err) {
            console.error("Error durante sincronización", err);
            alert("Ocurrió un error al sincronizar con los exchanges.");
        } finally {
            setSyncing(false);
        }
    };

    return (
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '1.75rem 2rem', color: 'var(--text-primary)' }}>
            {/* Header */}
            <header style={{ marginBottom: '1.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                        <div style={{
                            width: '36px',
                            height: '36px',
                            borderRadius: 'var(--radius-md)',
                            background: 'var(--brand-indigo-subtle)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            border: '1px solid var(--brand-indigo-border)'
                        }}>
                            <Plug size={18} color="var(--brand-indigo-light)" />
                        </div>
                        <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#F8FAFC', margin: 0, letterSpacing: '-0.02em' }}>
                            Conexión de APIs & Sincronización
                        </h1>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', margin: '0.25rem 0 0 0', fontSize: '0.88rem', paddingLeft: '2.85rem' }}>
                        Conecta tus exchanges mediante API Keys seguras de solo lectura para extraer órdenes y depósitos automáticamente.
                    </p>
                </div>

                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <button
                        onClick={() => loadKeys(true)}
                        className="btn-secondary"
                        disabled={statusLoading}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', padding: '0.5rem 0.9rem' }}
                    >
                        <RefreshCw size={14} className={statusLoading ? "spin" : ""} />
                        <span>Verificar Estado</span>
                    </button>
                    <button
                        onClick={handleSyncNow}
                        className="btn-primary"
                        disabled={syncing}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', padding: '0.5rem 1rem' }}
                    >
                        <RefreshCw size={14} className={syncing ? "spin" : ""} />
                        <span>{syncing ? 'Sincronizando...' : 'Sincronizar Todo Ahora'}</span>
                    </button>
                </div>
            </header>

            {serverError && (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--accent-rose-border)', borderRadius: 'var(--radius-md)', padding: '1rem 1.25rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <AlertCircle size={20} color="#FB7185" style={{ flexShrink: 0 }} />
                    <span style={{ fontSize: '13px', color: '#FCA5A5' }}>{serverError}</span>
                </div>
            )}

            {/* SYNC RESULTS MODAL / BANNER */}
            {syncResults && (
                <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--accent-emerald-border)', borderRadius: 'var(--radius-md)', padding: '1rem 1.25rem', marginBottom: '1.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.6rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <CheckCircle size={18} color="#34D399" />
                            <h4 style={{ margin: 0, color: '#34D399', fontSize: '14px', fontWeight: 700 }}>Resumen de Sincronización</h4>
                        </div>
                        <span style={{ fontSize: '12px', color: '#A7F3D0', fontWeight: 600 }}>
                            +{syncResults.total_inserted || 0} nuevas insertadas, {syncResults.total_skipped || 0} omitidas
                        </span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', fontSize: '12px' }}>
                        {(Array.isArray(syncResults.details) ? syncResults.details : []).map((item, idx) => (
                            <div key={item.exchange || idx} style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem 0.75rem', borderRadius: '4px' }}>
                                <strong style={{ color: '#F8FAFC' }}>{item.exchange}: </strong>
                                <span style={{ color: item.message === 'Success' ? '#34D399' : '#FB7185' }}>
                                    {item.message === 'Success' ? `${item.count || 0} leídas` : (item.message || 'Error')}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* BACKGROUND SYNC TOGGLE PANEL */}
            <div className="card-surface" style={{ padding: '1.25rem', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 700, color: '#F8FAFC' }}>
                        Sincronización Automática en Segundo Plano
                    </h3>
                    <p style={{ margin: '0.2rem 0 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Ejecuta un ciclo de extracción automático cada hora mientras la aplicación esté abierta.
                    </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span style={{ fontSize: '12px', fontWeight: 600, color: bgSyncEnabled ? '#34D399' : 'var(--text-muted)' }}>
                        {bgSyncEnabled ? 'ACTIVA (Cada 1h)' : 'DESACTIVADA'}
                    </span>
                    <button
                        onClick={handleToggleScheduler}
                        className={bgSyncEnabled ? "btn-secondary" : "btn-primary"}
                        style={{ padding: '0.45rem 0.9rem', fontSize: '12px' }}
                    >
                        {bgSyncEnabled ? 'Pausar' : 'Activar'}
                    </button>
                </div>
            </div>

            {/* EXCHANGES CARDS LIST */}
            <div style={{ display: 'grid', gap: '1.25rem' }}>
                {dynamicExchanges.map((ex) => (
                    <ApiExchangeCard
                        key={ex.id}
                        ex={ex}
                        envKeys={envKeys}
                        apiStatuses={apiStatuses}
                        statusLoading={statusLoading}
                        isEditing={editingEx === ex.id}
                        setEditingEx={setEditingEx}
                        formData={formData}
                        setFormData={setFormData}
                        handleSaveKey={handleSaveKey}
                    />
                ))}
            </div>
        </div>
    );
}

export default APIs;
