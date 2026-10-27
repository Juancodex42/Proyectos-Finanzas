import React, { useState } from 'react';
import { Building2, ShieldAlert, CheckCircle2, Download, ArrowRight } from 'lucide-react';

/**
 * CorporateSimulator — Simulador de crédito para Empresas y PyMEs con alto contraste y soporte Dark Mode.
 */
export function CorporateSimulator({ onOpenRegister, onExportModal }) {
  const [cuit, setCuit] = useState('30-71234567-8');
  const [razonSocial, setRazonSocial] = useState('Catamarca Minería & Servicios S.A.');
  const [tipoSocietario, setTipoSocietario] = useState('SA');
  const [facturacionAnual, setFacturacionAnual] = useState(180000000);
  const [monto, setMonto] = useState(15000000);
  const [plazoMeses, setPlazoMeses] = useState(24);

  // Fórmulas financieras simplificadas del Sistema Francés para empresas
  const facturacionMensual = facturacionAnual / 12;
  const tna = tipoSocietario === 'COOPERATIVA' ? 0.52 : 0.58;
  const tasaMensual = tna / 12;
  const cuotaEstimada =
    (monto * (tasaMensual * Math.pow(1 + tasaMensual, plazoMeses))) /
    (Math.pow(1 + tasaMensual, plazoMeses) - 1);
  const ratioCuotaVentas = cuotaEstimada / facturacionMensual;
  const esApto = ratioCuotaVentas <= 0.20;
  const requiereFianza = tipoSocietario === 'SAS' || tipoSocietario === 'SRL';

  const formatearPesos = (val) =>
    new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      maximumFractionDigits: 0,
    }).format(val || 0);

  return (
    <div id="simulador-empresas" className="valle-card p-6 sm:p-10 mb-12 rounded-3xl transition-colors duration-200">
      <div className="pb-6 mb-8 border-b border-slate-200 dark:border-valle-darkBorder">
        <div className="inline-flex items-center gap-2 text-xs sm:text-sm font-bold uppercase tracking-wider text-valle-blue dark:text-sky-300 mb-1.5">
          <Building2 className="w-4 h-4 text-valle-orange" />
          <span>Línea Productiva Corporativa</span>
        </div>
        <h2 className="font-display font-extrabold text-2xl sm:text-3xl text-slate-900 dark:text-white">
          Simulador de Financiamiento para PyMEs
        </h2>
        <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 mt-1">
          Crédito para inversión productiva, galpones industriales, flotas y capital de trabajo.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
        {/* Controles PyME */}
        <div className="lg:col-span-7 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-sm font-bold text-slate-800 dark:text-slate-200">
                  CUIT Empresa
                </label>
                {razonSocial && (
                  <span className="text-[11px] font-bold text-valle-orange truncate max-w-[190px]" title={razonSocial}>
                    {razonSocial}
                  </span>
                )}
              </div>
              <input
                type="text"
                value={cuit}
                onChange={(e) => {
                  setCuit(e.target.value);
                  if (e.target.value.includes('71234567')) {
                    setRazonSocial('Catamarca Minería & Servicios S.A.');
                    setTipoSocietario('SA');
                  }
                }}
                placeholder="ej. 30-71234567-8"
                className="w-full text-sm sm:text-base px-4 py-2.5 bg-slate-50 dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange font-bold text-slate-900 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-sm font-bold text-slate-800 dark:text-slate-200 mb-1.5">
                Tipo Societario
              </label>
              <select
                value={tipoSocietario}
                onChange={(e) => setTipoSocietario(e.target.value)}
                className="w-full text-sm sm:text-base px-4 py-2.5 bg-slate-50 dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange font-bold text-slate-900 dark:text-white"
              >
                <option value="SA">Sociedad Anónima (S.A.)</option>
                <option value="SRL">Sociedad de Resp. Ltda. (S.R.L.)</option>
                <option value="SAS">Sociedad por Acciones Simplif. (S.A.S.)</option>
                <option value="COOPERATIVA">Cooperativa / Mutual de Trabajo</option>
              </select>
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center text-sm font-bold text-slate-800 dark:text-slate-200 mb-2">
              <span>Facturación Anual Comprobada ($)</span>
              <span className="text-valle-blue dark:text-sky-400 font-extrabold tabular-nums">{formatearPesos(facturacionAnual)}</span>
            </div>
            <input
              type="range"
              min="10000000"
              max="300000000"
              step="5000000"
              value={facturacionAnual}
              onChange={(e) => setFacturacionAnual(Number(e.target.value))}
              className="slider-valle"
            />
          </div>

          <div>
            <div className="flex justify-between items-center text-sm font-bold text-slate-800 dark:text-slate-200 mb-2">
              <span>Monto a Financiar ($)</span>
              <span className="text-valle-orange font-extrabold tabular-nums">{formatearPesos(monto)}</span>
            </div>
            <input
              type="range"
              min="2000000"
              max="50000000"
              step="1000000"
              value={monto}
              onChange={(e) => setMonto(Number(e.target.value))}
              className="slider-valle"
            />
          </div>

          <div>
            <label className="block text-sm font-bold text-slate-800 dark:text-slate-200 mb-2">
              Plazo de Amortización
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {[12, 24, 36, 48].map((pl) => (
                <button
                  key={pl}
                  type="button"
                  onClick={() => setPlazoMeses(pl)}
                  className={`py-2.5 text-xs sm:text-sm font-bold rounded-xl border transition ${
                    plazoMeses === pl
                      ? 'bg-valle-blue dark:bg-valle-orange text-white border-valle-blue dark:border-valle-orange shadow-md'
                      : 'border-slate-300 dark:border-valle-darkBorder text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-valle-darkElevated'
                  }`}
                >
                  {pl} Meses
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Panel Resumen */}
        <div className="lg:col-span-5 bg-gradient-to-br from-slate-900 via-valle-bluedark to-valle-blue dark:from-[#0B1526] dark:via-[#10203B] dark:to-[#172D52] text-white rounded-3xl p-7 sm:p-9 flex flex-col justify-between shadow-xl border border-slate-800 dark:border-valle-darkBorder">
          <div className="space-y-5">
            <div>
              <span className="text-xs sm:text-sm font-bold uppercase tracking-wider text-valle-orangelight">
                Cuota Mensual Estimada (Francés)
              </span>
              <div className="font-display font-extrabold text-3xl sm:text-4xl lg:text-5xl text-emerald-400 mt-1.5 tabular-nums">
                {formatearPesos(cuotaEstimada)}
              </div>
            </div>

            <div className="space-y-3 pt-5 border-t border-white/15 text-xs sm:text-sm">
              <div className="flex justify-between items-center bg-white/5 p-3 rounded-xl border border-white/10">
                <span className="text-slate-300">TNA Corporativa:</span>
                <span className="font-extrabold text-white text-base tabular-nums">{(tna * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between items-center bg-white/5 p-3 rounded-xl border border-white/10">
                <span className="text-slate-300">Impacto s/ Ventas Mensuales:</span>
                <span className={`font-extrabold text-base tabular-nums ${esApto ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {(ratioCuotaVentas * 100).toFixed(1)}% (Límite: 20%)
                </span>
              </div>
              {requiereFianza && (
                <div className="p-3 bg-amber-500/20 border border-amber-500/30 rounded-xl text-amber-200 text-xs flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 flex-shrink-0 text-amber-400" />
                  <span>Requiere Fianza Solidaria de los Socios.</span>
                </div>
              )}
            </div>
          </div>

          <div className="pt-8 space-y-3">
            <button
              type="button"
              onClick={() => onOpenRegister && onOpenRegister('EMPRESA')}
              className="w-full py-3.5 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition flex items-center justify-center gap-2 group"
            >
              <span>Solicitar Calificación PyME</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
            <button
              type="button"
              onClick={() => onExportModal && onExportModal('PRESTAMOS')}
              className="w-full py-2.5 bg-white/10 hover:bg-white/20 text-slate-200 hover:text-white text-xs sm:text-sm font-semibold rounded-xl border border-white/15 transition flex items-center justify-center gap-2"
            >
              <Download className="w-4 h-4 text-valle-orange" />
              <span>Descargar Cotización (PDF)</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CorporateSimulator;
