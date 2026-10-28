import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  Search,
  Filter,
  Download,
  X,
  User,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  FileSpreadsheet,
  FileText,
  Loader2,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react';
import { apiClient } from '../../services/apiClient';
import { simSocket } from '../../services/simSocket';

/**
 * UsersModal — Visor Modal del Padrón Central de Clientes (Individuos & Empresas).
 * Soporta paginación 1/100, filtros de antigüedad, búsqueda en tiempo real y descarga oficial.
 */
export function UsersModal({ isOpen, onClose }) {
  const [usuarios, setUsuarios] = useState([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [totalPaginas, setTotalPaginas] = useState(1);
  const [limite, setLimite] = useState(10);

  // Filtros
  const [tipo, setTipo] = useState('TODOS'); // 'TODOS' | 'INDIVIDUO' | 'EMPRESA'
  const [estado, setEstado] = useState('TODOS');
  const [busqueda, setBusqueda] = useState('');
  const [busquedaDebounced, setBusquedaDebounced] = useState('');
  const [orden, setOrden] = useState('recientes'); // 'recientes' | 'antiguos' | 'mayor_saldo' | 'menor_saldo'

  const [loading, setLoading] = useState(false);
  const [exportando, setExportando] = useState(null); // 'csv' | 'excel' | null

  // Debounce para búsqueda
  useEffect(() => {
    const timer = setTimeout(() => {
      setBusquedaDebounced(busqueda);
      setPagina(1);
    }, 280);
    return () => clearTimeout(timer);
  }, [busqueda]);

  const cargarUsuarios = useCallback(async () => {
    if (!isOpen) return;
    setLoading(true);
    try {
      const data = await apiClient.getUsuarios({
        page: pagina,
        limit: limite,
        tipo: tipo !== 'TODOS' ? tipo : undefined,
        estado: estado !== 'TODOS' ? estado : undefined,
        busqueda: busquedaDebounced || undefined,
        orden,
      });
      if (data && Array.isArray(data.usuarios)) {
        setUsuarios(data.usuarios);
        setTotal(data.total || 0);
        setTotalPaginas(data.total_paginas || 1);
      }
    } catch (err) {
      console.error('[UsersModal] Error al cargar usuarios:', err);
    } finally {
      setLoading(false);
    }
  }, [isOpen, pagina, limite, tipo, estado, busquedaDebounced, orden]);

  useEffect(() => {
    cargarUsuarios();
  }, [cargarUsuarios]);

  // Actualización reactiva con WebSocket en vivo (nuevo usuario registrado o avance del reloj)
  useEffect(() => {
    if (!isOpen) return;
    const unsubscribe = simSocket.subscribe((msg) => {
      if (
        msg.tipo === 'TICK' ||
        msg.tipo === 'TICK_DIARIO' ||
        msg.tipo === 'BALANCE_ACTUALIZADO' ||
        msg.tipo === 'RESET' ||
        msg.tipo === 'NUEVO_CLIENTE'
      ) {
        cargarUsuarios();
      }
    });
    return () => unsubscribe();
  }, [isOpen, cargarUsuarios]);

  // Cerrar con tecla Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleDescargar = async (formato) => {
    setExportando(formato);
    try {
      const blob = await apiClient.exportarUsuarios(formato);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `padron_clientes_valle_${new Date().toISOString().slice(0, 10)}.${formato === 'excel' ? 'xlsx' : 'csv'}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('[UsersModal] Error al exportar:', err);
      alert('Error descargando el archivo: ' + err.message);
    } finally {
      setExportando(null);
    }
  };

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-fade-in">
      <div className="w-full max-w-6xl max-h-[92vh] flex flex-col bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder rounded-3xl shadow-2xl overflow-hidden transition-colors duration-200">
        
        {/* ENCABEZADO DEL MODAL */}
        <div className="px-6 py-4.5 border-b border-slate-200 dark:border-valle-darkBorder flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/70 dark:bg-valle-darkElevated/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-valle-orange/15 text-valle-orange flex items-center justify-center flex-shrink-0 shadow-xs">
              <Users className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-display font-extrabold text-lg sm:text-xl text-slate-900 dark:text-white">
                  Padrón Central de Clientes & Empresas
                </h3>
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-400/30 text-[10px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>En Vivo</span>
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Consulta integral de cuentas transaccionales, saldos, líneas activas y antigüedad.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={exportando !== null}
              onClick={() => handleDescargar('excel')}
              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
              title="Descargar Padrón completo en formato Excel (.xlsx)"
            >
              {exportando === 'excel' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5" />}
              <span>Excel</span>
            </button>

            <button
              type="button"
              disabled={exportando !== null}
              onClick={() => handleDescargar('csv')}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-valle-darkElevated dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-valle-darkBorder rounded-xl text-xs font-bold transition flex items-center gap-1.5"
              title="Descargar Padrón completo en CSV"
            >
              {exportando === 'csv' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
              <span>CSV</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-200/60 dark:hover:bg-white/10 rounded-xl transition"
              title="Cerrar (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* BARRA DE FILTROS Y BÚSQUEDA */}
        <div className="p-4 border-b border-slate-200 dark:border-valle-darkBorder bg-white dark:bg-valle-darkSurface flex flex-wrap items-center justify-between gap-3 text-xs">
          {/* Buscador */}
          <div className="relative flex-1 min-w-[220px] max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 transform -translate-y-1/2" />
            <input
              type="text"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar por Nombre, DNI, CUIT, Email o Alias..."
              className="w-full pl-9 pr-8 py-2 rounded-xl bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-valle-orange/50 text-xs font-medium"
            />
            {busqueda && (
              <button
                type="button"
                onClick={() => setBusqueda('')}
                className="absolute right-2.5 top-1/2 transform -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-white"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Selectores de Segmento, Estado y Orden */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Segmento */}
            <div className="flex items-center bg-slate-100 dark:bg-valle-darkElevated p-0.5 rounded-xl border border-slate-200 dark:border-valle-darkBorder">
              {['TODOS', 'INDIVIDUO', 'EMPRESA'].map((seg) => (
                <button
                  key={seg}
                  type="button"
                  onClick={() => {
                    setTipo(seg);
                    setPagina(1);
                  }}
                  className={`px-2.5 py-1.5 rounded-lg font-bold transition text-[11px] ${
                    tipo === seg
                      ? 'bg-white dark:bg-valle-blue text-valle-blue dark:text-white shadow-2xs'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {seg === 'TODOS' ? 'Todos' : seg === 'INDIVIDUO' ? 'Individuos' : 'Empresas'}
                </button>
              ))}
            </div>

            {/* Estado */}
            <select
              value={estado}
              onChange={(e) => {
                setEstado(e.target.value);
                setPagina(1);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder text-slate-700 dark:text-slate-200 font-semibold focus:outline-none"
            >
              <option value="TODOS">Todos los Estados</option>
              <option value="ACTIVO">Activos</option>
              <option value="PENDIENTE_DOCS">Pendientes Docs</option>
              <option value="BAJA_SOLICITADA">Baja Solicitada</option>
              <option value="SUSPENDIDO_AML">Suspendidos AML</option>
              <option value="CERRADO">Cerrados</option>
            </select>

            {/* Orden */}
            <select
              value={orden}
              onChange={(e) => {
                setOrden(e.target.value);
                setPagina(1);
              }}
              className="px-2.5 py-1.5 rounded-xl bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder text-slate-700 dark:text-slate-200 font-semibold focus:outline-none"
            >
              <option value="recientes">Más Recientes (Nuevas Altas)</option>
              <option value="antiguos">Más Antiguos (Antigüedad)</option>
              <option value="mayor_saldo">Mayor Saldo en Cuenta</option>
              <option value="menor_saldo">Menor Saldo en Cuenta</option>
            </select>

            <button
              type="button"
              onClick={cargarUsuarios}
              className="p-2 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white rounded-xl hover:bg-slate-100 dark:hover:bg-valle-darkElevated transition"
              title="Recargar datos"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* TABLA PRINCIPAL CON SCROLL */}
        <div className="flex-1 overflow-auto min-h-[320px]">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="sticky top-0 z-10 bg-slate-100 dark:bg-valle-darkElevated text-slate-700 dark:text-slate-300 font-extrabold uppercase tracking-wider border-b border-slate-200 dark:border-valle-darkBorder">
              <tr>
                <th className="py-3 px-4">Titular / Razón Social</th>
                <th className="py-3 px-3">Segmento</th>
                <th className="py-3 px-3">Tipo / Actividad</th>
                <th className="py-3 px-3">Estado Cuenta</th>
                <th className="py-3 px-3 text-right">Saldo en Cuenta</th>
                <th className="py-3 px-3">Préstamos Activos</th>
                <th className="py-3 px-3">Fecha Alta</th>
                <th className="py-3 px-4">Alias / CBU</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-valle-darkBorder/60 font-medium">
              {loading && usuarios.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-slate-500">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-valle-orange mb-2" />
                    <span>Consultando base de datos del banco...</span>
                  </td>
                </tr>
              ) : usuarios.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-slate-500 dark:text-slate-400">
                    <Users className="w-8 h-8 mx-auto text-slate-400/50 mb-2" />
                    <span>No se encontraron clientes registrados con los filtros seleccionados.</span>
                  </td>
                </tr>
              ) : (
                usuarios.map((u, idx) => {
                  const esEmpresa = u.tipo_cliente === 'EMPRESA';
                  const tienePrestamo = (u.prestamos_activos ?? 0) > 0;
                  const estadoVal = (u.estado_cliente || 'ACTIVO').toUpperCase();

                  return (
                    <tr
                      key={idx}
                      className="hover:bg-slate-50/80 dark:hover:bg-valle-darkElevated/50 transition"
                    >
                      {/* Titular y DNI/CUIT */}
                      <td className="py-3 px-4">
                        <div className="font-bold text-slate-900 dark:text-white leading-tight">
                          {u.nombre_titular}
                        </div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono mt-0.5">
                          {esEmpresa ? 'CUIT' : 'DNI'}: {u.identificador_fiscal} {u.email_contacto ? `| ${u.email_contacto}` : ''}
                        </div>
                      </td>

                      {/* Segmento */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold ${
                            esEmpresa
                              ? 'bg-valle-blue/15 text-valle-blue dark:bg-sky-500/20 dark:text-sky-300'
                              : 'bg-valle-orange/15 text-valle-orange dark:bg-valle-orange/20 dark:text-amber-300'
                          }`}
                        >
                          {esEmpresa ? <Building2 className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                          <span>{esEmpresa ? 'Empresa' : 'Individuo'}</span>
                        </span>
                      </td>

                      {/* Tipo / Subtipo */}
                      <td className="py-3 px-3">
                        <span className="font-semibold text-slate-700 dark:text-slate-300 truncate max-w-[170px] block" title={u.subtipo_actividad}>
                          {u.tipo_empresa_o_laboral || u.subtipo_actividad || 'General'}
                        </span>
                      </td>

                      {/* Estado */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                            estadoVal === 'ACTIVO'
                              ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border border-emerald-400/30'
                              : estadoVal === 'BAJA_SOLICITADA'
                              ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-400/30'
                              : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-400/30'
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              estadoVal === 'ACTIVO'
                                ? 'bg-emerald-500'
                                : estadoVal === 'BAJA_SOLICITADA'
                                ? 'bg-amber-500'
                                : 'bg-rose-500'
                            }`}
                          />
                          <span>{estadoVal.replace('_', ' ')}</span>
                        </span>
                      </td>

                      {/* Saldo en Cuenta */}
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <span className="font-mono font-bold text-slate-900 dark:text-white tabular-nums">
                          {formatearPesos(u.saldo_cuenta)}
                        </span>
                        {u.es_cuenta_sueldo === 1 && (
                          <span className="block text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            Caja Sueldo
                          </span>
                        )}
                      </td>

                      {/* Préstamos */}
                      <td className="py-3 px-3 whitespace-nowrap">
                        {tienePrestamo ? (
                          <div>
                            <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300 font-bold">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>{u.prestamos_activos} Activo ({formatearPesos(u.monto_prestamos)})</span>
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-500 text-[11px]">
                            Sin préstamos
                          </span>
                        )}
                      </td>

                      {/* Fecha de Registro / Antigüedad */}
                      <td className="py-3 px-3 text-slate-600 dark:text-slate-400 whitespace-nowrap font-mono text-[11px]">
                        {u.fecha_registro || '2026-10-26'}
                      </td>

                      {/* Alias / CBU */}
                      <td className="py-3 px-4 whitespace-nowrap">
                        <div className="font-mono text-slate-700 dark:text-slate-300 font-bold truncate max-w-[130px]" title={u.alias}>
                          {u.alias || '—'}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 truncate max-w-[130px]" title={u.cbu}>
                          {u.cbu ? `CBU: ...${u.cbu.slice(-6)}` : ''}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* PIE DE TABLA Y PAGINACIÓN 1/100 */}
        <div className="px-6 py-3.5 border-t border-slate-200 dark:border-valle-darkBorder flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/70 dark:bg-valle-darkElevated/60 text-xs">
          <div className="text-slate-600 dark:text-slate-400">
            Mostrando <strong className="text-slate-900 dark:text-white">{usuarios.length}</strong> de{' '}
            <strong className="text-slate-900 dark:text-white">{total}</strong> clientes registrados | Página{' '}
            <strong className="text-slate-900 dark:text-white">{pagina}</strong> de{' '}
            <strong className="text-slate-900 dark:text-white">{totalPaginas}</strong>
          </div>

          <div className="flex items-center gap-3">
            {/* Selector de cantidad por página */}
            <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
              <span>Filas:</span>
              <select
                value={limite}
                onChange={(e) => {
                  setLimite(Number(e.target.value));
                  setPagina(1);
                }}
                className="px-2 py-1 bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder rounded-lg font-bold text-slate-700 dark:text-slate-200"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>

            {/* Controles de página */}
            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={pagina <= 1}
                onClick={() => setPagina(1)}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-valle-darkBorder bg-white dark:bg-valle-darkSurface disabled:opacity-30 disabled:pointer-events-none hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200"
                title="Primera página"
              >
                <ChevronsLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                disabled={pagina <= 1}
                onClick={() => setPagina((prev) => Math.max(1, prev - 1))}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-valle-darkBorder bg-white dark:bg-valle-darkSurface disabled:opacity-30 disabled:pointer-events-none hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200"
                title="Página anterior"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <span className="px-3 py-1 font-mono font-bold bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder rounded-lg text-valle-orange">
                {pagina} / {totalPaginas}
              </span>

              <button
                type="button"
                disabled={pagina >= totalPaginas}
                onClick={() => setPagina((prev) => Math.min(totalPaginas, prev + 1))}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-valle-darkBorder bg-white dark:bg-valle-darkSurface disabled:opacity-30 disabled:pointer-events-none hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200"
                title="Página siguiente"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                disabled={pagina >= totalPaginas}
                onClick={() => setPagina(totalPaginas)}
                className="p-1.5 rounded-lg border border-slate-200 dark:border-valle-darkBorder bg-white dark:bg-valle-darkSurface disabled:opacity-30 disabled:pointer-events-none hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200"
                title="Última página"
              >
                <ChevronsRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

export default UsersModal;
