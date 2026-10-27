# 🏛️ Portafolio de Ingeniería de Software Financiero, Trading Algorítmico & Sistemas Cuantitativos

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-Engine_Core-orange.svg)](https://www.rust-lang.org/)
[![Architecture: Clean / Hexagonal](https://img.shields.io/badge/Architecture-Clean%20%2F%20Hexagonal-emerald.svg)](ENGINEERING_GUIDELINES.md)
[![Tests: 866 Passing](https://img.shields.io/badge/Tests-866%20Passed-brightgreen.svg)]()
[![Code Style: Strict Typing](https://img.shields.io/badge/Typing-Strict%20Mypy-blueviolet.svg)]()

Bienvenido al repositorio maestro de ingeniería financiera y software de misión crítica. Este ecosistema consolida cinco desarrollos completos que cubren desde **sistemas bancarios transaccionales y regulados (ALM / BCRA)**, pasando por **motores contables forenses**, hasta **terminales cuantitativas de futuros** y **bots de arbitraje algorítmico de alta concurrencia**.

Para conocer los principios de ingeniería, límites de complejidad por módulo (~500 líneas), diagramación y contratos de diseño previos a la implementación, consulte la guía metodológica transversal:
👉 **[ENGINEERING_GUIDELINES.md](ENGINEERING_GUIDELINES.md)**

---

## 🗂️ Proyectos del Ecosistema

```text
Proyectos para Git/
├── Banco Del Valle/                 # Core Bancario, Scoring Crediticio & ALM (Tesorería BCRA)
├── Bot P2P Binance/                 # Market Making Algorítmico P2P & Mitigación de Colisiones
├── Bot Trading Ripio Binance V2/    # Arbitraje Cripto/Fiat Cross-Exchange en Tiempo Real
├── Motor Programa Contable/         # Conciliación Bancaria Forense & Auditoría Fiscal CPCE
├── Nexus Quant Terminal/            # Terminal Cuantitativa Institucional (Python + Rust Engine)
├── ENGINEERING_GUIDELINES.md        # Estándares de Arquitectura, Flujo de Trabajo y Testing
└── README.md                        # Índice Maestro del Portafolio
```

---

## 🚀 Resumen Técnico de Cada Proyecto

### 1. [Banco Del Valle](./Banco%20Del%20Valle)
* **Dominio:** Banca Comercial, Scoring Crediticio Automatizado y Gestión de Tesorería (ALM).
* **Stack:** Python 3.11, FastAPI, SQLite (Transacciones ACID estrictas), React 18, Vite, Tailwind CSS, Pytest.
* **Aspectos Destacados:**
  - **Motor de Scoring Paramétrico:** Evaluación crediticia multivariable considerando afectación de ingresos, estabilidad laboral y comportamiento crediticio histórico.
  - **Terminal Ejecutiva de ALM (Asset & Liability Management):** Simulación macroeconómica en tiempo real de encajes bancarios, brechas de liquidez (*liquidity gaps*) y cumplimiento de normativas del Banco Central (BCRA).
  - **Portal Dual Integrado:** Home Banking para clientes particulares y Terminal de Gerencia con aceleración temporal para análisis de estrés de cartera.
  - **Validación:** **88 pruebas unitarias** pasando al 100%.

---

### 2. [Bot P2P Binance](./Bot%20P2P%20Binance)
* **Dominio:** Creación de Mercado Algorítmico (Market Making) en el libro P2P de Binance.
* **Stack:** Python 3.11, AsyncIO, WebSockets, Binance SAPI, Telegram Bot API, SQLite.
* **Aspectos Destacados:**
  - **Resolución de Colisiones Dinámicas:** Algoritmo de reposicionamiento de precios multicompetidor con histéresis anti-spam para evitar guerras de centavos destructivas.
  - **Guardrails Antiban y Gestión de Liquidez:** Detección de errores operativos de exchange (códigos 187040, 187006), balanceo dinámico de colaterales y auto-pausa preventiva ante desequilibrios de inventario.
  - **Control Operativo:** Telemetría en vivo, gestión de órdenes de arbitraje y panel interactivo vía Telegram.
  - **Validación:** **210 pruebas unitarias e integración** pasando al 100%.

---

### 3. [Bot Trading Ripio Binance V2](./Bot%20Trading%20Ripio%20Binance%20V2)
* **Dominio:** Arbitraje Cripto-Fiat entre Exchanges Locales e Internacionales.
* **Stack:** Python 3.11, AsyncIO, Ripio Trade API, Binance Public Market Depth, Telegram Bot Interface.
* **Aspectos Destacados:**
  - **Cálculo de Spread Neto en Tiempo Real:** Detección de oportunidades de arbitraje considerando comisiones por nivel (*taker/maker*), deslizamiento (*slippage*) e impuestos locales.
  - **Arquitectura de Riesgo Cero:** Modos de ejecución simulada con libro de órdenes real y salvaguardas de capital con órdenes condicionales inmediatas.
  - **Validación:** **14 pruebas unitarias** pasando al 100%.

---

### 4. [Motor Programa Contable](./Motor%20Programa%20Contable)
* **Dominio:** Auditoría Forense Contable, Conciliación Bancaria Multicuenta y Regulación Fiscal.
* **Stack:** Python 3.11, Flask / FastAPI, SQLite, Pandas, PyPDF2 / OCR, OpenPyXL.
* **Aspectos Destacados:**
  - **Conciliación Inteligente:** Algoritmo de cruce multivariado entre extractos bancarios de entidades tradicionales (Galicia, BBVA, Macro, Mercado Pago) y registros de libros mayores.
  - **Pipeline de Ingesta y OCR:** Normalización de fechas anómalas, recuperación de dígitos corrompidos por escaneo y validación de sumas de control según estándares CPCE.
  - **Trazabilidad y Saneamiento:** Registro inmutable de transacciones certificadas y mitigación de lotes duplicados.
  - **Validación:** **38 pruebas unitarias** pasando al 100%.

---

### 5. [Nexus Quant Terminal](./Nexus%20Quant%20Terminal)
* **Dominio:** Plataforma Cuantitativa Institucional de Futuros USDⓈ-M y Optimización Algorítmica.
* **Stack:** Python 3.11, Flask, Rust (Motor Genético compilado con FFI nativo), NumPy, Pandas, Optuna, Plotly.
* **Aspectos Destacados:**
  - **Núcleo Híbrido Python + Rust:** Optimización evolutiva hiper-vectorizada escrita en Rust para maximizar el Sharpe Ratio y minimizar el Drawdown en espacio de parámetros multidimensional.
  - **Modelo Barbell de 30 Días:** Asignación asimétrica de capital combinando preservación ultraconservadora con apuestas sistemáticas de alta convexidad.
  - **Simulación Monte Carlo Vectorizada 2D:** Pruebas de estrés y caminata temporal causal (*Walk-Forward*) para mitigar el sobreajuste (*overfitting*).
  - **Validación:** **516 pruebas unitarias, de integración y stress testing** pasando al 100%.

---

## 🧪 Resumen de Calidad y Suite de Pruebas

Todos los proyectos han sido auditados exhaustivamente para certificar **cero dependencias circulares, tipado estático riguroso y aislamiento completo de credenciales**:

| Proyecto | Archivos de Prueba | Pruebas Unitarias | Cobertura / Estado |
| :--- | :---: | :---: | :---: |
| **Banco Del Valle** | `tests_unitarios/` | **88** | ✅ 100% Passed |
| **Bot P2P Binance** | `tests/` | **210** | ✅ 100% Passed |
| **Bot Trading Ripio Binance V2** | `tests/` | **14** | ✅ 100% Passed |
| **Motor Programa Contable** | `webapp/backend/tests/` | **38** | ✅ 100% Passed |
| **Nexus Quant Terminal** | `tests/` | **516** | ✅ 100% Passed |
| **TOTAL ECOSISTEMA** | | **866** | **✅ 100% Passed (0 fallos)** |

Para ejecutar la verificación completa:
```powershell
# Banco Del Valle
Push-Location "Banco Del Valle"; python -m pytest tests_unitarios; Pop-Location

# Bot P2P Binance
Push-Location "Bot P2P Binance"; python -m pytest tests; Pop-Location

# Bot Trading Ripio Binance V2
Push-Location "Bot Trading Ripio Binance V2"; python -m pytest tests; Pop-Location

# Motor Programa Contable
Push-Location "Motor Programa Contable\webapp\backend"; python -m pytest tests; Pop-Location

# Nexus Quant Terminal
Push-Location "Nexus Quant Terminal"; python -m pytest tests; Pop-Location
```

---

## 🔒 Higiene de Seguridad y Configuración de Entornos

- **Cero Secretos Hardcodeados:** Ningún archivo contiene API keys, passwords reales o tokens de producción.
- **Configuración mediante `.env`:** Cada subproyecto cuenta con su archivo `.env.example` debidamente documentado con valores explicativos y seguros para arranque en entornos sandbox/demo.
- **Gestión de Datos:** Los datasets de mercado pesados se descargan bajo demanda mediante scripts deterministas presentes en cada directorio.
