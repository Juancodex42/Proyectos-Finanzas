import React, { useState, useEffect } from 'react';
import { Home, Sparkles, TrendingUp, ShieldCheck, ArrowRight, ChevronLeft, ChevronRight, MapPin, Pause, Play } from 'lucide-react';

/**
 * 32 Fotografías de Alta Definición Curadas para Banco del Valle (Catamarca)
 * 16 para Individuos & Familias + 16 para Empresas & PyMEs
 */
export const HERO_SLIDES = {
  INDIVIDUOS: [
    {
      id: 'ind-1',
      url: '/images/hero/ind-1.jpg',
      tag: 'Vivienda Propia',
      titulo: 'Tu casa en San Fernando del Valle',
      descripcion: 'Accedé a créditos hipotecarios y refacción con cuotas fijas bajo Sistema Francés.',
      ubicacion: 'San Fernando del Valle de Catamarca',
    },
    {
      id: 'ind-2',
      url: '/images/hero/ind-2.jpg',
      tag: 'Hogar y Familia',
      titulo: 'Espacios para crecer juntos',
      descripcion: 'Líneas de financiamiento a medida para familias catamarqueñas en crecimiento.',
      ubicacion: 'Valle Viejo, Catamarca',
    },
    {
      id: 'ind-3',
      url: '/images/hero/ind-3.jpg',
      tag: 'Crédito Prendario',
      titulo: 'Tu auto nuevo con tasa bonificada',
      descripcion: 'Financiá hasta el 70% de vehículos 0km y usados seleccionados.',
      ubicacion: 'San Fernando del Valle',
    },
    {
      id: 'ind-4',
      url: '/images/hero/ind-4.jpg',
      tag: 'Arquitectura Regional',
      titulo: 'Construcción en zonas residenciales',
      descripcion: 'Planes especiales para loteos y obras nuevas en los valles.',
      ubicacion: 'Fray Mamerto Esquiú',
    },
    {
      id: 'ind-5',
      url: '/images/hero/ind-5.jpg',
      tag: 'Futuro Universitario',
      titulo: 'Inversión en educación y capacitación',
      descripcion: 'Préstamos para estudiantes y profesionales de la Universidad Nacional de Catamarca.',
      ubicacion: 'UNCA, Catamarca',
    },
    {
      id: 'ind-6',
      url: '/images/hero/ind-6.jpg',
      tag: 'Refacción y Mejoras',
      titulo: 'Modernizá tu hogar hoy mismo',
      descripcion: 'Créditos rápidos con aprobación en el día para ampliaciones y equipamiento.',
      ubicacion: 'San Fernando del Valle',
    },
    {
      id: 'ind-7',
      url: '/images/hero/ind-7.jpg',
      tag: 'Ahorro Inteligente',
      titulo: 'Rentabilidad en Caja Remunerada al 28.5%',
      descripcion: 'Tus ingresos generan intereses diarios con disponibilidad de fondos 24/7.',
      ubicacion: 'Banca Digital Banco del Valle',
    },
    {
      id: 'ind-8',
      url: '/images/hero/ind-8.jpg',
      tag: 'Tranquilidad Familiar',
      titulo: 'Un futuro seguro para tus hijos',
      descripcion: 'Plazos fijos tradicionales con garantía SEDESA y tasas preferenciales.',
      ubicacion: 'Valle Central de Catamarca',
    },
    {
      id: 'ind-9',
      url: '/images/hero/ind-9.jpg',
      tag: 'Movilidad y Viajes',
      titulo: 'Explorá las rutas de nuestra provincia',
      descripcion: 'Financiamiento personal para viajes, turismo interno y recreación.',
      ubicacion: 'Cuesta del Portezuelo, Catamarca',
    },
    {
      id: 'ind-10',
      url: '/images/hero/ind-10.jpg',
      tag: 'Equipamiento Familiar',
      titulo: 'Confort y tecnología para tu casa',
      descripcion: 'Planes en cuotas fijas para climatización, paneles solares domésticos y electrodomésticos.',
      ubicacion: 'San Fernando del Valle',
    },
    {
      id: 'ind-11',
      url: '/images/hero/ind-11.jpg',
      tag: 'Planificación de Retiro',
      titulo: 'Respaldo y seguridad para jubilados',
      descripcion: 'Atención preferencial, anticipo de haberes y créditos previsionales transparentes.',
      ubicacion: 'Red de Sucursales Catamarca',
    },
    {
      id: 'ind-12',
      url: '/images/hero/ind-12.jpg',
      tag: 'Nuestra Tierra',
      titulo: 'Orgullo por el paisaje catamarqueño',
      descripcion: 'Raíz e identidad en los valles calchaquíes y serranos de nuestra provincia.',
      ubicacion: 'Belen & Tinogasta, Catamarca',
    },
    {
      id: 'ind-13',
      url: '/images/hero/ind-13.jpg',
      tag: 'Proyectos Personales',
      titulo: 'Alcanzá tus metas con respaldo financiero',
      descripcion: 'Simulá tu préstamo en 1 minuto con tu DNI y conocé tu cuota al instante.',
      ubicacion: 'Ruta Nacional 38, Catamarca',
    },
    {
      id: 'ind-14',
      url: '/images/hero/ind-14.jpg',
      tag: 'Comunidad Regional',
      titulo: 'Cerca de cada familia catamarqueña',
      descripcion: 'Banca humana con atención personalizada y canales digitales de vanguardia.',
      ubicacion: 'San Fernando del Valle',
    },
    {
      id: 'ind-15',
      url: '/images/hero/ind-15.jpg',
      tag: 'Banca Joven',
      titulo: 'Cuentas 100% digitales y sin comisiones',
      descripcion: 'Apertura inmediata, transferencias 24/7 y tarjeta de débito sin costo de emisión.',
      ubicacion: 'Catamarca Digital',
    },
    {
      id: 'ind-16',
      url: '/images/hero/ind-16.jpg',
      tag: 'Bienestar Financiero',
      titulo: 'La tranquilidad de estar bien respaldado',
      descripcion: 'Supervisión estricta del BCRA y solidez de capital para proteger tu patrimonio.',
      ubicacion: 'Valle de Catamarca',
    },
  ],
  EMPRESAS: [
    {
      id: 'emp-1',
      url: '/images/hero/emp-1.jpg',
      tag: 'Industria & Manufactura',
      titulo: 'Líneas productivas para industrias del Valle',
      descripcion: 'Financiamiento para ampliación de plantas fabriles y adquisición de tecnología.',
      ubicacion: 'Parque Industrial El Pantanillo, Catamarca',
    },
    {
      id: 'emp-2',
      url: '/images/hero/emp-2.jpg',
      tag: 'Transporte & Flotas',
      titulo: 'Renovación de camiones y utilitarios',
      descripcion: 'Leasing y créditos prendarios para flotas de distribución y logística pesada.',
      ubicacion: 'San Fernando del Valle de Catamarca',
    },
    {
      id: 'emp-3',
      url: '/images/hero/emp-3.jpg',
      tag: 'Agroindustria & Olivares',
      titulo: 'Impulso a la producción olivícola y nogalera',
      descripcion: 'Capital de trabajo y financiamiento de cosecha para productores de Catamarca.',
      ubicacion: 'Valle de Pomán & Capayán, Catamarca',
    },
    {
      id: 'emp-4',
      url: '/images/hero/emp-4.jpg',
      tag: 'Construcción Civil',
      titulo: 'Financiamiento para obras y desarrollos',
      descripcion: 'Créditos para compra de maquinaria pesada, excavadoras y hormigoneras.',
      ubicacion: 'Obras de Infraestructura Catamarca',
    },
    {
      id: 'emp-5',
      url: '/images/hero/emp-5.jpg',
      tag: 'Energías Renovables',
      titulo: 'Transición solar en el noroeste argentino',
      descripcion: 'Líneas verdes a tasa subsidiada para parques solares y autogeneración PyME.',
      ubicacion: 'Tinogasta & Fiambalá, Catamarca',
    },
    {
      id: 'emp-6',
      url: '/images/hero/emp-6.jpg',
      tag: 'Logística & Depósitos',
      titulo: 'Galpones industriales y centros de carga',
      descripcion: 'Financiación de naves logísticas e instalaciones de almacenamiento regional.',
      ubicacion: 'El Pantanillo, Catamarca',
    },
    {
      id: 'emp-7',
      url: '/images/hero/emp-7.jpg',
      tag: 'Producción Agrícola',
      titulo: 'Tecnología de riego y maquinaria de campo',
      descripcion: 'Créditos para sistemas de riego por goteo y tractores de alta potencia.',
      ubicacion: 'Santa María, Catamarca',
    },
    {
      id: 'emp-8',
      url: '/images/hero/emp-8.jpg',
      tag: 'Talleres Metalúrgicos',
      titulo: 'Equipamiento de tornería y mecanizado',
      descripcion: 'Líneas PyME para herramientas de precisión y mantenimiento electromecánico.',
      ubicacion: 'San Fernando del Valle',
    },
    {
      id: 'emp-9',
      url: '/images/hero/emp-9.jpg',
      tag: 'Comercio Mayorista',
      titulo: 'Líneas de crédito para capital de trabajo',
      descripcion: 'Acuerdo en cuenta corriente y descuento de cheques con tasas preferenciales.',
      ubicacion: 'Área Metropolitana de Catamarca',
    },
    {
      id: 'emp-10',
      url: '/images/hero/emp-10.jpg',
      tag: 'Gestión Corporativa',
      titulo: 'Tesorería corporativa y pago a proveedores',
      descripcion: 'Plataforma Interbanking y rendimientos mayoristas en cuentas remuneradas.',
      ubicacion: 'Banca Empresas Banco del Valle',
    },
    {
      id: 'emp-11',
      url: '/images/hero/emp-11.jpg',
      tag: 'Metalurgia & Minería',
      titulo: 'Proveedores mineros de Catamarca',
      descripcion: 'Créditos específicos para empresas proveedoras de la cadena de valor del litio.',
      ubicacion: 'Andalgalá & Antofagasta de la Sierra',
    },
    {
      id: 'emp-12',
      url: '/images/hero/emp-12.jpg',
      tag: 'Agroalimentos & Envasado',
      titulo: 'Líneas de valor agregado local',
      descripcion: 'Financiamiento para envasado de aceite de oliva, dulces y frutos secos.',
      ubicacion: 'Pomán & Belén, Catamarca',
    },
    {
      id: 'emp-13',
      url: '/images/hero/emp-13.jpg',
      tag: 'Sustentabilidad Productiva',
      titulo: 'Bonificación de tasa para PyMEs Verdes',
      descripcion: 'Incentivos financieros para reducción de huella de carbono y efluentes.',
      ubicacion: 'Catamarca Sustentable',
    },
    {
      id: 'emp-14',
      url: '/images/hero/emp-14.jpg',
      tag: 'Innovación Tecnológica',
      titulo: 'Software y automatización en planta',
      descripcion: 'Créditos para digitalización y trazabilidad de procesos productivos.',
      ubicacion: 'Valle Central de Catamarca',
    },
    {
      id: 'emp-15',
      url: '/images/hero/emp-15.jpg',
      tag: 'Desarrollo Regional',
      titulo: 'Inversión de capital para PyMEs en expansión',
      descripcion: 'Estructuración financiera y acompañamiento institucional continuo.',
      ubicacion: 'Sede Corporativa Catamarca',
    },
    {
      id: 'emp-16',
      url: '/images/hero/emp-16.jpg',
      tag: 'Comercio & Servicios',
      titulo: 'Soluciones de cobro y crédito comercial',
      descripcion: 'Terminales de pago, acreditación en 24hs y financiamiento de inventario.',
      ubicacion: 'Red Comercial Catamarca',
    },
  ],
};

/**
 * HeroBanner — Sección Hero aspiracional con carrusel automático rotativo de 32 imágenes
 * (16 para Individuos + 16 para Empresas) con controles interactivos y diseño responsive a 1600px.
 */
export function HeroBanner({ segmento = 'INDIVIDUOS', onSimulateClick, onDepositClick }) {
  const isIndividuo = segmento === 'INDIVIDUOS';
  const slides = isIndividuo ? HERO_SLIDES.INDIVIDUOS : HERO_SLIDES.EMPRESAS;

  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);

  // Reiniciar el índice si cambia de segmento
  useEffect(() => {
    setCurrentIndex(0);
  }, [segmento]);

  // Rotación automática cada 4.5 segundos (pausa si el usuario tiene el cursor encima)
  useEffect(() => {
    if (isPaused) return;

    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % slides.length);
    }, 4500);

    return () => clearInterval(timer);
  }, [isPaused, slides.length]);

  const handlePrev = (e) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev - 1 + slides.length) % slides.length);
  };

  const handleNext = (e) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev + 1) % slides.length);
  };

  const currentSlide = slides[currentIndex] || slides[0];

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-white via-slate-50 to-orange-50/40 dark:from-[#091224] dark:via-[#0F1E38] dark:to-[#162B4E] text-slate-900 dark:text-white rounded-2xl sm:rounded-3xl p-4 sm:p-8 lg:p-12 shadow-xs border border-slate-200 dark:border-valle-darkBorder transition-colors duration-200">
      {/* Patrón decorativo de fondo */}
      <div className="absolute inset-0 opacity-15 dark:opacity-10 bg-[radial-gradient(#FF7A00_1px,transparent_1px)] [background-size:18px_18px] pointer-events-none" />

      <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-12 items-center">
        {/* Columna Izquierda: Mensaje y Acciones */}
        <div className="lg:col-span-7 space-y-4 sm:space-y-6">
          {/* Badge Institucional */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-100 dark:bg-valle-orange/20 border border-orange-200 dark:border-valle-orange/40 text-valle-orangedark dark:text-valle-orangelight text-xs sm:text-sm font-bold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-valle-orange" />
            <span>{isIndividuo ? 'Banca para Familias & Hogares' : 'Banca Corporativa & PyMEs'}</span>
          </div>

          {/* Título Principal */}
          <h1 className="font-display font-extrabold text-2xl sm:text-4xl lg:text-5xl leading-tight tracking-tight text-slate-900 dark:text-white">
            {isIndividuo ? (
              <>
                El sueño de tu casa, tu auto y tu futuro,{' '}
                <span className="text-valle-orange">hoy más cerca.</span>
              </>
            ) : (
              <>
                Financiamiento estratégico para el{' '}
                <span className="text-valle-orange">desarrollo de tu empresa.</span>
              </>
            )}
          </h1>

          {/* Subtítulo Cómodo (16px base) */}
          <p className="text-slate-700 dark:text-slate-200 text-sm sm:text-base lg:text-lg leading-relaxed font-normal max-w-2xl">
            {isIndividuo
              ? 'Accedé a préstamos personales y prendarios con cuotas fijas bajo Sistema Francés. Conocé tu tasa personalizada consultando con tu DNI en tiempo real.'
              : 'Líneas de crédito para adquisición de maquinaria pesada, camiones de logística y capital de trabajo. Cuentas remuneradas de tesorería y plazos fijos mayoristas.'}
          </p>

          {/* Botones de Acción Rápida (CTA) */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-1 sm:pt-2">
            <button
              type="button"
              onClick={onSimulateClick}
              className="px-6 py-3 bg-valle-orange hover:bg-valle-orangedark text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition flex items-center justify-center gap-2 group"
            >
              <span>{isIndividuo ? 'Simular Préstamo Familiar' : 'Simular Crédito PyME'}</span>
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>

            <button
              type="button"
              onClick={onDepositClick}
              className="px-5 py-3 bg-white dark:bg-white/10 hover:bg-slate-100 dark:hover:bg-white/20 text-slate-800 dark:text-white font-semibold text-sm sm:text-base rounded-xl border border-slate-300 dark:border-white/20 shadow-xs transition flex items-center justify-center gap-2"
            >
              <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <span>Invertir al 28.5% TNA</span>
            </button>
          </div>

          {/* Micro-Badges de Confianza */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-4 sm:pt-6 border-t border-slate-200 dark:border-valle-darkBorder text-xs sm:text-sm">
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300 font-medium">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Calificación en Línea</span>
            </div>
            <div className="flex items-center gap-2 text-slate-700 dark:text-slate-300 font-medium">
              <ShieldCheck className="w-4 h-4 text-valle-orange" />
              <span>Supervisado BCRA</span>
            </div>
            <div className="hidden sm:flex items-center gap-2 text-slate-700 dark:text-slate-300 font-medium">
              <Home className="w-4 h-4 text-valle-blue dark:text-sky-300" />
              <span>Valle Catamarqueño</span>
            </div>
          </div>
        </div>

        {/* Columna Derecha: Tarjeta Fotográfica de Alto Impacto con Carrusel Automático */}
        <div
          className="lg:col-span-5 relative group"
          onMouseEnter={() => setIsPaused(true)}
          onMouseLeave={() => setIsPaused(false)}
        >
          <div className="relative rounded-2xl sm:rounded-3xl overflow-hidden shadow-xl border-2 sm:border-4 border-white dark:border-valle-darkBorder bg-slate-900">
            {/* Imagen Activa con Transición Suave */}
            <div className="relative w-full h-64 sm:h-96 lg:h-[420px] overflow-hidden bg-slate-900">
              <img
                key={currentSlide.id}
                src={currentSlide.url}
                alt={currentSlide.titulo}
                className="w-full h-full object-cover transition-all duration-700 transform scale-100 group-hover:scale-105 animate-fade-in"
                loading="eager"
                decoding="async"
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
            </div>

            {/* Controles del Carrusel (Flechas Anterior / Siguiente) */}
            <div className="absolute top-4 right-4 flex items-center gap-1.5 z-20">
              <button
                type="button"
                onClick={handlePrev}
                title="Imagen anterior"
                className="p-2 rounded-xl bg-slate-950/70 hover:bg-slate-950 text-white backdrop-blur-md border border-white/20 transition shadow-sm"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleNext}
                title="Imagen siguiente"
                className="p-2 rounded-xl bg-slate-950/70 hover:bg-slate-950 text-white backdrop-blur-md border border-white/20 transition shadow-sm"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>

            {/* Contador de Slides e Indicador de Reproducción */}
            <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
              <span className="px-3 py-1 rounded-full bg-slate-950/75 backdrop-blur-md text-white text-xs font-mono font-bold border border-white/20">
                {String(currentIndex + 1).padStart(2, '0')} / {String(slides.length).padStart(2, '0')}
              </span>
              <button
                type="button"
                onClick={() => setIsPaused(!isPaused)}
                className="p-1 rounded-full bg-slate-950/60 backdrop-blur-md text-slate-300 hover:text-white border border-white/20 transition"
                title={isPaused ? 'Reanudar carrusel automático' : 'Pausar carrusel'}
              >
                {isPaused ? <Play className="w-3 h-3 text-emerald-400" /> : <Pause className="w-3 h-3 text-amber-400" />}
              </button>
            </div>

            {/* Cartela de Información y Contexto de la Foto */}
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-slate-950 via-slate-950/85 to-transparent p-6 text-white z-10">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <span className="inline-block px-2.5 py-0.5 bg-valle-orange text-white text-[11px] font-bold rounded-lg uppercase tracking-wider">
                  {currentSlide.tag}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] text-slate-300 font-medium">
                  <MapPin className="w-3 h-3 text-valle-orange" />
                  <span>{currentSlide.ubicacion}</span>
                </span>
              </div>

              <div className="font-display font-bold text-lg text-white leading-snug">
                {currentSlide.titulo}
              </div>
              <div className="text-xs sm:text-sm text-slate-200 mt-1 line-clamp-2">
                {currentSlide.descripcion}
              </div>

              {/* Indicadores de Posición (Puntos inferiores interactivos) */}
              <div className="flex items-center gap-1.5 mt-3 pt-2 border-t border-white/10">
                {slides.map((_, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setCurrentIndex(idx)}
                    title={`Ir a imagen ${idx + 1}`}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      currentIndex === idx
                        ? 'w-6 bg-valle-orange'
                        : 'w-1.5 bg-white/40 hover:bg-white/80'
                    }`}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HeroBanner;
