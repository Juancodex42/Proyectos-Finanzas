# 📐 Engineering Guidelines & Development Methodology
### Estándares de Arquitectura, Flujo de Trabajo y Buenas Prácticas

> **Quick Navigation / Navegación Rápida:**  
> 🌐 `[ES]` **[Versión en Español](#es-versión-en-español)**  
> 🌐 `[EN]` **[English Version](#en-english-version)**

---

# 🌐 [ES] Versión en Español

### Propósito del Documento
Este documento detalla la metodología integral, estándares de arquitectura, políticas de calidad y el flujo de diseño y desarrollo aplicado en este proyecto. Describe el proceso paso a paso: desde la recopilación documental y el diseño de contratos antes de escribir una sola línea de código, hasta la estructura modular, los límites estrictos de complejidad, el testing unitario y la orquestación avanzada de agentes de software con *Skills*.

---

## 1. Principio Fundamental: Cero Líneas de Código sin Diseño Previo

Este principio es universal: **aplica a cualquier tipo de software** (sistemas bancarios, bots de trading algorítmico, terminales cuantitativas, APIs o herramientas de infraestructura). No se programa por intuición ni se improvisa sobre la marcha.

Todo desarrollo sigue este **paso a paso riguroso antes de crear o modificar código fuente**:

```text
[ 1. Recopilación Documental ] ➔ [ 2. Diseño de Contratos e I/O ] ➔ [ 3. Diagramación de Flujos ] ➔ [ 4. Diseño de Tests ] ➔ [ 5. Implementación Modular ]
```

### Paso 1: Recopilación Documental en la carpeta `/docs`
Antes de programar, se centraliza toda la verdad teórica, normativa o técnica en archivos Markdown dentro de `/docs`:
- **Normativas y Reglas:** Normativas legales, financieras o bancarias (ej. encajes y tasas mínimas del BCRA, requerimientos UIF/AML).
- **Especificaciones de APIs Externas:** Endpoints de exchanges, burós de crédito, protocolos WebSockets y límites de rate limit.
- **Modelado Matemático:** Fórmulas financieras (sistema francés, TIR, TNA/TEA), ratios de apalancamiento, modelos estocásticos o algoritmos de scoring.
- **Requerimientos Funcionales:** Casos de uso y especificaciones completas del comportamiento esperado.

### Paso 2: Diseño de Contratos de Datos e Interfaces (Previo a la Implementación)
Antes de escribir la lógica interna de cualquier módulo, se definen formalmente sus **contratos de entrada y salida (I/O)**:
- Tipos de datos exactos de entrada y salida (parámetros y valores de retorno).
- Esquemas de request/response para APIs HTTP y WebSockets.
- Excepciones esperadas, validaciones y códigos de error normalizados.  
*Regla inquebrantable:* Si los contratos no están definidos y aprobados, la implementación de código tiene prohibido comenzar.

### Paso 3: Diagramación de Lógica y Flujos de Estado
Se definen los diagramas de secuencia, árboles de decisión y máquinas de estados en `/docs`. Esto garantiza que los casos de borde (ej. saldos insuficientes, desconexiones de red, volatilidad anómala) estén resueltos analíticamente antes de escribir una sola línea de código ejecutable.

### Paso 4: Definición de Casos de Prueba (Criterios de Aceptación)
Se establecen de antemano qué valores exactos deben arrojar las funciones ante escenarios nominales y casos límite.

---

## 2. Arquitectura de Carpetas y Separación Estricta de Capas

El proyecto se estructura bajo una separación limpia y predecible de responsabilidades (Clean / Hexagonal Architecture):

```text
Nombre_del_Proyecto/
├── docs/                     # 1. FUENTE DE VERDAD: Documentación, normativas, fórmulas y diagramas
├── tests_unitarios/          # 2. VALIDACIÓN: Suite exhaustiva de pruebas unitarias (Pytest)
├── src/                      # 3. BACKEND / MOTOR CENTRAL
│   ├── domain/               # Capa de Dominio (Lógica pura y reutilizable)
│   │   ├── models.py         # Estandarización transversal: Dataclasses y esquemas tipados
│   │   └── [modulos].py      # Funciones matemáticas, scoring y reglas puras
│   ├── database/             # Capa de Persistencia (SQLite / SQL)
│   │   ├── connection.py     # Gestión de conexiones y transacciones ACID
│   │   └── repositories/     # Repositorios especializados por entidad (sin lógica de negocio)
│   ├── services/             # Servicios de integración externa (seguridad, exportaciones, APIs)
│   ├── simulation/           # Motores de tiempo, eventos y simulación
│   ├── api/                  # Exposición de endpoints (FastAPI / WebSockets)
│   └── config.py             # Configuración y variables de entorno tipadas
└── frontend/                 # 4. FRONTEND (Si aplica: React / Vite / Tailwind CSS)
    └── src/
        ├── components/       # Componentes desacoplados (UI pura)
        ├── pages/            # Vistas principales de la aplicación
        └── services/         # Clientes de consumo de API y WebSockets
```

---

## 3. Modularidad, Cohesión y Límites Físicos Estrictos

Para evitar el código espagueti y los archivos monolíticos inmanejables, se aplican reglas fijas:

1. **Límite de Referencia: ~500 Líneas por Archivo:**  
   Los archivos de código (`.py`, `.js`, `.jsx`, `.sql`) se diseñan en torno a un techo de referencia de **~500 líneas de código** (con un margen de tolerancia de hasta un ~10% cuando sea necesario preservar la cohesión semántica de un módulo).  
   *Alerta preventiva:* Si un módulo supera las 400–450 líneas, se analiza su descomposición en submódulos delegados o componentes especializados más pequeños.
2. **Alta Cohesión (Funciones pertenecientes al Módulo):**  
   Cada módulo contiene únicamente funciones directamente relacionadas con su propósito temático. Si una función resuelve cálculo de mora, pertenece a `scoring.py`; si calcula encajes, pertenece a `treasury.py`. No existen archivos genéricos tipo `utils.py` gigantes ni bolsas de funciones huérfanas.
3. **Principio de Responsabilidad Única (SRP):**  
   Cada función realiza una única tarea y la ejecuta a la perfección. Nombres expresivos compuestos por `verbo_objeto` (ej. `calcular_encaje_requerido`, `determinar_decision_riesgo`).

---

## 4. Trazabilidad Minimalista: Regla de los Encabezados Breves

Para mantener el código limpio y legible sin saturarlo con comentarios innecesarios, se prohíbe el código sobre-comentado. El código debe ser auto-explicativo mediante nombres expresivos y tipado estático (`typing`).

### La regla del Header de 2 a 3 renglones:
Cada archivo o módulo debe iniciar obligatoriamente con un *docstring* conciso que cumpla tres condiciones:
1. Describir la responsabilidad del módulo.
2. Declarar qué algoritmos o procesos ejecuta.
3. Referenciar de manera exacta el archivo de especificación en `/docs`.
4. **No superar los 3 renglones de longitud** para no acaparar espacio visual ni desviar la atención.

**Ejemplo estándar:**
```python
"""
Módulo de cálculo de encajes mínimos y riesgo de liquidez bancaria.
Aplica el algoritmo de Cashflow Seguro y reservas según normativa BCRA.
Referencia de diseño: docs/normativa_encajes_bcra.md
"""
```

---

## 5. Modelos Estandarizados (`models.py`) y Capa de Dominio Pura

### Estandarización transversal con `models.py`:
- No se utilizan diccionarios genéricos ni estructuras dinámicas no controladas para mover información en el sistema.
- Todas las entidades (personas, cuentas, transacciones, órdenes de compra, balances) se definen formalmente en `models.py` utilizando **Dataclasses** o **Pydantic**.
- Esto garantiza contratos inmutables, validación estricta de tipos en tiempo de desarrollo y autocompletado en el IDE.

### Dominio Puro y Reutilización de Funciones:
- La carpeta `domain/` contiene **cálculos matemáticos, financieros y algoritmos puros**.
- **Regla de Pureza:** Las funciones de dominio son puras (sin efectos secundarios, sin llamadas a red, sin consultas a bases de datos ni escritura en disco). Reciben datos validados y devuelven un resultado determinista.
- **Máxima Reutilización:** Gracias a este desacoplamiento, una misma función matemática (ej. cálculo de amortización francesa o volatilidad de mercado) se reutiliza de forma transparente en el simulador en tiempo real, en la API pública, en exportaciones PDF y en los tests unitarios, sin duplicar código.

---

## 6. Metodología de Testing Unitario

La estabilidad del sistema se valida mediante suites de pruebas automatizadas con **Pytest**, diseñadas antes y durante la codificación:

1. **Aislamiento Total:**  
   Los tests de dominio no requieren bases de datos en disco ni servicios externos activos; utilizan estructuras en memoria (`:memory:`) y datos simulados (*fixtures*).
2. **Cobertura de Casos Críticos:**  
   - **Cálculos matemáticos nominales:** Verificación contra resultados teóricos documentados en `/docs`.
   - **Casos de borde (*Edge cases*):** Tasa nominal cero, montos negativos, plazos mínimos y máximos, usuarios bloqueados.
   - **Manejo de excepciones:** Validación de que el sistema falle de forma controlada ante datos inválidos.
3. **Determinismo:**  
   Un test nunca depende del reloj real del sistema ni de conexiones a internet; todo comportamiento temporal se simula mediante relojes virtuales controlados.

---

## 7. Estrategia de Versionado Git

Dado que el desarrollo es conducido individualmente, la estrategia de versionado equilibra agilidad extrema con rigor profesional:

* **Trunk-Based Development con Integración Continua:**  
  Se trabaja directamente sobre la rama principal (`main` / `master`) mediante commits atómicos y continuos.
* **Política de Commits Verdes:**  
  Ningún commit se integra a la rama principal sin haber superado el 100% de la suite de tests unitarios locales.
* **Conventional Commits:**  
  Cada commit documenta con precisión su propósito:
  - `feat:` Nuevas funcionalidades validadas contra la documentación previa.
  - `fix:` Correcciones puntuales en casos de borde.
  - `refactor:` Mejoras de estructura interna respetando el límite de 500 líneas.
  - `test:` Incorporación o expansión de casos de prueba.
  - `docs:` Actualizaciones en especificaciones y contratos.
* **Preparación para Equipos:**  
  La modularidad del diseño permite que, al incorporarse más desarrolladores, el proyecto pase de inmediato a un flujo de **Feature Branches y Pull Requests** con validaciones automáticas por CI/CD.

---

## 8. Ingeniería Aumentada por IA: Orquestación Multi-Agente con *Skills*

El software es diseñado y desarrollado mediante flujos avanzados de **Ingeniería Aumentada por Inteligencia Artificial (AI-Augmented Engineering)**, sustentados en la orquestación de agentes con directrices arquitectónicas estrictas, **agentes adversariales** para pruebas de estrés y rotura, **comprobación MRE (Minimal Reproducible Example)** para el aislamiento determinista de bugs, y la **supervisión del ojo humano en una simbiosis estricta**:

```text
[ Ingeniero Humano: Arquitecto Líder ] 
       │ 
       ▼ (Diseño de Specs, Contratos, MREs y Skills)
[ Agente Orquestador / Multi-Agente ] 
       │ 
       ├──► [ Agente Constructor: Código Modular < 500 líneas ]
       │ 
       └──► [ Agente Adversarial: Fuzzing, Estrés y Rompimiento ]
              │
              ▼
       [ Validación MRE + Cobertura Total de Tests Verdes ]
```

1. **Simbiosis Estricta y Supervisión Humana (*Human-in-the-Loop*):**  
   El ingeniero actúa como Arquitecto en Jefe y auditor final: concibe la lógica del problema, diseña las especificaciones en `/docs`, formula los contratos de datos y establece los criterios de aceptación. La IA asiste y acelera bajo supervisión activa; ninguna decisión arquitectónica queda a merced de la autonomía ciega del modelo.
2. **Agentes Adversariales y Fuzzing:**  
   Se implementan agentes con rol antagónico cuya única función es intentar vulnerar o romper los algoritmos mediante inyección de inputs malformados, escenarios de altísima volatilidad, concurrencia forzada y búsqueda de fugas de precisión matemática.
3. **Comprobación MRE de Bugs (Minimal Reproducible Example):**  
   Ningún bug se corrige sobre suposiciones. Cuando se detecta una anomalía, se construye un **MRE** (un test mínimo que reproduce el fallo en aislamiento estricto). Solo cuando el test falla de manera predecible y reproducible, se aplica la corrección quirúrgica hasta volver el test verde, previniendo regresiones a futuro.
4. **Uso de *Skills* Especializados:**  
   Se definen archivos de habilidades (*Skills*, como `code-architecture-standards`) que cargan en el contexto de los agentes las directrices inmutables:
   - Prohibición de superar 500 líneas por módulo.
   - Respeto irrestricto de la separación de carpetas (`docs`, `src/domain`, `database`, `api`).
   - Obligación de usar modelos tipados y headers de trazabilidad de 2 a 3 renglones.
5. **Barrera de Calidad Infranqueable:**  
   Todo código generado o asistido por agentes debe compilar, respetar los límites de modularidad, sobrevivir a los agentes adversariales y pasar el 100% de los tests unitarios antes de ser aceptado.
6. **Protección de Propiedad Intelectual (*Alpha Sanitization*) y Modo Demo Auto-Contenido (`.bat`):**  
   En sistemas cuantitativos, motores de arbitraje y bots financieros, las heurísticas propietarias de negocio (*Alpha*: spreads finos, filtros privados de contrapartes y calibraciones en vivo) se parametrizan con valores sintéticos/académicos de demostración antes de su publicación en repositorios públicos. Asimismo, cada proyecto incorpora un **Lanzador Interactivo (`.bat`) con Modo Demo / Sandbox sin necesidad de API Keys reales**, permitiendo a reclutadores y auditores técnicos verificar el funcionamiento completo en vivo y ejecutar la suite de pruebas con un solo clic.

---

## 9. Conclusión y Valor Técnico
> Este repositorio refleja un proceso de ingeniería maduro: **nada se deja al azar ni a la improvisación**. La combinación de documentación exhaustiva previa, arquitectura limpia desacoplada, límites estrictos de modularidad, pruebas unitarias rigurosas y gobierno sobre herramientas de IA garantiza software robusto, auditable y listo para producción.

---
---

# 🌐 [EN] English Version

### Document Purpose
This document details the comprehensive engineering methodology, architectural standards, quality assurance policies, and end-to-end design and development workflows applied throughout this project. It outlines the step-by-step process: from upfront documentation and contract-first design before writing a single line of code, to modular physical limits, deterministic unit testing, and advanced multi-agent software orchestration governed by *Skills*.

---

## 1. Core Principle: Zero Lines of Code Without Upfront Design

This principle is universal: **it applies to any category of software** (banking cores, algorithmic trading bots, quantitative terminals, APIs, or infrastructure tooling). Software is never written based on intuition or improvised on the fly.

All development adheres to this **strict step-by-step pipeline before authoring or modifying source code**:

```text
[ 1. Docs Gathering ] ➔ [ 2. Contract & I/O Design ] ➔ [ 3. Logic & Flow Diagrams ] ➔ [ 4. Test Case Design ] ➔ [ 5. Modular Implementation ]
```

### Step 1: Upfront Documentation Gathering in `/docs`
Before touching code, the theoretical, regulatory, or technical single source of truth is centralized as Markdown documents within `/docs`:
- **Regulations & Business Frameworks:** Legal, banking, or financial standards (e.g., central bank reserve ratios, interest rate guidelines, AML/KYC compliance).
- **External API Specifications:** Exchange endpoints, credit bureau specs, WebSocket protocols, and rate-limiting behaviors.
- **Pure Mathematical Modeling:** Financial formulas (amortization schedules, IRR, nominal/effective rates), leverage matrices, stochastic models, or custom scoring logic.
- **Functional Requirements:** Complete system use cases and state transitions.

### Step 2: Contract-First & Interface Design (Prior to Implementation)
Before writing internal module logic, all **Input/Output (I/O) contracts** are formally specified:
- Exact parameter and return types.
- Request and response schemas for REST APIs and WebSockets.
- Expected domain exceptions, validation rules, and normalized error responses.  
*Inviolable Rule:* If contracts are not explicitly designed and approved, code authoring is prohibited from starting.

### Step 3: Logic Diagramming & State Transition Flows
Sequence diagrams, decision trees, and state machines are modeled inside `/docs`. This ensures that all critical edge cases (e.g., insufficient balance, network timeouts, abnormal volatility spikes) are solved analytically before a single line of executable code is written.

### Step 4: Test Case Formulation (Acceptance Criteria)
Deterministic target outputs and boundary assertions are defined upfront for every scenario.

---

## 2. Directory Architecture & Layer Decoupling

The project implements a decoupled Clean / Hexagonal Architecture pattern with predictable separation of concerns:

```text
Project_Root/
├── docs/                     # 1. SOURCE OF TRUTH: Documentation, regulations, math & diagrams
├── tests_unitarios/          # 2. VALIDATION: Comprehensive automated test suite (Pytest)
├── src/                      # 3. BACKEND / CORE ENGINE
│   ├── domain/               # Domain Layer (Pure, reusable business logic)
│   │   ├── models.py         # Cross-system standardization: Typed dataclasses & entities
│   │   └── [modules].py      # Pure mathematical functions, scoring & business rules
│   ├── database/             # Persistence Layer (SQLite / SQL)
│   │   ├── connection.py     # Connection pool & ACID transaction management
│   │   └── repositories/     # Entity repositories (zero business logic)
│   ├── services/             # Integrations (security, exports, external APIs)
│   ├── simulation/           # Time-series engines, virtual clocks & live events
│   ├── api/                  # Exposure layer (FastAPI routers & WebSockets)
│   └── config.py             # Strongly-typed environment configuration
└── frontend/                 # 4. FRONTEND (If applicable: React / Vite / Tailwind CSS)
    └── src/
        ├── components/       # Decoupled UI components (pure presentation)
        ├── pages/            # Application views
        └── services/         # API HTTP & WebSocket client consumers
```

---

## 3. High Modularity, Cohesion & Strict Physical Code Limits

To eliminate spaghetti code and monolithic, unmaintainable files, strict rules are enforced:

1. **Reference Limit: ~500 Lines per File:**  
   Code files (`.py`, `.js`, `.jsx`, `.sql`) are engineered around a reference ceiling of **~500 lines of code** (with a pragmatic ~10% tolerance margin when preserving semantic cohesion is preferable to artificial splitting).  
   *Preventive threshold:* When any module exceeds 400–450 lines, it is evaluated for refactoring into delegated sub-modules or smaller specialized components.
2. **High Cohesion (Domain-Bound Functions):**  
   Each module houses only functions directly bound to its specific purpose. If a function calculates delinquency days, it belongs in `scoring.py`; if it calculates reserve ratios, it belongs in `treasury.py`. Generic catch-all files like `utils.py` are strictly banned.
3. **Single Responsibility Principle (SRP):**  
   Each function executes one single task and does so flawlessly. Expressive semantic naming convention: `verb_noun` (e.g., `calculate_required_reserve`, `determine_risk_decision`).

---

## 4. Minimalist Traceability: The 2-3 Line Header Rule

To preserve code cleanliness and avoid visual fatigue, over-commented code is strictly forbidden. The code must be self-documenting through expressive identifiers and static type annotations (`typing`).

### The 2-3 Line Header Rule:
Every module begins with a concise docstring that satisfies three criteria:
1. Summarizes the module's core responsibility.
2. Identifies the primary algorithms or processes executed.
3. Provides a direct link to the corresponding specification document in `/docs`.
4. **Does not exceed 3 lines** to avoid cluttering vertical space.

**Standard Header Example:**
```python
"""
Bank minimum liquidity reserve computation module.
Implements the Safe Cashflow algorithm and BCRA reserve requirements.
Design Reference: docs/normativa_encajes_bcra.md
"""
```

---

## 5. Standardized Data Models (`models.py`) & Pure Domain Layer

### Cross-System Standardization via `models.py`:
- Untyped dictionaries and unstructured payload dictionaries are barred from internal data transit.
- All entities (users, accounts, transactions, orders, balances) are declared in `models.py` using **Dataclasses** or **Pydantic**.
- This enforces immutable data contracts, compile/design-time type safety, and IDE autocompletion.

### Pure Domain Logic & Function Reusability:
- The `domain/` directory contains **pure mathematical, financial, and algorithmic routines**.
- **Purity Rule:** Domain functions are side-effect free (no network calls, no database I/O, no filesystem access). They ingest validated entities and return deterministic outputs.
- **Universal Reusability:** Due to this strict decoupling, the same math function (e.g., French amortization or volatility computation) is reused across the real-time simulator, the public API, export engines, and automated unit tests without code duplication.

---

## 6. Deterministic Automated Testing Methodology

System reliability and calculations are verified through automated **Pytest** suites designed before and alongside implementation:

1. **Total Isolation:**  
   Domain tests execute without requiring disk databases or live network services; they leverage in-memory storage (`:memory:`) and predictable *fixtures*.
2. **Critical Path & Edge-Case Coverage:**  
   - **Nominal Math:** Verified against theoretical formulas specified in `/docs`.
   - **Corner & Edge Cases:** Zero interest rates, negative quantities, boundary tenors, blocked accounts.
   - **Controlled Exception Handling:** Asserting that the system fails gracefully with expected errors when presented with invalid input.
3. **Determinism:**  
   Tests never depend on wall-clock time or external network latency; all temporal flows use injectable virtual clocks.

---

## 7. Version Control Strategy & Git Lifecycle

Because development is executed independently, the Git lifecycle balances maximum delivery speed with enterprise engineering rigor:

* **Trunk-Based Development with Continuous Integration:**  
  Work commits directly to the main branch (`main` / `master`) using small, atomic, and continuous units of work.
* **Green Commits Policy:**  
  No commit is integrated into the main branch without passing 100% of the local automated test suite.
* **Conventional Commits Standard:**  
  Every commit explicitly communicates its intent:
  - `feat:` New features verified against specification docs.
  - `fix:` Targeted fixes for identified edge cases.
  - `refactor:` Internal improvements preserving external contracts and the 500-line rule.
  - `test:` Additions or expansions to automated test suites.
  - `docs:` Updates to technical specifications and contracts.
* **Team-Ready Scalability:**  
  The decoupled modular architecture enables seamless transition to **Feature Branches and Pull Requests** with automated CI/CD quality gates as additional engineers join the repository.

---

## 8. AI-Augmented Engineering: Multi-Agent Orchestration with *Skills*

The software is designed and developed through state-of-the-art **AI-Augmented Software Engineering** workflows, underpinned by multi-agent orchestration bound by strict architectural guardrails, **adversarial agents** dedicated to stress testing and fuzzing, **MRE (Minimal Reproducible Example) bug verification**, and **human-in-the-loop oversight in a strict engineering symbiosis**:

```text
[ Human Engineer: Chief Architect ] 
       │ 
       ▼ (Designs Specs, Contracts, MREs & Skills)
[ Multi-Agent Orchestrator / Agents ] 
       │ 
       ├──► [ Builder Agent: Modular Code < 500 lines ]
       │ 
       └──► [ Adversarial Agent: Fuzzing, Stress & Chaos Injection ]
              │
              ▼
       [ MRE Verification + 100% Green Test Suite ]
```

1. **Strict Engineering Symbiosis & Human Oversight (*Human-in-the-Loop*):**  
   The human engineer acts as Chief Architect and final auditor: analyzing requirements, drafting specifications in `/docs`, establishing data contracts, and setting rigorous acceptance criteria. AI accelerates execution under direct supervision; no architectural decisions are left to autonomous model discretion.
2. **Adversarial Agents & Fuzz Testing:**  
   Dedicated adversarial agents actively attack the codebase by injecting malformed payloads, simulating extreme volatility market regimes, forcing race conditions, and probing for mathematical precision leaks.
3. **MRE (Minimal Reproducible Example) Bug Verification:**  
   Bugs are never patched based on guesswork. When an anomaly is reported, an **MRE test** is constructed to reliably reproduce the failure in complete isolation. Only after the test fails deterministically is a surgical fix applied to turn the assertion green, preventing future regressions.
4. **Specialized *Skills* System:**  
   Custom *Skills* (such as `code-architecture-standards`) inject persistent, immutable constraints into the agent context:
   - Hard enforcement of the $< 500$ line limit per file.
   - Strict adherence to layer boundaries (`docs`, `src/domain`, `database`, `api`).
   - Mandatory usage of strongly-typed models and 2-3 line traceability headers.
5. **Impenetrable Quality Gate:**  
   All AI-assisted code must compile cleanly, honor modular architectural limits, withstand adversarial agent attacks, and achieve a 100% pass rate across the automated test suite before acceptance.
6. **Intellectual Property Protection (*Alpha Sanitization*) & Self-Contained Demo Mode (`.bat`):**  
   In quantitative terminals, arbitrage engines, and financial bots, proprietary business heuristics (*Alpha*: micro-structure spreads, private counterparty filters, and live production calibrations) are sanitized with academic/synthetic demonstration defaults for public portfolio distribution. Furthermore, every project includes a **1-Click Interactive Launcher (`.bat`) featuring a Zero-API Demo / Sandbox Mode**, enabling technical reviewers and recruiters to experience the live system and run the automated test suite without configuring external exchange credentials.

---

## 9. Conclusion & Technical Value Summary
> This repository demonstrates a mature, disciplined engineering process: **nothing is left to chance or guesswork**. The combination of exhaustive upfront documentation, decoupled clean architecture, strict physical modularity limits, deterministic testing, and governed AI-agent orchestration delivers software that is auditable, robust, and production-ready.
