import React, { useState } from 'react';
import { X, Download, FileSpreadsheet, FileText, FileCode, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { DateRangePicker } from './DateRangePicker';
import { apiClient } from '../../services/apiClient';

/**
 * ExportModal — Modal unificado de exportación oficial (Excel, PDF membretado B+V, CSV).
 */
export function ExportModal({ isOpen, onClose, defaultModulo = 'PRESTAMOS' }) {
  const [modulo, setModulo] = useState(defaultModulo);
  const [formato, setFormato] = useState('excel'); // 'excel' | 'pdf' | 'csv'
  const [estado, setEstado] = useState('TODOS');
  const [dates, setDates] = useState({
    fechaInicio: '2026-01-01',
    fechaFin: new Date().toISOString().split('T')[0],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const handleDescargar = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const blob = await apiClient.exportarArchivo({
        modulo,
        formato,
        fechaInicio: dates.fechaInicio,
        fechaFin: dates.fechaFin,
        estado: estado === 'TODOS' ? undefined : estado,
      });

      // Determinar extensión del archivo
      const extensiones = {
        excel: 'xlsx',
        pdf: 'pdf',
        csv: 'csv',
      };
      const extension = extensiones[formato] || 'txt';
      const filename = `Reporte_${modulo}_${dates.fechaInicio}_al_${dates.fechaFin}.${extension}`;

      // Crear URL de descarga y simular clic
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
      }, 1500);
    } catch (err) {
      console.error('[ExportModal] Error en descarga:', err);
      setError(err.message || 'No se pudo generar el archivo solicitado');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-white dark:bg-valle-darkSurface rounded-2xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
        {/* Header con Paleta Catamarca */}
        <div className="bg-valle-blue dark:bg-valle-darkElevated px-6 py-4 flex items-center justify-between text-white border-b border-valle-blue/20 dark:border-valle-darkBorder">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-valle-orange/20 flex items-center justify-center">
              <Download className="w-5 h-5 text-valle-orange" />
            </div>
            <h3 className="font-display font-bold text-base tracking-wide text-white">
              Centro de Exportación de Datos
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Contenido */}
        <div className="p-6 space-y-5">
          {/* Selector de Módulo */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
              Módulo de Información
            </label>
            <select
              value={modulo}
              onChange={(e) => setModulo(e.target.value)}
              className="w-full text-sm px-3.5 py-2.5 border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-800 dark:text-slate-100 bg-white dark:bg-valle-darkElevated"
            >
              <option value="PRESTAMOS">Cartera de Préstamos y Cobranzas</option>
              <option value="PLAZOS_FIJOS">Depósitos a Plazo Fijo</option>
              <option value="FLEXIBLES">Cuentas Flexibles y Rendimientos</option>
              <option value="BALANCE">Balance General, Solvencia y Encajes</option>
            </select>
          </div>

          {/* Formato de Descarga */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
              Formato de Archivo
            </label>
            <div className="grid grid-cols-3 gap-3">
              <button
                type="button"
                onClick={() => setFormato('excel')}
                className={`p-3.5 rounded-xl border flex flex-col items-center gap-2 transition text-xs font-semibold ${
                  formato === 'excel'
                    ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 ring-2 ring-emerald-400'
                    : 'border-slate-200 dark:border-valle-darkBorder hover:bg-slate-50 dark:hover:bg-valle-darkElevated text-slate-600 dark:text-slate-400'
                }`}
              >
                <FileSpreadsheet className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                <span>Excel (.xlsx)</span>
              </button>

              <button
                type="button"
                onClick={() => setFormato('pdf')}
                className={`p-3.5 rounded-xl border flex flex-col items-center gap-2 transition text-xs font-semibold ${
                  formato === 'pdf'
                    ? 'border-red-500 bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 ring-2 ring-red-400'
                    : 'border-slate-200 dark:border-valle-darkBorder hover:bg-slate-50 dark:hover:bg-valle-darkElevated text-slate-600 dark:text-slate-400'
                }`}
              >
                <FileText className="w-6 h-6 text-red-600 dark:text-red-400" />
                <span>PDF Membretado</span>
              </button>

              <button
                type="button"
                onClick={() => setFormato('csv')}
                className={`p-3.5 rounded-xl border flex flex-col items-center gap-2 transition text-xs font-semibold ${
                  formato === 'csv'
                    ? 'border-valle-blue bg-blue-50 dark:bg-blue-950/40 text-valle-blue dark:text-blue-300 ring-2 ring-valle-blue'
                    : 'border-slate-200 dark:border-valle-darkBorder hover:bg-slate-50 dark:hover:bg-valle-darkElevated text-slate-600 dark:text-slate-400'
                }`}
              >
                <FileCode className="w-6 h-6 text-valle-blue dark:text-blue-400" />
                <span>CSV Analítico</span>
              </button>
            </div>
          </div>

          {/* Selector de Fechas (DateRangePicker) */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
              Rango Temporal
            </label>
            <DateRangePicker
              fechaInicio={dates.fechaInicio}
              fechaFin={dates.fechaFin}
              onChange={setDates}
            />
          </div>

          {/* Filtro por Estado */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
              Estado de los Registros
            </label>
            <div className="flex gap-2">
              {['TODOS', 'ACTIVOS', 'VENCIDOS', 'EN_MORA'].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setEstado(st)}
                  className={`flex-1 py-2 text-xs font-bold rounded-xl border transition ${
                    estado === st
                      ? 'bg-valle-blue dark:bg-valle-orange text-white border-valle-blue dark:border-valle-orange shadow-xs'
                      : 'border-slate-200 dark:border-valle-darkBorder text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  {st.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Mensajes de Alerta */}
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 text-red-700 dark:text-red-300 text-xs sm:text-sm rounded-xl flex items-center gap-2 font-medium">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-200 text-xs sm:text-sm rounded-xl flex items-center gap-2 font-medium">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
              <span>¡Archivo generado con éxito! Iniciando descarga...</span>
            </div>
          )}
        </div>

        {/* Footer de Acciones */}
        <div className="px-6 py-4 bg-slate-50 dark:bg-valle-darkElevated border-t border-slate-200 dark:border-valle-darkBorder flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white transition"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleDescargar}
            disabled={loading}
            className="px-5 py-2.5 bg-valle-orange hover:bg-valle-orangedark text-white text-xs sm:text-sm font-bold rounded-xl shadow-md flex items-center gap-2 transition disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Generando...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                <span>Descargar {formato.toUpperCase()}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ExportModal;
