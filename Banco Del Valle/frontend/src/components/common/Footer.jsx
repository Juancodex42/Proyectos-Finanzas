import React, { useState } from 'react';
import { BrandLogo } from './BrandLogo';
import {
  ShieldCheck,
  ExternalLink,
  QrCode,
  X,
  CheckCircle2,
  Phone,
  MapPin,
  Lock,
  Building,
  RotateCcw,
  UserX
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { MODAL_CONTENT } from './footerLegalContent';

/**
 * Footer — Pie de página bancario normativo oficial de la República Argentina.
 * Incluye ARCA Formulario 960/D (Data Fiscal QR), Sellos BCRA, SEDESA, UIF y Ley 24.240.
 */
export function Footer() {
  const { isDark } = useTheme();

  const [modalDataFiscal, setModalDataFiscal] = useState(false);
  const [modalArrepentimiento, setModalArrepentimiento] = useState(false);
  const [modalBaja, setModalBaja] = useState(false);
  const [mensajeExito, setMensajeExito] = useState(null);

  const handleSolicitarArrepentimiento = (e) => {
    e.preventDefault();
    setMensajeExito('Tu solicitud de revocación ha sido registrada. Número de trámite: REV-' + Math.floor(100000 + Math.random() * 900000));
    setTimeout(() => {
      setMensajeExito(null);
      setModalArrepentimiento(false);
    }, 3000);
  };

  const handleSolicitarBaja = (e) => {
    e.preventDefault();
    setMensajeExito('Tu solicitud de baja de producto ha sido ingresada conforme Ley 24.240. Trámite: BAJA-' + Math.floor(100000 + Math.random() * 900000));
    setTimeout(() => {
      setMensajeExito(null);
      setModalBaja(false);
    }, 3000);
  };

  return (
    <footer className="bg-white dark:bg-valle-darkSurface text-slate-700 dark:text-slate-300 text-sm border-t border-slate-200 dark:border-valle-darkBorder mt-8 sm:mt-16 transition-colors duration-200">
      <div className="max-w-[1600px] mx-auto px-4 sm:px-8 xl:px-12 py-8 sm:py-12">
        
        {/* FILA 1: INFORMACIÓN INSTITUCIONAL, PRODUCTOS Y ATENCIÓN AL CLIENTE */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8 mb-12">
          <div className="lg:col-span-2 space-y-4">
            <BrandLogo size="md" variant={isDark ? 'light' : 'dark'} />
            <p className="text-slate-600 dark:text-slate-300 text-sm leading-relaxed max-w-md">
              {MODAL_CONTENT.institucional.descripcion}
            </p>
            <div className="space-y-1.5 text-xs text-slate-600 dark:text-slate-400 pt-1 font-medium">
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-valle-orange flex-shrink-0" />
                <span>Casa Central: {MODAL_CONTENT.institucional.domicilio}</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4 text-valle-orange flex-shrink-0" />
                <span>Centro de Atención Telefónica: {MODAL_CONTENT.institucional.telefono}</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-display font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider mb-3">
              Soluciones Financieras
            </h4>
            <ul className="space-y-2 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
              <li><a href="#simulador-prestamos" className="hover:text-valle-orange transition">Préstamos Personales</a></li>
              <li><a href="#simulador-empresas" className="hover:text-valle-orange transition">Financiamiento PyME</a></li>
              <li><a href="#simulador-inversiones" className="hover:text-valle-orange transition">Plazos Fijos Tradicionales</a></li>
              <li><a href="#simulador-inversiones" className="hover:text-valle-orange transition">Caja Remunerada (28.5% TNA)</a></li>
              <li><span className="text-slate-400">Banca Móvil & Home Banking</span></li>
            </ul>
          </div>

          <div>
            <h4 className="font-display font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider mb-3">
              Marco Legal y Ético
            </h4>
            <ul className="space-y-2 text-xs sm:text-sm text-slate-600 dark:text-slate-400">
              <li><span className="hover:text-valle-orange cursor-pointer transition">Régimen Informativo BCRA</span></li>
              <li><span className="hover:text-valle-orange cursor-pointer transition">Prevención PLA/FT (Res. UIF 78/2025)</span></li>
              <li><span className="hover:text-valle-orange cursor-pointer transition">Protección de Datos Personales (Ley 25.326)</span></li>
              <li><span className="hover:text-valle-orange cursor-pointer transition">Cifrado Bancario SSL/TLS 256-bit</span></li>
              <li><span className="hover:text-valle-orange cursor-pointer transition">Código de Conducta Ética</span></li>
            </ul>
          </div>

          <div>
            <h4 className="font-display font-bold text-slate-900 dark:text-white text-xs uppercase tracking-wider mb-3">
              Defensa del Cliente
            </h4>
            <div className="space-y-2.5 text-xs sm:text-sm">
              <button
                type="button"
                onClick={() => setModalArrepentimiento(true)}
                className="w-full text-left px-3 py-2 rounded-xl bg-orange-50 dark:bg-valle-orange/10 hover:bg-orange-100 dark:hover:bg-valle-orange/20 text-valle-orangedark dark:text-valle-orangelight font-bold flex items-center justify-between transition border border-orange-200 dark:border-valle-orange/30 shadow-2xs"
              >
                <span className="flex items-center gap-1.5">
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Botón de Arrepentimiento</span>
                </span>
              </button>

              <button
                type="button"
                onClick={() => setModalBaja(true)}
                className="w-full text-left px-3 py-2 rounded-xl bg-slate-100 dark:bg-valle-darkElevated hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold flex items-center justify-between transition border border-slate-200 dark:border-valle-darkBorder"
              >
                <span className="flex items-center gap-1.5">
                  <UserX className="w-3.5 h-3.5 text-rose-500" />
                  <span>Botón de Baja de Servicios</span>
                </span>
              </button>

              <div className="pt-1 text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                <span>Responsable de Atención al Usuario Financiero: </span>
                <strong className="text-slate-700 dark:text-slate-300">{MODAL_CONTENT.institucional.emailDefensa}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* FILA 2: SELLOS OFICIALES (ARCA DATA FISCAL QR, BCRA, SEDESA, UIF) */}
        <div className="p-6 rounded-3xl bg-slate-50 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder mb-10">
          <div className="text-center sm:text-left mb-5">
            <span className="text-[11px] font-extrabold uppercase tracking-widest text-valle-orange block">
              Organismos de Contralor y Entidades Regulatorias Oficiales
            </span>
            <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
              Banco del Valle S.A. opera bajo estricto cumplimiento del marco legal y financiero de la República Argentina.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-stretch">
            <div
              onClick={() => setModalDataFiscal(true)}
              className="cursor-pointer p-4 rounded-2xl bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder hover:border-valle-orange dark:hover:border-valle-orange transition-all duration-200 shadow-2xs group flex items-center gap-3.5"
              title="Click para ver constancia de Data Fiscal ARCA"
            >
              <div className="w-14 h-16 bg-[#004B87] rounded-lg p-1 text-white flex flex-col justify-between items-center flex-shrink-0 shadow-xs group-hover:scale-105 transition-transform">
                <div className="text-[8px] font-black tracking-wider leading-none">ARCA</div>
                <div className="bg-white p-0.5 rounded">
                  <svg className="w-8 h-8 text-black" viewBox="0 0 24 24" fill="currentColor">
                    <path d={MODAL_CONTENT.qrSvgPath} />
                  </svg>
                </div>
                <div className="text-[6.5px] font-bold tracking-tighter leading-none">F. 960/D</div>
              </div>
              <div>
                <div className="flex items-center gap-1 text-[11px] font-extrabold uppercase text-[#004B87] dark:text-sky-400">
                  <span>Data Fiscal ARCA</span>
                  <ExternalLink className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
                <div className="font-bold text-xs text-slate-800 dark:text-slate-100">Formulario Nº 960/D</div>
                <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-0.5 font-mono">
                  CUIT: {MODAL_CONTENT.institucional.cuit}
                </span>
              </div>
            </div>

            <a
              href="https://www.usuariosfinancieros.gob.ar"
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 rounded-2xl bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder hover:border-valle-blue dark:hover:border-sky-400 transition-all duration-200 shadow-2xs group flex items-center gap-3.5"
            >
              <div className="w-12 h-12 rounded-xl bg-valle-blue/10 dark:bg-sky-950/50 border border-valle-blue/20 dark:border-sky-800/40 text-valle-blue dark:text-sky-300 flex items-center justify-center flex-shrink-0 group-hover:scale-105 transition-transform">
                <Building className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-1 text-[11px] font-extrabold uppercase text-valle-blue dark:text-sky-300">
                  <span>BCRA Usuarios Financieros</span>
                  <ExternalLink className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
                <div className="font-bold text-xs text-slate-800 dark:text-slate-100">Entidad N° 00492</div>
                <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-0.5">Supervisado por el BCRA</span>
              </div>
            </a>

            <div className="p-4 rounded-2xl bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder shadow-2xs flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center flex-shrink-0">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <div className="text-[11px] font-extrabold uppercase text-emerald-700 dark:text-emerald-400">Garantía SEDESA</div>
                <div className="font-bold text-xs text-slate-800 dark:text-slate-100">Hasta $25.000.000</div>
                <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-0.5">Ley 24.485 y Dec. 540/95</span>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-valle-darkSurface border border-slate-200 dark:border-valle-darkBorder shadow-2xs flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-amber-50 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-800/40 text-amber-600 dark:text-amber-400 flex items-center justify-center flex-shrink-0">
                <Lock className="w-6 h-6" />
              </div>
              <div>
                <div className="text-[11px] font-extrabold uppercase text-amber-700 dark:text-amber-400">Sujeto Obligado UIF</div>
                <div className="font-bold text-xs text-slate-800 dark:text-slate-100">Prevención PLA / FT</div>
                <span className="text-[11px] text-slate-500 dark:text-slate-400 block mt-0.5">Ley 25.246 & Res. 78/2025</span>
              </div>
            </div>
          </div>
        </div>

        {/* FILA 3: REDES DE PAGO Y MEDIOS TRANSACCIONALES HOMOLOGADOS */}
        <div className="flex flex-col md:flex-row items-center justify-between pb-8 mb-8 border-b border-slate-200 dark:border-valle-darkBorder gap-4">
          <div className="text-center md:text-left">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 block">
              Canales Transaccionales y Redes Interbancarias Homologadas:
            </span>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 text-xs font-bold">
            {MODAL_CONTENT.redesHomologadas.map((red) => (
              <span
                key={red.label}
                className={
                  red.variant === 'emerald'
                    ? 'px-3.5 py-1.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/40 text-emerald-800 dark:text-emerald-300 font-bold tracking-tight shadow-2xs'
                    : red.variant === 'blue'
                    ? 'px-3.5 py-1.5 rounded-xl bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/40 text-blue-800 dark:text-blue-300 font-mono tracking-tight shadow-2xs'
                    : 'px-3.5 py-1.5 rounded-xl bg-slate-100 dark:bg-valle-darkElevated border border-slate-200 dark:border-valle-darkBorder text-slate-700 dark:text-slate-200 font-mono tracking-tight shadow-2xs'
                }
              >
                {red.label}
              </span>
            ))}
          </div>
        </div>

        {/* FILA 4: BARRA DE COPYRIGHT Y LEY DE PROTECCIÓN DE DATOS PERSONALES */}
        <div className="flex flex-col lg:flex-row items-center justify-between gap-4 text-xs text-slate-500 dark:text-slate-400">
          <p className="text-center lg:text-left leading-relaxed">{MODAL_CONTENT.institucional.copyright}</p>
          <div className="flex flex-wrap items-center justify-center gap-4 text-slate-600 dark:text-slate-400 font-medium">
            <span className="hover:text-valle-orange cursor-pointer">Términos y Condiciones</span>
            <span>•</span>
            <span className="hover:text-valle-orange cursor-pointer">Protección de Datos Personales (Ley 25.326)</span>
            <span>•</span>
            <span className="hover:text-valle-orange cursor-pointer">Seguridad Bancaria</span>
          </div>
        </div>
      </div>

      {/* MODAL 1: FORMULARIO 960/D DATA FISCAL ARCA */}
      {modalDataFiscal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-md bg-white dark:bg-valle-darkSurface rounded-3xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
            <div className="bg-[#004B87] px-6 py-4 flex items-center justify-between text-white">
              <div className="flex items-center gap-2">
                <QrCode className="w-5 h-5 text-sky-300" />
                <span className="font-bold text-sm">{MODAL_CONTENT.dataFiscal.titulo}</span>
              </div>
              <button onClick={() => setModalDataFiscal(false)} className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 text-center space-y-4">
              <div className="w-36 h-36 bg-slate-50 dark:bg-white p-3 rounded-2xl mx-auto border border-slate-200 shadow-inner flex items-center justify-center">
                <svg className="w-full h-full text-slate-900" viewBox="0 0 24 24" fill="currentColor">
                  <path d={MODAL_CONTENT.qrSvgPath} />
                </svg>
              </div>
              <div>
                <h4 className="font-display font-extrabold text-base text-slate-900 dark:text-white">{MODAL_CONTENT.institucional.razonSocial}</h4>
                <p className="text-xs font-mono text-slate-600 dark:text-slate-300 mt-0.5">CUIT: {MODAL_CONTENT.institucional.cuit}</p>
              </div>
              <div className="text-left bg-slate-50 dark:bg-valle-darkElevated p-4 rounded-xl border border-slate-200 dark:border-valle-darkBorder space-y-2 text-xs">
                <div>
                  <span className="text-slate-500 dark:text-slate-400">Actividad Principal:</span>
                  <p className="font-bold text-slate-800 dark:text-slate-200">{MODAL_CONTENT.dataFiscal.actividad}</p>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400">Domicilio Fiscal Registrado:</span>
                  <p className="font-bold text-slate-800 dark:text-slate-200">{MODAL_CONTENT.dataFiscal.domicilio}</p>
                </div>
                <div>
                  <span className="text-slate-500 dark:text-slate-400">Estado de Inscripción:</span>
                  <p className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> {MODAL_CONTENT.dataFiscal.estado}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setModalDataFiscal(false)}
                className="w-full py-2.5 bg-slate-100 dark:bg-valle-darkElevated hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200 font-bold text-xs rounded-xl transition"
              >
                Cerrar Consulta
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: BOTÓN DE ARREPENTIMIENTO (LEY 24.240) */}
      {modalArrepentimiento && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-md bg-white dark:bg-valle-darkSurface rounded-3xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
            <div className="bg-valle-orange px-6 py-4 flex items-center justify-between text-white">
              <div className="flex items-center gap-2">
                <RotateCcw className="w-5 h-5" />
                <span className="font-bold text-sm">{MODAL_CONTENT.arrepentimiento.titulo}</span>
              </div>
              <button onClick={() => setModalArrepentimiento(false)} className="p-1 rounded-lg text-white hover:bg-white/20 transition">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{MODAL_CONTENT.arrepentimiento.leyenda}</p>
              {mensajeExito ? (
                <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-200 text-xs sm:text-sm rounded-xl font-medium flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                  <span>{mensajeExito}</span>
                </div>
              ) : (
                <form onSubmit={handleSolicitarArrepentimiento} className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">DNI / CUIT del Titular</label>
                    <input type="text" required placeholder="ej. 35123456" className="w-full text-xs sm:text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-white" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Producto o Préstamo a Revocar</label>
                    <select className="w-full text-xs sm:text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-white">
                      {MODAL_CONTENT.arrepentimiento.opciones.map((op) => <option key={op}>{op}</option>)}
                    </select>
                  </div>
                  <button type="submit" className="w-full py-3 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition">
                    Confirmar Solicitud de Revocación
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: BOTÓN DE BAJA DE SERVICIOS (LEY 24.240) */}
      {modalBaja && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-md bg-white dark:bg-valle-darkSurface rounded-3xl shadow-2xl border border-slate-200 dark:border-valle-darkBorder overflow-hidden">
            <div className="bg-slate-900 dark:bg-valle-darkElevated px-6 py-4 flex items-center justify-between text-white border-b border-slate-800">
              <div className="flex items-center gap-2">
                <UserX className="w-5 h-5 text-rose-400" />
                <span className="font-bold text-sm">{MODAL_CONTENT.bajaServicios.titulo}</span>
              </div>
              <button onClick={() => setModalBaja(false)} className="p-1 rounded-lg text-slate-300 hover:text-white hover:bg-white/10 transition">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{MODAL_CONTENT.bajaServicios.leyenda}</p>
              {mensajeExito ? (
                <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-200 text-xs sm:text-sm rounded-xl font-medium flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                  <span>{mensajeExito}</span>
                </div>
              ) : (
                <form onSubmit={handleSolicitarBaja} className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">DNI o CUIT del Titular</label>
                    <input type="text" required placeholder="ej. 35123456" className="w-full text-xs sm:text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-white" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Servicio a Dar de Baja</label>
                    <select className="w-full text-xs sm:text-sm px-3.5 py-2.5 bg-white dark:bg-valle-darkElevated border border-slate-300 dark:border-valle-darkBorder rounded-xl outline-none focus:ring-2 focus:ring-valle-orange text-slate-900 dark:text-white">
                      {MODAL_CONTENT.bajaServicios.opciones.map((op) => <option key={op}>{op}</option>)}
                    </select>
                  </div>
                  <button type="submit" className="w-full py-3 bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-md transition">
                    Confirmar Pedido de Baja
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </footer>
  );
}

export default Footer;
