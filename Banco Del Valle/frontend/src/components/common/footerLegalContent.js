/**
 * Contenido legal, normativo y datos institucionales del pie de página (Footer).
 * Incluye información oficial para Formulario ARCA 960/D, BCRA, SEDESA, UIF y Ley 24.240.
 */

export const MODAL_CONTENT = {
  institucional: {
    razonSocial: 'Banco del Valle S.A.',
    cuit: '30-71234567-8',
    domicilio: 'República 550, San Fernando del Valle de Catamarca (K4700)',
    telefono: '0800-888-VALLE (82553) | Lun a Vie 08:00 a 18:00',
    emailDefensa: 'usuariosfinancieros@bancodelvalle.com.ar',
    descripcion:
      'Banco del Valle S.A. es una entidad financiera regional comprometida con el progreso de las familias, comerciantes y el aparato productivo e industrial de San Fernando del Valle y toda la provincia de Catamarca.',
    copyright:
      '© 2026 Banco del Valle S.A. CUIT 30-71234567-8. Entidad Financiera autorizada por el Banco Central de la República Argentina. República 550, San Fernando del Valle de Catamarca, Argentina.',
  },
  qrSvgPath:
    'M2 2h8v8H2V2zm2 2v4h4V4H4zm10-2h8v8h-8V2zm2 2v4h4V4h-4zM2 14h8v8H2v-8zm2 2v4h4v-4H4zm14 0h4v4h-4v-4zm-4 4h4v4h-4v-4zm0-4h4v4h-4v-4zm4-4h4v4h-4v-4zm-4 0h4v4h-4v-4zM6 6h2v2H6V6zm10 0h2v2h-2V6zM6 16h2v2H6v-2z',
  dataFiscal: {
    titulo: 'ARCA — Formulario 960/D Data Fiscal',
    actividad: 'Servicios de la Banca Minorista y Entidades Financieras',
    domicilio: 'República 550, San Fernando del Valle de Catamarca',
    estado: 'Activo — Cumplimiento Fiscal Regular',
  },
  arrepentimiento: {
    titulo: 'Botón de Arrepentimiento',
    leyenda:
      'Conforme a la Ley 24.240 de Defensa del Consumidor y normas del BCRA, tenés derecho a revocar la aceptación de cualquier producto o servicio financiero contratado dentro del plazo de 10 (diez) días hábiles contados a partir de la fecha de contratación.',
    opciones: [
      'Préstamo Personal en Pesos',
      'Crédito PyME',
      'Tarjeta o Paquete de Cuenta',
      'Otro Servicio Financiero',
    ],
  },
  bajaServicios: {
    titulo: 'Solicitud de Baja de Servicios',
    leyenda:
      'Podés rescindir y dar de baja tus servicios contratados de forma simple y 100% digital, sin costo de rescisión conforme a las disposiciones del BCRA.',
    opciones: [
      'Caja de Ahorro / Paquete de Cuenta',
      'Tarjeta de Débito',
      'Servicio de Alertas SMS',
      'Cierre Definitivo de Cuenta',
    ],
  },
  redesHomologadas: [
    { label: 'RED LINK', variant: 'neutral' },
    { label: 'BANELCO', variant: 'neutral' },
    { label: 'TRANSFERENCIAS 3.0 / MODO', variant: 'emerald' },
    { label: 'INTERBANKING', variant: 'blue' },
    { label: 'VISA DÉBITO', variant: 'neutral' },
    { label: 'MASTERCARD', variant: 'neutral' },
  ],
};

export default MODAL_CONTENT;
