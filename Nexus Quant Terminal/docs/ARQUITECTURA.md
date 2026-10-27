# 🏛️ Documento de Arquitectura de Software — Nexus Quant Terminal

## 1. Visión General & Estándar de Diseño
Nexus Quant Terminal implementa una arquitectura institucional con **`src-layout` genuino** conforme a PEP 517/518, complementada con modularización estricta en todas sus capas:
- **Backend Modular**: Enrutamiento desacoplado en Flask Blueprints, con descomposiciones de endpoints pesados en submódulos especializados.
- **Frontend Modular ES6**: Arquitectura basada en módulos de JavaScript puro sin bundlers pesados, con bus de eventos desacoplado y gestión de estado reactivo.
- **Sistema de Diseño CSS Modular**: Separación de tokens, layouts responsive, componentes interactivos y gráficos.
- **Plantillas Jinja2 Componentizadas**: `index.html` descompuesto en sub-plantillas semánticas.
- **Límite de Código Estricto**: Ningún archivo supera las 500 líneas (excepto motores numéricos puros y generadores de código).

---

## 2. Mapa de Módulos y Paquetes (`src/`)

```
Nexus Quant Terminal/
├── app.py                      # Host Flask ejecutable (< 60 líneas)
├── pytest.ini                  # pythonpath = src . con exclusiones formales
├── src/
│   ├── app.py                  # Fábrica de aplicación Flask (create_app)
│   ├── routes/                 # Flask Blueprints desacoplados (< 450 l cada uno)
│   │   ├── __init__.py         # Registrador central de Blueprints
│   │   ├── data_routes.py      # Endpoints de velas, pares e intervalos
│   │   ├── backtest_routes.py  # Backtest causal síncrono y streaming SSE (< 410 l)
│   │   ├── plan_routes.py      # Planes de apalancamiento clásico y 6 balas (< 120 l)
│   │   ├── genetic_routes.py   # Subproceso y streaming del optimizador Rust
│   │   ├── export_routes.py    # Descarga de reportes CSV/PDF y Pine Script v5
│   │   ├── execution_routes.py # Ejecución en vivo e interfaces de órdenes
│   │   ├── utils.py            # Helpers comunes de SSE, serialización y datasets
│   │   └── smart/              # Sub-módulo para el Piloto Automático Smart Mode
│   │       ├── __init__.py     # Exporta Blueprint smart_bp
│   │       ├── optimizer.py    # Búsqueda bayesiana y optimización multiactivo (< 400 l)
│   │       ├── barbell.py      # Lógica de distribución Barbell y 6 balas (< 330 l)
│   │       ├── monte_carlo.py  # Simulación estocástica y conos de volatilidad (< 105 l)
│   │       ├── stream_v1.py    # Streaming SSE de progreso en tiempo real (< 410 l)
│   │       └── helpers.py      # Transformaciones y validación de parámetros (< 420 l)
│   └── engine/                 # Motores Cuantitativos de Simulación y Optimización
│       ├── simulators/         # Triple Barrier Causal, matrices vectorizadas NumPy
│       ├── optimizers/         # Algoritmos genéticos, optimizadores de capital
│       ├── exporters/          # Pine Script v5, Python standalone, schemas
│       ├── ml_engine/          # Purged K-Fold CV, Meta-Labeling, Feature extraction
│       └── correlation.py      # Matriz de correlación de Pearson con candados de hilo
├── static/
│   ├── css/                    # Sistema de Diseño Slate / Obsidian Pro (< 450 l por archivo)
│   │   ├── style.css           # Tokens :root, reset universal y variables globales (401 l)
│   │   ├── layout.css          # Grid containers, headers, tabs, media queries (376 l)
│   │   ├── components.css      # Botones, tarjetas glass-card, inputs, badges (368 l)
│   │   └── charts.css          # Contenedores de gráficos y tooltips (338 l)
│   └── js/
│       ├── app.js              # Inicializador y despachador principal (419 l)
│       └── modules/            # 19 Módulos ES6 independientes (< 450 l por archivo)
│           ├── state.js        # Store reactivo global
│           ├── api.js          # Cliente HTTP unificado con fetch resiliente
│           ├── modals.js       # Manejador de diálogos y popups
│           ├── smart_mode.js   # Controlador del panel de Smart Mode
│           ├── charts.js       # Coordinador de gráficos
│           └── ...             # Componentes específicos de vista y ejecución
└── templates/
    ├── index.html              # Shell principal Jinja2 unificado (< 200 l)
    └── components/             # Fragmentos semánticos componentizados (< 350 l)
        ├── header.html         # Header institucional y switcher de modos
        ├── data_panel.html     # Selector de dataset, activos y temporalidades
        ├── backtest_panel.html # Controles del simulador causal
        ├── results_panel.html  # Métricas institucionales y equity curve
        ├── smart_panel.html    # Panel del piloto automático Smart Mode
        └── modals.html         # Modales de confirmación y exportación
```

---

## 3. Principios Arquitectónicos
1. **Causalidad Estricta y Cero Lookahead Bias**: Toda métrica y señal se computa sin filtraciones del futuro, validado por tests de invariancia temporal (`test_tier1_feature_coverage.py`).
2. **Confinamiento de Procesos Huérfanos**: La comunicación con el binario compilado en Rust (`genetic_optimizer.exe`) dispone de handlers de terminación atómica vía `process.kill()` en eventos de desconexión SSE.
3. **High-Performance Canvas Rendering**: Gráficos construidos sobre TradingView Lightweight Charts y Canvas 2D acelerado por hardware para renderizar 100,000+ velas sin degradación de framerate.

---

## 4. Garantías de Calidad y Testing
- **516 pruebas automatizadas en suite completa pytest (100% GREEN, 0 fallos)**.
- Suites cubren: Tiers 1 a 5 (adversarial stress testing, verificación de tokens CSS, conformidad WCAG AAA de contraste, validación cruzada causal, concordancia de 105 IDs del DOM).
