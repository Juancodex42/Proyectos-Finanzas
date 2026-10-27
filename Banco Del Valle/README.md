# Banco del Valle — Scoring Calculator & Lending Engine

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4+-38B2AC?style=flat&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> **Plataforma cuantitativa integral de calificación de riesgo crediticio, gestión de tesorería y encajes regulatorios (BCRA), pricing macroeconómico dinámico y simulación temporal acelerada con interfaz web dual.**

---

## 📌 Resumen Ejecutivo

**Banco del Valle (Scoring Calculator & Lending Engine)** es un sistema financiero diseñado para resolver los tres desafíos críticos de una entidad de crédito moderna:
1. **Calificación de Riesgo y Mora Precisa:** Evalúa solicitantes cruzando el historial interno de atrasos con reportes de buró crediticio externo (**Veraz / BCRA**), calculando con exactitud matemática los días de mora y devengando punitorios diarios.
2. **Tesorería y Cumplimiento Normativo (ALM):** Administra la base de depósitos (**Plazos Fijos tradicionales y Cuentas Flexibles**), calculando en tiempo real el cumplimiento del **Efectivo Mínimo (Encajes)** exigido por el BCRA y el **Cashflow Seguro Prestable** para evitar descalces de liquidez.
3. **Pricing Macroeconómico:** Ajusta dinámicamente las tasas activas y pasivas incorporando expectativas de inflación (**REM del BCRA y consultoras privadas**) y el ciclo de actividad económica (**EMAE / PBI**).
4. **Simulación Temporal y Portal Dual:** Permite ejecutar una simulación acelerada (**1 segundo = 1 día**) donde se observa en tiempo real cómo los clientes depositan, solicitan créditos, pagan cuotas o caen en mora, todo reflejado en una interfaz web con **portal público aspiracional para clientes** y **dashboard cuantitativo para gerencia**.

---

## 🚀 Características Principales

* 🎯 **Motor de Scoring Multi-Factor (Individuos y Empresas):**
  * Tracking exacto de `dias_mora` cuota a cuota.
  * Segmentación precisa de riesgo individual (`categoria_laboral`: públicos, privados, jubilados, monotributistas) y corporativo (`tipo_societario`: SA, SRL, SAS, cooperativas).
  * Evaluación de relación cuota/ingreso (familias) y cuota/facturación operativa (PyMEs).
  * Consulta e integración de buró Veraz/BCRA (situaciones 1 a 6 y cheques rechazados) con persistencia de snapshots.
  * **Simulador Inteligente Conectado a BD:** Al ingresar DNI o CUIT, consulta en milisegundos los antecedentes en SQLite para emitir cotización con **Tasa Personalizada Real** y pre-aprobación sujeta a liquidez en tesorería.
* 🏦 **Gestión de Tesorería, P&L y Capacidad Prestable:**
  * Clasificación regulatoria de depósitos a la vista vs. a plazo.
  * Cálculo algorítmico del **Cashflow Seguro** deduciendo encajes, colchón precautorio y compromisos a vencer.
  * **P&L y Reinversión Automática:** El spread neto de intereses cobrados se capitaliza en el Patrimonio Neto y se inyecta directamente al Cashflow Seguro para ampliar la capacidad de colocar nuevos créditos.
  * Bloqueo preventivo de desembolsos si la liquidez pone en riesgo las reservas bancarias.
* 📈 **Sensibilidad Macroeconómica y Proyecciones Multi-Escenario:**
  * Aplicación de la Ecuación de Fisher: Tasa nominal ajustada por inflación esperada a 12 meses.
  * Ajuste de morosidad sistémica según la fase del ciclo económico (expansión vs. contracción).
  * **Dashboard de Proyecciones:** Gráfica de Ganancias y Patrimonio (Eje Y: Pesos $, Eje X: Meses/Semanas y horizontes a 1, 3 y 5 años) bajo 3 escenarios dinámicos: **Optimista**, **Base** y **Pesimista (Stress Test)**.
* ⏱️ **Motor de Tiempo Acelerado (Time-Warp Engine):**
  * Reloj virtual (`SimulationClock`) que corre cierres diarios (*Daily Ticks*).
  * Comportamiento estocástico: pagos puntuales, morosidad progresiva, renovaciones y retiros de depósitos.
  * Control de velocidad interactivo (1 seg = 1 día, pausa, salto diario).
* 🎨 **Frontend Web Dual (Paleta Catamarca Ciudad):**
  * **Portal Clientes:** Identidad visual cálida y profesional (Azul `#0F3A5D`, Naranja `#FF7A00` y Blanco), mensaje aspiracional (*"Vendemos un sueño"* / *Impulso PyME*), simuladores interactivos conectados a SQLite y sección *"Nuevas Inversiones (Alto Riesgo)"* con teaser interactivo (*Pronto: Acciones, Bonos, Índices y Derivados*).
  * **Portal Empleados / Gerencia:** Terminal ejecutiva con métricas patrimoniales, monitor de encajes en vivo, gráficos de dispersión de tasas y centro de simulación.
* 📑 **Motor Universal de Exportación:**
  * Extracción de datos con selector de fechas en **PDF oficial membretado**, **Excel (.xlsx)** y **CSV**.

---

## 📂 Arquitectura del Proyecto

El código está estructurado bajo principios de **Arquitectura Limpia** y regulado por la regla de **menos de 500 líneas por módulo**:

```text
Scoring calculator/
├── docs/                               # Documentación normativa, matemática, macro y diagramas
│   ├── normativa_encajes_bcra.md       # Régimen de Efectivo Mínimo BCRA
│   ├── multiplicador_y_cashflow_prestable.md # Fórmulas de liquidez y multiplicador
│   ├── margen_financiero_y_proyecciones_escenarios.md # P&L bancario y proyecciones
│   ├── proyecciones_inflacion_consultoras.md # REM, consultoras y Fisher
│   ├── proyecciones_macro_actividad_economica.md # EMAE, PBI y morosidad sistémica
│   ├── compliance_aml_fraude_bajas.md  # Normativa UIF, EBR y soft delete
│   ├── homebanking_ux_cuentas_sueldo.md# UX Home Banking y sueldos
│   ├── seguridad_autenticacion_credenciales.md # Bcrypt, JWT y RBAC
│   ├── diagrama_logica_negocio_banco.md# Diagrama de flujo financiero y ALM
│   ├── diagrama_usuarios_empresas_aml_bloqueos.md # Diagrama onboarding, AML y bloqueos
│   └── diagrama_plazos_fijos_flexibles_prestamos.md # Diagrama de colocaciones y captaciones
│
├── tests_unitarios/                    # Suite de pruebas unitarias (Pytest)
│
├── src/                                # BACKEND (Python / FastAPI / SQLite)
│   ├── domain/                         # Reglas de negocio puras (scoring, tesorería, compliance, macro)
│   ├── database/                       # Persistencia SQLite unificada y 10 repositorios
│   ├── services/                       # Seguridad (Bcrypt/JWT), buró Veraz y exportadores (PDF/XLS/CSV)
│   ├── simulation/                     # Reloj virtual, cierre diario y tráfico sintético
│   ├── api/                            # Endpoints REST y WebSockets para streaming en vivo
│   └── config.py                       # Parámetros regulatorios y umbrales de crédito
│
├── frontend/                           # FRONTEND (React / Vite / Tailwind CSS)
│   ├── src/components/common/          # Navbar, Footer, ExportModal, DateRangePicker, RegisterModal
│   ├── src/components/public/          # HeroBanner, LoanSimulator, CorporateSimulator, DepositSimulator
│   ├── src/components/client/          # ClientBalanceCard, TransferModal, DepositModal, FixedTermModal
│   ├── src/components/employee/        # KpiGrid, LiveRatesChart, ProfitProjectionsChart, SimController
│   ├── src/pages/                      # HomePage, ClientHomeBanking, Simuladores, EmployeeDashboard
│   ├── src/services/                   # Clientes HTTP y conexión WebSocket
│   └── src/styles/theme.css            # Paleta de colores Catamarca Ciudad
│
├── project.md                          # Documento maestro de especificación y diseño
└── README.md                           # Presentación ejecutiva del repositorio
```

---

## 📚 Documentación Técnica Detallada

Para consultar la fundamentación teórica, fórmulas y manuales normativos:
* 📄 [**`project.md`**](project.md): Documento maestro de diseño integral, esquemas de bases de datos y UX/UI.
* 🏛️ [**`docs/diagrama_logica_negocio_banco.md`**](docs/diagrama_logica_negocio_banco.md): Diagrama integral del funcionamiento del banco a nivel lógica de negocios.
* 🛡️ [**`docs/diagrama_usuarios_empresas_aml_bloqueos.md`**](docs/diagrama_usuarios_empresas_aml_bloqueos.md): Diagrama y protocolo de manejo de usuarios, empresas, AML y gestión de bloqueos (UIF).
* 💳 [**`docs/diagrama_plazos_fijos_flexibles_prestamos.md`**](docs/diagrama_plazos_fijos_flexibles_prestamos.md): Diagrama de manejo de plazos fijos, cuentas flexibles y préstamos amortizables.
* ⚖️ [**`docs/normativa_encajes_bcra.md`**](docs/normativa_encajes_bcra.md): Marco regulatorio de reservas bancarias mínimas.
* 🧮 [**`docs/multiplicador_y_cashflow_prestable.md`**](docs/multiplicador_y_cashflow_prestable.md): Mecánica del multiplicador bancario y liquidez segura.
* 💰 [**`docs/margen_financiero_y_proyecciones_escenarios.md`**](docs/margen_financiero_y_proyecciones_escenarios.md): P&L bancario, reinversión de ganancias y proyecciones multi-escenario (Optimista, Base, Pesimista).
* 📊 [**`docs/proyecciones_inflacion_consultoras.md`**](docs/proyecciones_inflacion_consultoras.md): Relevamiento REM y ecuaciones de tasas.
* 📉 [**`docs/proyecciones_macro_actividad_economica.md`**](docs/proyecciones_macro_actividad_economica.md): Impacto del EMAE/PBI en la morosidad.
* 🛡️ [**`docs/compliance_aml_fraude_bajas.md`**](docs/compliance_aml_fraude_bajas.md): Políticas KYC/AML de la UIF, bloqueo preventivo y ciclo de vida de cuentas (Soft Delete).
* 📱 [**`docs/homebanking_ux_cuentas_sueldo.md`**](docs/homebanking_ux_cuentas_sueldo.md): Experiencia de Home Banking, simulación de Juan José ($3M), cuentas sueldo y cancelación anticipada de plazos fijos.
* 🔐 [**`docs/seguridad_autenticacion_credenciales.md`**](docs/seguridad_autenticacion_credenciales.md): Seguridad bancaria, hashing Bcrypt/Argon2id, tokens JWT, roles RBAC y credenciales demo.
* 🧪 [**`tests_unitarios/README.md`**](tests_unitarios/README.md): Plan de pruebas unitarias, casos de prueba para scoring, tesorería, compliance y simulación.
* 📐 [**`.agents/skills/code-architecture-standards/SKILL.md`**](.agents/skills/code-architecture-standards/SKILL.md): Estándares de calidad de código y catálogo de funciones.

---

## 🛠️ Guía de Instalación y Ejecución Local

### 1. Prerrequisitos
* Python 3.11 o superior.
* Node.js 18 o superior y npm.

### 2. Configuración del Backend
```bash
# Navegar al directorio del proyecto
cd "Scoring calculator"

# Crear entorno virtual de Python
python -m venv venv

# Activar entorno virtual
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# En Linux/macOS:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos SQLite y servidor de desarrollo
uvicorn src.api.main:app --reload --port 8000
```

### 3. Configuración del Frontend
```bash
# En una terminal separada, ingresar a la carpeta frontend
cd "Scoring calculator/frontend"

# Instalar dependencias de Node
npm install

# Iniciar servidor de desarrollo
npm run dev
```

El portal web estará accesible en `http://localhost:5173` y la API con documentación Swagger interactiva en `http://localhost:8000/docs`.

---

## 🛡️ Estándares de Calidad y Buenas Prácticas

* **Límite de 500 Líneas:** Ningún módulo o componente excede las 500 líneas de código, garantizando alta cohesión y bajo acoplamiento.
* **Transacciones Atómicas (ACID):** Toda operación financiera (depósito, cobro o desembolso) actualiza simultáneamente los saldos de clientes y el balance general del banco en SQLite.
* **Separación de Responsabilidades:** El motor matemático de scoring opera como funciones puras desacopladas de la base de datos y la interfaz gráfica.
