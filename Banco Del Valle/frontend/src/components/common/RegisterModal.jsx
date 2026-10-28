import React, { useState, useEffect } from 'react';
import { X, ArrowRight, ArrowLeft, CheckCircle2, Building2, User, ShieldCheck, AlertCircle, Loader2 } from 'lucide-react';
import { apiClient, setAuthToken } from '../../services/apiClient';
import { useAuth } from '../../context/AuthContext';
import { BrandLogo } from './BrandLogo';

/**
 * RegisterModal — Asistente multi-paso (Stepper Modal) de apertura atómica de cuenta.
 */
export function RegisterModal({ isOpen, onClose, onSuccess, initialTipo = 'PERSONA' }) {
  const { login } = useAuth();
  const [step, setStep] = useState(1);
  const [tipo, setTipo] = useState(initialTipo); // 'PERSONA' | 'EMPRESA'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setError(null);
      if (initialTipo) setTipo(initialTipo);
    }
  }, [isOpen, initialTipo]);

  // Expresión regular estándar para formato de email
  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // Form Persona (ejemplo inicial válido no colisionante)
  const [persona, setPersona] = useState({
    dni: '20-43512389-4',
    nombre_completo: 'Mariano Cordero',
    email: 'mariano.cordero@valle.com.ar',
    password: 'ValleSeguro2026!',
    localidad: 'San Fernando del Valle de Catamarca',
    categoria_laboral: 'EMPLEADO_PUBLICO',
    antiguedad_laboral_meses: 24,
    ingreso_mensual_comprobado: 3000000,
    monto_sueldo_acreditado: 3000000,
    es_cuenta_sueldo: true,
  });

  // Form Empresa (ejemplo inicial corporativo válido)
  const [empresa, setEmpresa] = useState({
    cuit: '30-79888123-5',
    razon_social: 'Valle Andino Logística S.A.',
    email: 'contacto@valleandino.com.ar',
    password: 'EmpresaValle2026!',
    localidad: 'San Fernando del Valle de Catamarca',
    tipo_societario: 'SA',
    rubro_actividad: 'Servicios Logísticos e Industriales',
    facturacion_anual_comprobada: 180000000,
    exencion_impositiva: false,
  });

  const [resultadoAlta, setResultadoAlta] = useState(null);

  if (!isOpen) return null;

  // Validación estricta del Paso 1 (Identificación y Credenciales)
  const validarPaso1 = () => {
    if (tipo === 'PERSONA') {
      const dniLimpio = (persona.dni || '').replace(/\D/g, '');
      if (!dniLimpio || dniLimpio.length < 7 || dniLimpio.length > 11) {
        return 'El DNI debe contener entre 7 y 8 dígitos numéricos (o 11 dígitos para formato CUIL).';
      }
      const nombreLimpio = (persona.nombre_completo || '').trim();
      if (!nombreLimpio || nombreLimpio.length < 3) {
        return 'El nombre completo debe tener al menos 3 caracteres.';
      }
      const emailLimpio = (persona.email || '').trim();
      if (!emailLimpio || !EMAIL_REGEX.test(emailLimpio)) {
        return 'Por favor ingresá un correo electrónico válido (ej. usuario@correo.com).';
      }
      const pass = persona.password || '';
      if (pass.length < 8) {
        return 'La contraseña debe tener al menos 8 caracteres.';
      }
      if (!/[A-Za-z]/.test(pass) || !/\d/.test(pass)) {
        return 'La contraseña debe combinar letras y al menos un número.';
      }
    } else {
      const cuitLimpio = (empresa.cuit || '').replace(/\D/g, '');
      if (!cuitLimpio || cuitLimpio.length !== 11) {
        return 'El CUIT corporativo debe contener exactamente 11 dígitos numéricos.';
      }
      const razonLimpia = (empresa.razon_social || '').trim();
      if (!razonLimpia || razonLimpia.length < 3) {
        return 'La razón social de la empresa debe tener al menos 3 caracteres.';
      }
      const emailLimpio = (empresa.email || '').trim();
      if (!emailLimpio || !EMAIL_REGEX.test(emailLimpio)) {
        return 'Por favor ingresá un correo corporativo válido (ej. contacto@empresa.com).';
      }
      const pass = empresa.password || '';
      if (pass.length < 8) {
        return 'La contraseña corporativa debe tener al menos 8 caracteres.';
      }
      if (!/[A-Za-z]/.test(pass) || !/\d/.test(pass)) {
        return 'La contraseña corporativa debe combinar letras y al menos un número.';
      }
    }
    return null;
  };

  // Validación estricta del Paso 2 (Perfil Socioeconómico)
  const validarPaso2 = () => {
    if (tipo === 'PERSONA') {
      const antiguedad = Number(persona.antiguedad_laboral_meses);
      if (isNaN(antiguedad) || antiguedad < 0) {
        return 'La antigüedad laboral debe ser un valor numérico mayor o igual a 0.';
      }
      const ingreso = Number(persona.ingreso_mensual_comprobado);
      if (isNaN(ingreso) || ingreso < 0) {
        return 'El ingreso mensual comprobado no puede ser un valor negativo.';
      }
    } else {
      const facturacion = Number(empresa.facturacion_anual_comprobada);
      if (isNaN(facturacion) || facturacion < 0) {
        return 'La facturación anual no puede ser un valor negativo.';
      }
    }
    return null;
  };

  const handleNext = () => {
    setError(null);
    if (step === 1) {
      const err = validarPaso1();
      if (err) {
        setError(err);
        return;
      }
    } else if (step === 2) {
      const err = validarPaso2();
      if (err) {
        setError(err);
        return;
      }
    }
    setStep((prev) => Math.min(prev + 1, 3));
  };

  const handleBack = () => {
    setError(null);
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleCrearCuenta = async () => {
    setError(null);
    const err1 = validarPaso1();
    if (err1) {
      setError(err1);
      setStep(1);
      return;
    }
    const err2 = validarPaso2();
    if (err2) {
      setError(err2);
      setStep(2);
      return;
    }

    setLoading(true);
    try {
      let res;
      if (tipo === 'PERSONA') {
        res = await apiClient.registroPersona({
          ...persona,
          dni: persona.dni.replace(/\D/g, ''),
          ingreso_mensual_comprobado: Number(persona.ingreso_mensual_comprobado),
          monto_sueldo_acreditado: Number(persona.monto_sueldo_acreditado),
          antiguedad_laboral_meses: Number(persona.antiguedad_laboral_meses),
        });
      } else {
        res = await apiClient.registroEmpresa({
          ...empresa,
          cuit: empresa.cuit.replace(/\D/g, ''),
          facturacion_anual_comprobada: Number(empresa.facturacion_anual_comprobada),
        });
      }

      setResultadoAlta(res);
      // Auto-login con el token generado
      if (res.token && res.usuario) {
        setAuthToken(res.token, res.usuario);
      }
    } catch (err) {
      setError(err.message || 'Error al procesar el alta de cuenta');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-xl bg-white dark:bg-valle-darkSurface rounded-2xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
        {/* Header */}
        <div className="bg-valle-blue dark:bg-valle-darkElevated px-6 py-4 flex items-center justify-between text-white border-b border-valle-blue/20 dark:border-valle-darkBorder">
          <BrandLogo size="sm" variant="light" />
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Indicador de Pasos (Stepper) */}
        {!resultadoAlta && (
          <div className="bg-slate-50 dark:bg-valle-darkElevated px-6 py-3 border-b border-slate-200 dark:border-valle-darkBorder flex items-center justify-between text-xs sm:text-sm font-semibold">
            <span className={step >= 1 ? 'text-valle-orange font-bold' : 'text-slate-400 dark:text-slate-500'}>
              1. Identificación
            </span>
            <span className="text-slate-400 dark:text-slate-600">➔</span>
            <span className={step >= 2 ? 'text-valle-orange font-bold' : 'text-slate-400 dark:text-slate-500'}>
              2. Perfil Socioeconómico
            </span>
            <span className="text-slate-400 dark:text-slate-600">➔</span>
            <span className={step === 3 ? 'text-valle-orange font-bold' : 'text-slate-400 dark:text-slate-500'}>
              3. Confirmación y Términos
            </span>
          </div>
        )}

        {/* Contenido por Paso */}
        <div className="p-6">
          {resultadoAlta ? (
            /* Vista de Cuenta Creada Exitosamente */
            <div className="text-center space-y-4 py-4">
              <div className="w-16 h-16 bg-emerald-100 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 rounded-full flex items-center justify-center mx-auto border border-emerald-200 dark:border-emerald-800/50">
                <CheckCircle2 className="w-9 h-9" />
              </div>
              <div>
                <h3 className="font-display font-bold text-2xl text-slate-900 dark:text-slate-50">
                  ¡Bienvenido a Banco del Valle!
                </h3>
                <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">
                  Tu cuenta transaccional ha sido generada y activada de forma inmediata.
                </p>
              </div>

              <div className="bg-slate-50 dark:bg-valle-darkElevated p-4 rounded-xl border border-slate-200 dark:border-valle-darkBorder text-left space-y-2.5 text-xs sm:text-sm">
                <div>
                  <span className="text-slate-500 dark:text-slate-400 font-medium">CBU Asignado (22 dígitos):</span>
                  <p className="font-mono font-bold text-slate-900 dark:text-slate-100 text-sm sm:text-base">{resultadoAlta.cbu}</p>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400 font-medium">Alias Bancario Único:</span>
                  <p className="font-mono font-bold text-valle-blue dark:text-valle-orange text-sm sm:text-base">{resultadoAlta.alias}</p>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400 font-medium">Rendimiento Flexible Activo:</span>
                  <p className="font-bold text-emerald-600 dark:text-emerald-400 text-sm sm:text-base">28.5% TNA (Acreditación Diaria)</p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  onClose();
                  if (onSuccess) onSuccess('homebanking');
                  window.location.reload();
                }}
                className="w-full py-3 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-sm rounded-xl shadow-md transition"
              >
                Ir a mi Home Banking
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* PASO 1 */}
              {step === 1 && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
                      Tipo de Titular
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      <button
                        type="button"
                        onClick={() => setTipo('PERSONA')}
                        className={`p-3.5 rounded-xl border flex items-center justify-center gap-2 text-xs sm:text-sm font-bold transition ${
                          tipo === 'PERSONA'
                            ? 'bg-valle-blue dark:bg-valle-orange text-white border-valle-blue dark:border-valle-orange shadow-sm'
                            : 'border-slate-200 dark:border-valle-darkBorder text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-valle-darkElevated'
                        }`}
                      >
                        <User className="w-4 h-4" /> Persona Humana
                      </button>
                      <button
                        type="button"
                        onClick={() => setTipo('EMPRESA')}
                        className={`p-3.5 rounded-xl border flex items-center justify-center gap-2 text-xs sm:text-sm font-bold transition ${
                          tipo === 'EMPRESA'
                            ? 'bg-valle-blue dark:bg-valle-orange text-white border-valle-blue dark:border-valle-orange shadow-sm'
                            : 'border-slate-200 dark:border-valle-darkBorder text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-valle-darkElevated'
                        }`}
                      >
                        <Building2 className="w-4 h-4" /> Empresa / PyME
                      </button>
                    </div>
                  </div>

                  {tipo === 'PERSONA' ? (
                    <>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">DNI / CUIL</label>
                        <input
                          type="text"
                          required
                          value={persona.dni}
                          onChange={(e) => setPersona({ ...persona, dni: e.target.value })}
                          placeholder="ej. 20-42049164-7"
                          className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Nombre Completo</label>
                        <input
                          type="text"
                          required
                          value={persona.nombre_completo}
                          onChange={(e) => setPersona({ ...persona, nombre_completo: e.target.value })}
                          placeholder="ej. Juan José Cano"
                          className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                        />
                      </div>
                    </>
                  ) : (
                    <>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">CUIT Empresa</label>
                        <input
                          type="text"
                          required
                          value={empresa.cuit}
                          onChange={(e) => setEmpresa({ ...empresa, cuit: e.target.value })}
                          placeholder="ej. 30-71234567-8"
                          className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Razón Social</label>
                        <input
                          type="text"
                          required
                          value={empresa.razon_social}
                          onChange={(e) => setEmpresa({ ...empresa, razon_social: e.target.value })}
                          placeholder="ej. Industrias del Valle S.R.L."
                          className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                        />
                      </div>
                    </>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Correo Electrónico</label>
                      <input
                        type="email"
                        required
                        value={tipo === 'PERSONA' ? persona.email : empresa.email}
                        onChange={(e) =>
                          tipo === 'PERSONA'
                            ? setPersona({ ...persona, email: e.target.value })
                            : setEmpresa({ ...empresa, email: e.target.value })
                        }
                        placeholder="tu@correo.com"
                        className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Contraseña</label>
                      <input
                        type="password"
                        required
                        value={tipo === 'PERSONA' ? persona.password : empresa.password}
                        onChange={(e) =>
                          tipo === 'PERSONA'
                            ? setPersona({ ...persona, password: e.target.value })
                            : setEmpresa({ ...empresa, password: e.target.value })
                        }
                        placeholder="Mínimo 8 caracteres"
                        className="w-full text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                      />
                      <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1">Mínimo 8 caracteres con letras y números</p>
                    </div>
                  </div>
                </div>
              )}

              {/* PASO 2 */}
              {step === 2 && (
                <div className="space-y-4">
                  {tipo === 'PERSONA' ? (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Categoría Laboral</label>
                          <select
                            value={persona.categoria_laboral}
                            onChange={(e) => setPersona({ ...persona, categoria_laboral: e.target.value })}
                            className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange bg-white dark:bg-valle-darkElevated text-slate-800 dark:text-slate-100"
                          >
                            <option value="EMPLEADO_PUBLICO">Empleado Público</option>
                            <option value="EMPLEADO_PRIVADO">Empleado Privado Formal</option>
                            <option value="MONOTRIBUTISTA">Monotributista / Autónomo</option>
                            <option value="JUBILADO">Jubilado / Pensionado</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Antigüedad (meses)</label>
                          <input
                            type="number"
                            value={persona.antiguedad_laboral_meses}
                            onChange={(e) => setPersona({ ...persona, antiguedad_laboral_meses: e.target.value })}
                            className="w-full text-sm px-3.5 py-2 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Ingreso Mensual Comprobado ($)</label>
                        <input
                          type="number"
                          value={persona.ingreso_mensual_comprobado}
                          onChange={(e) => setPersona({ ...persona, ingreso_mensual_comprobado: e.target.value })}
                          className="w-full text-sm px-3.5 py-2 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                        />
                      </div>

                      <div className="p-3.5 bg-slate-50 dark:bg-valle-darkElevated rounded-xl border border-slate-200 dark:border-valle-darkBorder flex items-center gap-2.5">
                        <input
                          type="checkbox"
                          id="sueldo_check"
                          checked={persona.es_cuenta_sueldo}
                          onChange={(e) => setPersona({ ...persona, es_cuenta_sueldo: e.target.checked })}
                          className="w-4 h-4 text-valle-orange rounded focus:ring-valle-orange"
                        />
                        <label htmlFor="sueldo_check" className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 font-medium">
                          Quiero cobrar mis haberes aquí (Habilitar acreditación automática de sueldo)
                        </label>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Tipo Societario</label>
                          <select
                            value={empresa.tipo_societario}
                            onChange={(e) => setEmpresa({ ...empresa, tipo_societario: e.target.value })}
                            className="w-full text-xs sm:text-sm px-3 py-2 border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange bg-white dark:bg-valle-darkElevated text-slate-800 dark:text-slate-100"
                          >
                            <option value="SA">Sociedad Anónima (S.A.)</option>
                            <option value="SRL">Sociedad de Resp. Ltda. (S.R.L.)</option>
                            <option value="SAS">Sociedad por Acciones Simplif. (S.A.S.)</option>
                            <option value="COOPERATIVA">Cooperativa</option>
                            <option value="MUTUAL">Mutual</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Facturación Anual ($)</label>
                          <input
                            type="number"
                            value={empresa.facturacion_anual_comprobada}
                            onChange={(e) => setEmpresa({ ...empresa, facturacion_anual_comprobada: e.target.value })}
                            className="w-full text-sm px-3.5 py-2 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-slate-100"
                          />
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* PASO 3 */}
              {step === 3 && (
                <div className="space-y-3.5">
                  <div className="p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 rounded-xl space-y-2 text-xs sm:text-sm text-blue-900 dark:text-blue-200">
                    <div className="flex items-center gap-1.5 font-bold">
                      <ShieldCheck className="w-4 h-4 text-valle-blue dark:text-valle-orange" />
                      <span>Políticas de Cumplimiento y PLA/FT (UIF / BCRA)</span>
                    </div>
                    <p className="leading-relaxed text-xs text-blue-800 dark:text-blue-300">
                      Declaro bajo juramento que los fondos tienen origen lícito conforme Ley 25.246.
                      Acepto la asignación inmediata de CBU, Alias y rendimiento flexible del 28.5% TNA.
                    </p>
                  </div>

                  <div className="p-3.5 bg-slate-50 dark:bg-valle-darkElevated rounded-xl border border-slate-200 dark:border-valle-darkBorder text-xs sm:text-sm text-slate-600 dark:text-slate-300 space-y-1.5">
                    <p>• Titular: <strong className="text-slate-900 dark:text-slate-100">{tipo === 'PERSONA' ? persona.nombre_completo : empresa.razon_social}</strong></p>
                    <p>• Localidad: <strong className="text-slate-900 dark:text-slate-100">{persona.localidad}</strong></p>
                    <p>• Tipo: <strong className="text-slate-900 dark:text-slate-100">{tipo === 'PERSONA' ? 'Caja de Ahorro Sueldo' : 'Cuenta Corriente PyME'}</strong></p>
                  </div>
                </div>
              )}

              {error && (
                <div className="p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 text-red-700 dark:text-red-300 text-xs sm:text-sm rounded-xl flex items-center gap-2 font-medium">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Botones de navegación */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-200 dark:border-valle-darkBorder">
                {step > 1 ? (
                  <button
                    type="button"
                    onClick={handleBack}
                    className="px-4 py-2 text-xs sm:text-sm font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-800 dark:hover:text-white flex items-center gap-1.5"
                  >
                    <ArrowLeft className="w-4 h-4" /> Volver
                  </button>
                ) : <div />}

                {step < 3 ? (
                  <button
                    type="button"
                    onClick={handleNext}
                    className="px-5 py-2.5 bg-valle-blue hover:bg-valle-bluelight text-white font-bold text-xs sm:text-sm rounded-xl shadow-md flex items-center gap-1.5 transition"
                  >
                    Siguiente <ArrowRight className="w-4 h-4" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleCrearCuenta}
                    disabled={loading}
                    className="px-5 py-2.5 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-xs sm:text-sm rounded-xl shadow-md flex items-center gap-1.5 transition disabled:opacity-50"
                  >
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" /> Confirmar y Abrir Cuenta
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default RegisterModal;
