import React from 'react';
import { HeroBanner } from '../components/public/HeroBanner';
import { LoanSimulator } from '../components/public/LoanSimulator';
import { CorporateSimulator } from '../components/public/CorporateSimulator';
import { DepositSimulator } from '../components/public/DepositSimulator';
import { HighRiskInvestmentsTeaser } from '../components/public/HighRiskInvestmentsTeaser';
import { AboutSection } from '../components/public/AboutSection';

/**
 * HomePage — Vista principal del portal público de clientes (Contenedor optimizado a 1600px).
 */
export function HomePage({ segmento, onOpenRegister, onOpenLogin, onOpenExportModal }) {
  const scrollToSimulator = () => {
    const el = document.getElementById(
      segmento === 'INDIVIDUOS' ? 'simulador-prestamos' : 'simulador-empresas'
    );
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToDeposits = () => {
    const el = document.getElementById('simulador-inversiones');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-8 xl:px-12 py-8 space-y-10">
      {/* Hero Banner Dinámico */}
      <HeroBanner
        segmento={segmento}
        onSimulateClick={scrollToSimulator}
        onDepositClick={scrollToDeposits}
      />

      {/* Simuladores según Segmento Activo */}
      {segmento === 'INDIVIDUOS' ? (
        <LoanSimulator
          onOpenRegister={() => onOpenRegister && onOpenRegister('PERSONA')}
          onExportModal={onOpenExportModal}
        />
      ) : (
        <CorporateSimulator
          onOpenRegister={(tipo) => onOpenRegister && onOpenRegister(tipo || 'EMPRESA')}
          onExportModal={onOpenExportModal}
        />
      )}

      {/* Simulador de Inversiones */}
      <DepositSimulator onOpenRegister={onOpenRegister} />

      {/* Teaser de Nuevas Inversiones (Mercado de Capitales) */}
      <HighRiskInvestmentsTeaser />

      {/* Respaldo Institucional y Misión */}
      <AboutSection />
    </div>
  );
}

export default HomePage;
