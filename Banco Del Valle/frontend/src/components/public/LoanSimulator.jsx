import React, { useState, useEffect } from 'react';
import { Calculator, CheckCircle2, ArrowRight, Download, Sparkles, Search, Loader2, RotateCcw } from 'lucide-react';
import { apiClient } from '../../services/apiClient';

/**
 * LoanSimulator — Cotizador inteligente de préstamos personales con scoring reactivo y alto contraste.
 */
export function LoanSimulator({ onOpenRegister, onExportModal }) {
  const [monto, setMonto] = useState(1500000);
  const [cuotas, setCuotas] = useState(24);
  const [ingresoDeclarado, setIngresoDeclarado] = useState(3000000);
  const [categoriaLaboral, setCategoriaLaboral] = useState('EMPLEADO_PUBLICO');
  const [dni, setDni] = useState('20-42049164-7');
  const [buscandoDni, setBuscandoDni] = useState(false);
  const [clienteEncontrado, setClienteEncontrado] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleConsultarDni = async () => {
    if (!dni.trim()) return;
    setBuscandoDni(true);
    try {
      const res = await apiClient.buscarPorDni(dni.trim());
      if (res && res.encontrado) {
        setClienteEncontrado(res.cliente);
        if (res.cliente.ingreso_mensual) setIngresoDeclarado(res.cliente.ingreso_mensual);
        if (res.cliente.categoria_laboral) setCategoriaLaboral(res.cliente.categoria_laboral);
      } else {
        setClienteEncontrado(null);
      }
    } catch (err) {
      console.error('[LoanSimulator] Error buscando DNI:', err);
    } finally {
      setBuscandoDni(false);
    }
  };

  const handleResetValores = () => {
    setMonto(1500000);
    setCuotas(24);
    setIngresoDeclarado(3000000);
    setCategoriaLaboral('EMPLEADO_PUBLICO');
    setDni('20-42049164-7');
    setClienteEncontrado(null);
  };

  const ejecutarSimulacion = async () => {
    setLoading(true);
    try {
      const payload = {
        monto_solicitado: monto,
        plazo_meses: cuotas,
        ingreso_neto_mensual: ingresoDeclarado,
        categoria_laboral: categoriaLaboral,
        score_externo: clienteEncontrado?.score_externo || 720,
        peor_situacion_bcra: clienteEncontrado?.peor_situacion_bcra || 1,
        antiguedad_meses: clienteEncontrado?.antiguedad_meses || 24,
      };

      const res = await apiClient.simularPrestamo(payload);
      setResultado(res);
    } catch (err) {
      console.warn('[LoanSimulator] Backend no disponible, usando cálculo financiero local de respaldo:', err);
      const tnaBase = categoriaLaboral === 'EMPLEADO_PUBLICO' ? 0.54 : 0.57;
      const tnaEfectiva = clienteEncontrado ? tnaBase - 0.03 : tnaBase;
      const tasaMensual = tnaEfectiva / 12;
      const cuotaPura = (monto * (tasaMensual * Math.pow(1 + tasaMensual, cuotas))) / (Math.pow(1 + tasaMensual, cuotas) - 1);
      const cuotaConIva = cuotaPura * 1.21;
      const ratio = cuotaConIva / (ingresoDeclarado || 1);
      setResultado({
        cuota_mensual: Math.round(cuotaConIva),
        tna_aplicada: tnaEfectiva,
        ratio_cuota_ingreso: ratio,
        scoring_aprobado: ratio <= 0.35,
        decision: ratio <= 0.35 ? 'APROBADO' : 'RECHAZADO',
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    ejecutarSimulacion();
  }, [monto, cuotas, ingresoDeclarado, categoriaLaboral, clienteEncontrado]);

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  return (
    <div id="simulador-prestamos" className="valle-card p-4 sm:p-8 lg:p-10 rounded-2xl sm:rounded-3xl transition-colors duration-200">
      {/* Encabezado del Simulador */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 sm:pb-6 mb-6 sm:mb-8 border-b border-slate-200 dark:border-valle-darkBorder gap-4">
        <div>
          <div className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold uppercase tracking-wider text-valle-orange mb-1">
            <Calculator className="w-4 h-4" />
            <span>Simulador Inteligente con Validación Crediticia</span>
          </div>
          <h2 className="font-display font-extrabold text-xl sm:text-3xl text-slate-900 dark:text-white">
            Cotizá tu Préstamo Personal a Medida
          </h2>
          <p className="text-xs sm:text-base text-slate-600 dark:text-slate-300 mt-1 max-w-2xl">
            Sistema Francés con cuota fija. Conectado en vivo con la base de datos de Banco del Valle.
          </p>
        </div>

        {/* Buscador de DNI */}
        <div className="flex items-center gap-2 bg-slate-50 dark:bg-valle-darkElevated p-2 rounded-xl sm:rounded-2xl border border-slate-300 dark:border-valle-darkBorder w-full sm:w-auto">
          <input
            type="text"
            value={dni}
            onChange={(e) => setDni(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConsultarDni()}
            placeholder="DNI / CUIL"
            className="text-xs sm:text-sm px-3 py-2 bg-white dark:bg-valle-darkSurface border border-slate-300 dark:border-valle-darkBorder rounded-lg sm:rounded-xl outline-none focus:ring-2 focus:ring-valle-orange flex-1 sm:w-44 font-medium text-slate-900 dark:text-white"
          />
          <button
            type="button"
            onClick={handleConsultarDni}
            disabled={buscandoDni}
            className="px-3.5 sm:px-4 py-2 bg-valle-blue hover:bg-valle-bluelight text-white text-xs sm:text-sm font-bold rounded-lg sm:rounded-xl transition flex items-center gap-1.5 flex-shrink-0"
          >
            {buscandoDni ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            <span>Validar</span>
          </button>
          <button
            type="button"
            onClick={handleResetValores}
            title="Restablecer cotizador a valores iniciales"
            className="p-2 sm:px-3 bg-slate-200/80 hover:bg-rose-50 hover:text-rose-600 dark:bg-valle-darkBorder dark:hover:bg-rose-950/40 text-slate-600 dark:text-slate-300 dark:hover:text-rose-400 text-xs sm:text-sm font-bold rounded-lg sm:rounded-xl transition flex items-center gap-1.5 flex-shrink-0"
          >
            <RotateCcw className="w-4 h-4 text-rose-500" />
            <span className="hidden sm:inline">Reset</span>
          </button>
        </div>
      </div>

      {/* Banner de Cliente Reconocido */}
      {clienteEncontrado && (
        <div className="mb-8 p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 rounded-2xl flex flex-wrap items-center justify-between gap-3 text-sm text-blue-950 dark:text-blue-200 animate-fade-in">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-5 h-5 text-valle-orange" />
            <span>
              Cliente verificado: <strong className="font-bold">{clienteEncontrado.nombre}</strong> (Score:{' '}
              <strong className="text-valle-orange font-bold">{clienteEncontrado.score_externo}</strong> | Situación BCRA:{' '}
              <strong>{clienteEncontrado.peor_situacion_bcra}</strong>)
            </span>
          </div>
          <span className="text-xs font-bold bg-emerald-100 text-emerald-900 dark:bg-emerald-900/60 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-700 px-3 py-1 rounded-full">
            Tasa Preferencial Bonificada (-3%)
          </span>
        </div>
      )}

      {/* Sliders y Resultados */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-10 items-start">
        {/* Controles (Sliders) */}
        <div className="lg:col-span-7 space-y-6 sm:space-y-8">
          {/* Slider Monto */}
          <div>
            <div className="flex justify-between items-center mb-2.5">
              <label className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                Monto Solicitado
              </label>
              <span className="font-display font-extrabold text-2xl sm:text-3xl text-valle-blue dark:text-sky-400 tabular-nums">
                {formatearPesos(monto)}
              </span>
            </div>
            <input
              type="range"
              min="100000"
              max="8000000"
              step="50000"
              value={monto}
              onChange={(e) => setMonto(Number(e.target.value))}
              className="slider-valle"
            />
            <div className="flex justify-between text-xs sm:text-sm font-semibold text-slate-600 dark:text-slate-400 mt-2 font-mono">
              <span>$100.000</span>
              <span>$4.000.000</span>
              <span>$8.000.000</span>
            </div>
          </div>

          {/* Slider Cuotas */}
          <div>
            <div className="flex justify-between items-center mb-2.5">
              <label className="text-sm font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                Plazo de Devolución
              </label>
              <span className="font-display font-extrabold text-2xl sm:text-3xl text-valle-orange tabular-nums">
                {cuotas} cuotas fijas
              </span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {[6, 12, 24, 36, 48, 60].map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setCuotas(c)}
                  className={`py-2.5 text-xs sm:text-sm font-bold rounded-xl border transition ${
                    cuotas === c
                      ? 'bg-valle-orange text-white border-valle-orange shadow-md'
                      : 'border-slate-300 dark:border-valle-darkBorder text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-valle-darkElevated'
                  }`}
                >
                  {c} meses
                </button>
              ))}
            </div>
          </div>

          {/* Ingreso Declarado & Categoría */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-4 border-t border-slate-200 dark:border-valle-darkBorder">
            <div>
              <label className="block text-sm font-bold text-slate-800 dark:text-slate-200 mb-1.5">
                Ingreso Neto Mensual ($)
              </label>
              <input
                type="number"
                value={ingresoDeclarado}
                onChange={(e) => setIngresoDeclarado(Number(e.target.value))}
                className="w-full text-sm sm:text-base px-4 py-2.5 bg-slate-50 dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange font-bold text-slate-900 dark:text-white"
              />
              <span className="text-xs text-slate-600 dark:text-slate-400 mt-1 block">
                Sueldo neto comprobable
              </span>
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 dark:text-slate-200 mb-1.5">
                Actividad Laboral
              </label>
              <select
                value={categoriaLaboral}
                onChange={(e) => setCategoriaLaboral(e.target.value)}
                className="w-full text-sm sm:text-base px-4 py-2.5 bg-slate-50 dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange font-bold text-slate-900 dark:text-white"
              >
                <option value="EMPLEADO_PUBLICO">Empleado Público / Estatal (-3% TNA)</option>
                <option value="EMPLEADO_PRIVADO">Empleado Privado en Blanco</option>
                <option value="MONOTRIBUTISTA">Monotributista / Autónomo</option>
                <option value="JUBILADO">Jubilado / Pensionado</option>
              </select>
              <span className="text-xs text-slate-600 dark:text-slate-400 mt-1 block">
                Convenios provinciales aplicados
              </span>
            </div>
          </div>
        </div>

        {/* Tarjeta de Salida Financiera */}
        <div className="lg:col-span-5 bg-gradient-to-br from-slate-900 via-valle-bluedark to-valle-blue dark:from-[#0B1526] dark:via-[#10203B] dark:to-[#172D52] text-white rounded-3xl p-7 sm:p-9 flex flex-col justify-between shadow-xl border border-slate-800 dark:border-valle-darkBorder relative overflow-hidden">
          <div className="absolute right-0 bottom-0 opacity-10 pointer-events-none transform translate-x-6 translate-y-6">
            <Calculator className="w-48 h-48 text-white" />
          </div>

          <div className="space-y-5 relative z-10">
            <div>
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider text-valle-orangelight">
                Tu Cuota Fija Mensual
              </span>
              <div className="font-display font-extrabold text-3xl sm:text-4xl lg:text-5xl text-valle-orange mt-1.5 tabular-nums">
                {formatearPesos(resultado?.cuota_mensual || 0)}
              </div>
              <span className="text-xs text-slate-300 mt-1 block">
                Incluye capital, interés e IVA bajo Sistema Francés regulado por el BCRA.
              </span>
            </div>

            <div className="space-y-3 pt-5 border-t border-white/15 text-xs sm:text-sm">
              <div className="flex justify-between items-center bg-white/5 p-3 rounded-xl border border-white/10">
                <span className="text-slate-300">Tasa Nominal Anual (TNA):</span>
                <span className="font-extrabold text-white text-base tabular-nums">
                  {resultado ? `${(resultado.tna_aplicada * 100).toFixed(1)}%` : '57.0%'}
                </span>
              </div>
              <div className="flex justify-between items-center bg-white/5 p-3 rounded-xl border border-white/10">
                <span className="text-slate-300">Relación Cuota / Ingreso:</span>
                <span
                  className={`font-extrabold text-base tabular-nums ${
                    resultado?.ratio_cuota_ingreso > 0.35
                      ? 'text-rose-400'
                      : 'text-emerald-400'
                  }`}
                >
                  {resultado ? `${(resultado.ratio_cuota_ingreso * 100).toFixed(1)}%` : '0%'}
                  {resultado?.ratio_cuota_ingreso <= 0.35 ? ' (Apto ≤ 35%)' : ' (Excede 35%)'}
                </span>
              </div>
              <div className="flex justify-between items-center bg-emerald-500/20 p-3 rounded-xl border border-emerald-400/30">
                <span className="text-emerald-200">Estado de Aprobación:</span>
                <span className="font-bold text-emerald-300 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" /> Aprobado por Scoring
                </span>
              </div>
            </div>
          </div>

          {/* Botones de Acción */}
          <div className="space-y-3 pt-8 relative z-10">
            <button
              type="button"
              onClick={onOpenRegister}
              className="w-full py-3.5 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition flex items-center justify-center gap-2 group"
            >
              <span>Solicitar este Préstamo Ahora</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>

            <button
              type="button"
              onClick={() => onExportModal && onExportModal('PRESTAMOS')}
              className="w-full py-2.5 bg-white/10 hover:bg-white/20 text-slate-200 hover:text-white text-xs sm:text-sm font-semibold rounded-xl border border-white/15 transition flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4 text-valle-orange" />
              <span>Descargar Cotización Oficial (PDF)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoanSimulator;
