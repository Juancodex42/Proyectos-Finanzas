import React from 'react';

/**
 * BrandLogo — Isotipo B+V y Logotipo Oficial Banco del Valle
 * Identidad visual inspirada en Catamarca Ciudad (Azul #0F3A5D y Naranja #FF7A00).
 */
export function BrandLogo({ size = 'md', variant = 'light', showText = true, className = '' }) {
  const iconSizes = {
    sm: 'w-7 h-7',
    md: 'w-9 h-9',
    lg: 'w-11 h-11 sm:w-12 sm:h-12',
    xl: 'w-16 h-16'
  };

  const textSizes = {
    sm: 'text-base',
    md: 'text-xl',
    lg: 'text-2xl sm:text-[1.65rem]',
    xl: 'text-3xl'
  };

  const gapSizes = {
    sm: 'gap-2',
    md: 'gap-2.5',
    lg: 'gap-3 sm:gap-3.5',
    xl: 'gap-4'
  };

  const isLight = variant === 'light'; // Text on dark background

  return (
    <div className={`flex items-center ${gapSizes[size] || 'gap-2.5'} select-none ${className}`}>
      {/* Isotipo Vectorial Geométrico B+V */}
      <div className={`relative flex-shrink-0 ${iconSizes[size]}`}>
        <svg viewBox="0 0 100 100" fill="none" className="w-full h-full drop-shadow-sm">
          {/* Contenedor Cuadrado Redondeado Azul Institucional */}
          <rect width="100" height="100" rx="22" fill="#0F3A5D" />
          <rect x="2" y="2" width="96" height="96" rx="20" stroke="#1E527D" strokeWidth="2" opacity="0.6" />

          {/* Letra B y Cerros (Trazos Blancos) */}
          <path
            d="M26 24V76H46C56 76 63 70 63 61C63 54.5 58 50 51 49C57 47.5 61 43.5 61 37C61 29 55 24 45 24H26ZM36 33H45C50 33 53 35.5 53 39C53 42.5 50 45 45 45H36V33ZM36 53H46C51.5 53 55 56 55 60C55 64 51.5 67 46 67H36V53Z"
            fill="#FFFFFF"
            fillOpacity="0.95"
          />

          {/* Letra V en Naranja Cálido (Valle y Sol) */}
          <path
            d="M48 42L61 74L74 42H83L66 82C64.5 85 61.5 86.5 58.5 85C56.5 84 55 82.5 54 80.5L39 42H48Z"
            fill="#FF7A00"
          />
          <circle cx="61" cy="42" r="5" fill="#FFA043" />
        </svg>
      </div>

      {/* Wordmark Tipográfico */}
      {showText && (
        <div className={`font-display font-bold tracking-tight leading-none ${textSizes[size]}`}>
          <span className={isLight ? 'text-white' : 'text-valle-blue'}>BANCO</span>{' '}
          <span className="text-valle-orange font-semibold">DEL VALLE</span>
        </div>
      )}
    </div>
  );
}

export default BrandLogo;
