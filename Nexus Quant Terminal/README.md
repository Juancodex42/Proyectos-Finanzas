# Nexus Quant Terminal 🚀

> **Terminal Cuantitativo Institucional de Trading Clásico Asimétrico, Optimización Genética en Rust y Gestión de Capital Barbell.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-black.svg)](https://flask.palletsprojects.com/)
[![Rust](https://img.shields.io/badge/Rust-Cargo-orange.svg)](https://www.rust-lang.org/)
[![Tests](https://img.shields.io/badge/Tests-516%20Passed%20(100%25)-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Modular%20Blueprints-blueviolet.svg)]()

> [!IMPORTANT]
> **ENFOQUE DEL PROGRAMA: TRADING CLÁSICO ASIMÉTRICO (FOREX, CRIPTO SPOT Y FUTUROS)**  
> Nexus Quant Terminal opera bajo el modelo de **Trading Clásico con Método de Triple Barrera de Marcos López de Prado** (Stop Loss y Take Profit calibrados dinámicamente por múltiplos de ATR con ratios $R:R \ge 1:2$ a $1:5$, y timeout vertical). Cualquier mención a contratos de opciones binarias en el histórico de archivos corresponde al *Legacy Research* (etapa preliminar de experimentación científica ya superada y adaptada a trading clásico).

---

## 📌 Descripción General

**Nexus Quant Terminal** es una plataforma institucional diseñada para la investigación, optimización y ejecución sistemática de estrategias de trading clásico en mercados de criptomonedas y forex.


Combina un **núcleo de optimización genética ultra-rápido en Rust**, un **backend en Python/Flask modularizado en Blueprints**, y un **frontend interactivo de alto rendimiento** (TradingView Lightweight Charts v4, Chart.js v4 y Canvas 2D Retina).

---

## 💎 Características Principales

### 1. Estrategia Cuantitativa Barbell (Ciclo Causal de 30 Días)
* **Capital Base Protegido ($1,000 USD):** El patrimonio principal se mantiene en bajo riesgo (arbitraje P2P/Spot) y **nunca se compromete**.
* **Presupuesto de Riesgo ($200 USD/mes):** Financiado exclusivamente por el rendimiento mensual del arbitraje (20%).
* **6 Balas de $33.33 USD:** Si se pierden las 6 balas en un mes, el bot pausa automáticamente las operaciones hasta completar el ciclo de **30 días calendario**, blindando matemáticamente el capital contra rachas negativas consecutivas.

### 2. Trading Clásico con Método de Triple Barrera
* Implementación del modelo de **Marcos López de Prado**:
  * **Barrera 1 (Stop Loss horizontal):** Basada en múltiplos dinámicos de ATR.
  * **Barrera 2 (Take Profit horizontal):** Ratios asimétricos R:R (1:2 a 1:5).
  * **Barrera 3 (Timeout vertical):** Salida a mercado tras $M$ velas.
* Cero Lookahead Bias y validación cruzada **Walk-Forward Causal** (Expanding Window con purga y embargo).

### 3. Algoritmo Genético en Rust (`genetic_optimizer.exe`)
* Aceleración nativa de búsqueda de hiperparámetros sobre millones de combinaciones.
* Control estricto de ciclo de vida: terminación instantánea (`process.kill()`) ante desconexiones SSE, eliminando procesos huérfanos.

### 4. Piloto Automático (Smart Mode)
* Optimización con 1 solo clic.
* Filtrado de activos no correlacionados (Pearson $< 0.65$).
* Ranking Top-5 de estrategias institucionales.
* Escalera de reinversión compuesta Paroli ($N=3$) y matrices de transición de Markov.
* Simulación Monte Carlo de 5,000 caminos con conos de volatilidad $P_5 \dots P_{95}$.

---

> [!NOTE]
> Para el desglose técnico detallado de módulos, contratos y patrones de diseño, consulte [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

## 🏛️ Arquitectura del Sistema

```
nexus-quant-terminal/
├── app.py                     # Host Flask central ultraligero (< 60 líneas)
├── pytest.ini                 # pythonpath = src . con exclusiones formales
├── docs/                      # 📚 Especificaciones cuantitativas, UI/UX y ARQUITECTURA.md
├── src/                       # Arquitectura src-layout genuina (< 450 líneas por archivo)
│   ├── app.py                 # Fábrica de aplicación Flask (create_app)
│   ├── routes/                # Flask Blueprints desacoplados (< 450 l cada uno)
│   │   ├── backtest_routes.py # Backtest causal síncrono y streaming SSE (< 410 l)
│   │   ├── plan_routes.py     # Planes de apalancamiento clásico y 6 balas (< 120 l)
│   │   ├── data_routes.py     # Endpoints de velas y catálogo de pares
│   │   ├── genetic_routes.py  # Subproceso seguro Rust con process.kill()
│   │   ├── export_routes.py   # Descargas CSV, reportes HTML/PDF, Pine Script v5
│   │   └── smart/             # Sub-módulo para Smart Mode (< 420 l por componente)
│   │       ├── optimizer.py   # Optimización Bayesiana multiactivo
│   │       ├── barbell.py     # Lógica Barbell y asignación asimétrica
│   │       ├── monte_carlo.py # Simulación estocástica y conos de volatilidad
│   │       └── stream_v1.py   # Streaming SSE de progreso en tiempo real
│   │
│   └── engine/                # Motores Cuantitativos de Simulación y Optimización
│       ├── simulators/        # Triple Barrier Causal, matrices vectorizadas NumPy
│       ├── optimizers/        # Algoritmos genéticos, optimizadores de capital
│       ├── exporters/         # Pine Script v5, Python standalone, JSON schemas
│       ├── ml_engine/         # Purged TimeSeries CV, Feature Extractor, Meta-Labeler
│       └── correlation.py     # Matriz de correlación Pearson con Threading Lock
│
├── static/
│   ├── css/                   # Sistema de Diseño Slate/Obsidian modular (< 450 l por archivo)
│   │   ├── style.css          # Design Tokens :root y CSS reset (401 l)
│   │   ├── layout.css         # Grid system, containers, media queries responsive (376 l)
│   │   ├── components.css     # Botones, glass-cards, inputs y badges (368 l)
│   │   └── charts.css         # Contenedores de gráficos y tooltips (338 l)
│   │
│   └── js/                    # Frontend modular ES6 sin dependencias de bundler
│       ├── app.js             # Despachador principal (< 420 l)
│       └── modules/           # 19 Módulos ES6 desacoplados (< 450 l cada uno)
│
├── templates/                 # Plantillas Jinja2 componentizadas (< 350 l por fragmento)
│   ├── index.html             # Shell principal unificado
│   └── components/            # Fragmentos semánticos (header, panels, modals)
│
└── tests/                     # 516 pruebas automatizadas (100% PASS)
```

---

## 🚀 Instalación y Puesta en Marcha

### Prerrequisitos
* Python 3.11 o superior.
* Navegador moderno (Chrome, Edge, Firefox, Brave).
* **Motor Genético en Rust:** El ejecutable de alta velocidad `genetic_optimizer.exe` se encuentra **precompilado para Windows x64**, por lo que **no es necesario tener instalado Rust ni Cargo** para ejecutar la terminal. *(Opcional: Si deseas compilarlo desde el código fuente en Linux/macOS, se requiere Rust 1.75+ y ejecutar `cargo build --release`).*

### 1. Preparar el entorno e instalar dependencias
```bash
# Navegar al directorio
cd "Nexus Quant Terminal"

# Crear entorno virtual (opcional pero recomendado)
python -m venv venv
venv\Scripts\activate  # En Windows

# Instalar librerías requeridas
pip install -r requirements.txt

# Configurar variables de entorno (opcional)
copy .env.example .env
```

### 2. Ejecutar la Suite de Pruebas
Para verificar la integridad matemática y de software:
```bash
pytest -q
```
*Debe reportar 516 passed (100% PASS) sin errores.*

### 3. Iniciar el Servidor Local
```bash
python app.py
```
O ejecutando directamente el script de acceso rápido en Windows:
```bash
run_nexus_terminal.bat
```

Abre en tu navegador:
```
http://localhost:5001
```
*(El puerto por defecto es 5001, calibrado dinámicamente mediante la variable de entorno `PORT`).*

---

## 🛡️ Seguridad y Resiliencia de Software

* **Protección ante Desconexión SSE:** Cierre limpio forzoso de subprocesos (`process.kill()`) si el usuario cierra la ventana.
* **Control de Hilos:** Interrupción reactiva en simulación multihilo mediante `threading.Event`.
* **Streaming WebSocket con Backoff:** Reconexión automática exponencial en caso de microcortes de red y cambio transparente a polling REST.
* **Búfer de Memoria Limitado:** Las velas en vivo se acotan estrictamente a un máximo de 1,500 en memoria RAM mediante FIFO (`shift()`).
* **Sanitización Exhaustiva:** Respuestas HTTP 400 limpias ante entradas numéricas fuera de rango o malformadas.

---

## 📄 Licencia

Uso privado e institucional para investigación cuantitativa. Todos los derechos reservados.
