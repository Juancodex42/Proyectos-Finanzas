# Funcionamiento Integral del Banco a Nivel Lógica de Negocios

> **Entidad:** Banco del Valle — Scoring Calculator & Lending Engine  
> **Área:** Arquitectura de Negocios, Tesorería Bancaria (ALM), Riesgo Crediticio y Ciclo Financiero  
> **Normativa de Referencia:** Ley de Entidades Financieras N° 21.526, Regulaciones BCRA (Efectivo Mínimo, Clasificación de Deudores), Ley 25.246 (UIF)

---

## 1. Visión Sistémica del Negocio Bancario

Una entidad financiera moderna opera como un **intermediario cuantitativo de liquidez y riesgo**:
1. **Captación de Pasivos:** Atrae liquidez del público (ahorristas particulares) y del sector productivo (empresas) mediante dos instrumentos con perfiles de exigibilidad y costo diferenciados:
   - **Depósitos Flexibles / A la vista:** Cajas de ahorro y cuentas corrientes remuneradas (liquidez inmediata, alto encaje BCRA, costo de fondeo bajo/medio).
   - **Plazos Fijos Tradicionales:** Fondos inmovilizados a 30, 60 o 90+ días (baja exigencia de encaje BCRA, tasa pactada más alta).
2. **Retención Prudencial y Cumplimiento de Encajes (BCRA):** Por cada peso captado, el banco debe inmovilizar una porción legal en reservas líquidas (30% para fondos flexibles, 12% a 0% para plazos fijos).
3. **Cálculo del Cashflow Seguro Prestable:** Algoritmo que determina en tiempo real el capital excedente prestable sin incurrir en descalce de plazos (*maturity mismatch*) ni violar los límites de solvencia.
4. **Colocación de Activos (Préstamos Amortizables):** Otorga financiamiento a personas y empresas evaluadas mediante un motor de Scoring Multi-Factor (ingresos comprobados, estabilidad laboral/societaria, historial Veraz y contexto macroeconómico).
5. **Ciclo de Cobranzas, Mora y Amortización:** Recupero mensual bajo Sistema Francés (cuota fija), monitoreo diario de días de mora y cobro de punitorios.
6. **Margen Financiero Neto (NII) y Ciclo Virtuoso de Capitalización:** El spread entre intereses activos cobrados e intereses pasivos pagados engrosa las utilidades del banco, capitalizándose de inmediato en el **Patrimonio Neto** y expandiendo el **Cashflow Seguro Prestable** para colocar nuevos créditos.

---

## 2. Diagrama Macro del Circuito Financiero del Banco

El siguiente diagrama detalla cómo circula el dinero, la información y las validaciones regulatorias en la entidad:

```mermaid
flowchart TD
    classDef default fill:#FFFFFF,stroke:#334155,stroke-width:2px,color:#0F172A;
    classDef captacion fill:#E0F2FE,stroke:#0284C7,stroke-width:2px,color:#0F172A;
    classDef tesoreria fill:#FEF3C7,stroke:#D97706,stroke-width:2px,color:#0F172A;
    classDef macro fill:#F3E8FF,stroke:#7E22CE,stroke-width:2px,color:#0F172A;
    classDef creditos fill:#DCFCE7,stroke:#15803D,stroke-width:2px,color:#0F172A;
    classDef pl fill:#FEE2E2,stroke:#B91C1C,stroke-width:2px,color:#0F172A;

    subgraph CAP["1. Captación de Pasivos (Fuentes de Fondeo)"]
        D_FLEX["Depósitos Flexibles / Cuentas a la Vista<br/>(Juan José y Clientes Particulares)<br/>TNA: ~28.5% | Liquidez Inmediata"]:::captacion
        D_PF["Plazos Fijos Tradicionales<br/>(Ahorristas y Tesorería PyME)<br/>TNA: ~38.0% | Plazos: 30 a 90+ días"]:::captacion
        PAT_PROP["Capital Propio / Patrimonio Neto Inicial<br/>(Respaldo de los Accionistas)"]:::captacion
    end

    subgraph ENCAJES["2. Régimen de Encajes Regulatorios (BCRA)"]
        ENC_FLEX["Encaje Legal Flexible (30%)<br/>Inmovilizado en BCRA"]:::tesoreria
        ENC_PF["Encaje Legal Plazo Fijo (12% / 6% / 0%)<br/>Inmovilizado en BCRA"]:::tesoreria
        COLCHON["Colchón Precautorio Adicional (5% - 10%)<br/>Reserva Operativa Interna"]:::tesoreria
    end

    subgraph MACRO["3. Entorno Macroeconómico y Pricing Dinámico"]
        REM_INF["REM BCRA + Consultoras Privadas<br/>Inflación Esperada a 12m (π^e)"]:::macro
        EMAE_PBI["Actividad Económica (EMAE / PBI)<br/>Factor de Ciclo Económico (F_macro)"]:::macro
        FISHER["Pricing de Tasa Activa (Fisher):<br/>TNA Base = TNA Pasiva + Margen + F_macro"]:::macro
    end

    subgraph ALM["4. Motor de Tesorería (Gestión ALM)"]
        CF_SEGURO["Algoritmo Cashflow Seguro Prestable:<br/>CF = Pasivos Libres + Patrimonio - Cartera Activa - Colchón - Vencimientos 30d"]:::tesoreria
        VALID_LIQ{"¿CF_seguro ≥ Monto Solicitado?"}:::tesoreria
    end

    subgraph SCORING["5. Motor de Calificación Crediticia (Scoring)"]
        SOLICITANTE["Solicitante (Individuo o PyME)"]:::creditos
        EVAL_RIESGO["Evaluación Multi-Factor:<br/>1. Veraz / Situación BCRA (1 a 6)<br/>2. Capacidad de Pago (Cuota ≤ 35% Ingreso)<br/>3. Segmento Laboral / Tipo Societario"]:::creditos
        DECISION_RIESGO{"¿Score y Ratios Aprobados?"}:::creditos
    end

    subgraph COLOCACION["6. Desembolso y Amortización"]
        PRESTAMO_DESEMBOLSO["Desembolso del Préstamo (Sistema Francés)<br/>Acreditación en Cuenta Transaccional"]:::creditos
        DAILY_TICK["Cierre Diario (Daily Tick Temporal):<br/>- Cobro de Cuotas Mensuales<br/>- Acreditación de Intereses Flexibles<br/>- Devengamiento de Días de Mora"]:::creditos
        MORA_CHECK{"¿Cuota Pagada a Término?"}:::creditos
        PAGO_OK["Crédito al Día (Situación 1)<br/>Intereses Ordinarios Cobrados"]:::creditos
        PAGO_MORA["Mora Detectada (Situación 2 a 5)<br/>Devengamiento de Punitorios Diarios"]:::creditos
    end

    subgraph PL["7. Estado de Resultados (P&L) y Reinversión"]
        INGRESOS["(+) Intereses Cobrados Préstamos<br/>(+) Punitorios por Mora"]:::pl
        EGRESOS["(-) Intereses Pagados (PF + Flexibles)<br/>(-) Previsiones por Incobrables"]:::pl
        SPREAD_NETO["Resultado Financiero Neto (NII)<br/>Margen de Intermediación"]:::pl
        REINVERSION["Ciclo de Capitalización:<br/>1. Crece el Patrimonio Neto (Equity)<br/>2. Inyección Directa a Caja Líquida<br/>3. Expansión del Cashflow Prestable"]:::pl
    end

    %% Conexiones de Captación a Encajes
    D_FLEX -->|Retiene 30%| ENC_FLEX
    D_FLEX -->|70% Disponible| CF_SEGURO
    D_PF -->|Retiene 12%| ENC_PF
    D_PF -->|88% Disponible| CF_SEGURO
    PAT_PROP --> CF_SEGURO
    COLCHON -.->|Deducción de Seguridad| CF_SEGURO

    %% Conexiones Macro
    REM_INF --> FISHER
    EMAE_PBI --> FISHER
    EMAE_PBI -->|Ajusta Ratio Máximo Cuota/Ingreso| EVAL_RIESGO

    %% Conexiones de Scoring y Créditos
    SOLICITANTE --> EVAL_RIESGO
    EVAL_RIESGO --> DECISION_RIESGO
    DECISION_RIESGO -- "No Aprobado" --> RECHAZO["Solicitud Rechazada o Cupo Reducido"]:::creditos
    DECISION_RIESGO -- "Aprobado por Riesgo" --> VALID_LIQ

    %% Conexión de Tesorería a Desembolso
    CF_SEGURO --> VALID_LIQ
    VALID_LIQ -- "No Hay Liquidez Suficiente" --> ESPERA_TES["En Espera de Liquidez / Reprogramación"]:::tesoreria
    VALID_LIQ -- "Liquidez Aprobada" --> PRESTAMO_DESEMBOLSO

    %% Conexiones de Colocación y Cobranzas
    PRESTAMO_DESEMBOLSO --> DAILY_TICK
    DAILY_TICK --> MORA_CHECK
    MORA_CHECK -- "Sí (Al Día)" --> PAGO_OK
    MORA_CHECK -- "No (Atraso)" --> PAGO_MORA

    %% Conexiones al P&L
    PAGO_OK --> INGRESOS
    PAGO_MORA --> INGRESOS
    D_FLEX -.->|Costo Financiero Diario| EGRESOS
    D_PF -.->|Costo Financiero al Vencimiento| EGRESOS
    INGRESOS --> SPREAD_NETO
    EGRESOS --> SPREAD_NETO
    SPREAD_NETO --> REINVERSION
    REINVERSION -->|Capitaliza y Aumenta| PAT_PROP
    REINVERSION -->|Aumenta Fondos Líquidos Prestables| CF_SEGURO
```

---

## 3. Desglose Operativo por Capa de Negocio

### A. Captación de Fondos y Costo Financiero Pasivo
* **Cuentas Flexibles / Transaccionales:**
  - El cliente mantiene dinero a la vista en su Caja de Ahorro.
  - El banco remunera ese saldo al **28.5% TNA** (rendimiento devengado diariamente: $\text{Saldo} \times \frac{0.285}{365}$).
  - Al ser fondos retirables en cualquier momento, el BCRA exige inmovilizar el **30% en efectivo mínimo** (`ENC_FLEX`).
* **Plazos Fijos Tradicionales:**
  - El cliente inmoviliza su capital por un plazo contractualmente estipulado (mínimo 30 días, hasta 90+ días) a una tasa fija (ej. **38% TNA**).
  - Al existir certeza temporal del vencimiento, el encaje obligatorio exigido por BCRA es mucho menor (**12% para 30 días**, **6% para 60 días**, **0% a 3% para más de 90 días**).
  - El cliente puede solicitar **cancelación anticipada**: rescata el 100% de su capital original pero resigna la totalidad de los intereses ($0 ganancia).

### B. Gestión de Tesorería y Asset & Liability Management (ALM)
El banco debe prevenir en todo momento el **descalce de plazos**: no puede prestar a 24 meses dinero que los depositantes pueden retirar en 24 horas.
* **Algoritmo de Cashflow Seguro Prestable ($CF_{\text{seguro}}$):**
  $$CF_{\text{seguro}} = \text{Depósitos Flexibles} \times (1 - e_{\text{flex}}) + \text{Plazos Fijos} \times (1 - e_{\text{pf}}) + \text{Patrimonio Neto} - \text{Cartera Activa Prestada} - \text{Colchón} - \text{Compromisos 30d}$$
* **Regla de Negocio:** Ningún préstamo se desembolsa si el monto solicitado excede $CF_{\text{seguro}}$, garantizando que el banco mantenga siempre solvencia absoluta frente a retiros masivos.

### C. Motor de Scoring y Calificación de Solicitantes
* **Individuos:**
  - **Capacidad de Pago:** Cuota del Sistema Francés $\le 35\%$ del ingreso mensual comprobado en BD.
  - **Categoría Laboral:** Empleados públicos y jubilados reciben bonificación de 2 a 3 puntos de tasa y plazos de hasta 60 cuotas. Privados requieren antigüedad $\ge 12$ meses. Monotributistas tienen cupos más conservadores (25% a 30% cuota/ingreso).
  - **Buró Externo (Veraz / Central de Deudores BCRA):** Se consulta situación crediticia (1: Normal hasta 6: Irrecuperable por disposición judicial) y monto de cheques rechazados.
* **Empresas y PyMEs:**
  - **Capacidad de Pago:** Cuota del préstamo $\le 20\%$ de la facturación mensual promedio comprobada.
  - **Tipo Societario:** Las `SAS` y `SRL` de baja antigüedad requieren fianza personal solidaria de los socios fundadores; las `SA` se evalúan con balances auditados; las `COOPERATIVAS` y `MUTUALES` con informe de excedentes y exención de ganancias.

### D. Pricing Macroeconómico de la Tasa de Interés
Para que el banco no sufra pérdidas reales por inflación, se aplica la **Ecuación de Fisher**:
$$\text{TNA Base} \approx \text{Inflación Proyectada 12m (REM + Consultoras)} + \text{Margen de Fondeo}$$
A esta tasa base se le adiciona el spread de riesgo individual según el score del cliente y el factor macroeconómico de actividad ($F_{\text{macro}}$):
* Si el EMAE/PBI está en recesión ($< -1\%$), $F_{\text{macro}} = 1.25 \text{ a } 1.40$, endureciendo el ratio cuota/ingreso (baja al 25%).
* Si la economía se expande ($> +1\%$), $F_{\text{macro}} = 0.85 \text{ a } 0.90$, ampliando la capacidad de colocación.

### E. Cierre Diario y Paso del Tiempo (Daily Tick)
En la simulación acelerada (donde 1 segundo real representa 1 día bancario):
1. Se actualiza la fecha virtual del sistema.
2. Se devengan los rendimientos de las cuentas flexibles a cada titular.
3. Se verifica si es día 1 del mes: se acredita automáticamente el sueldo en las cuentas sueldo (ej. Juan José $3.000.000).
4. Se ejecutan los débitos automáticos de cuotas de préstamos que vencen en la fecha.
5. Para cuotas no cobradas, se incrementa en +1 el contador exacto de `dias_mora` y se liquidan punitorios.
6. Se liquidan o renuevan los plazos fijos que hayan alcanzado su fecha de vencimiento.
7. Se recalculan los encajes legales y se registra el snapshot en `balance_patrimonio_banco`.

### F. Reinversión de Utilidades y Crecimiento Orgánico
Los intereses cobrados por préstamos menos los intereses pagados a depositantes constituyen el **Margen Financiero Neto (NII)**. Este beneficio:
1. No se distribuye inmediatamente: se capitaliza como utilidades retenidas en el **Patrimonio Neto**.
2. Ingresa de manera líquida a la tesorería del banco, aumentando directamente el $CF_{\text{seguro}}$.
3. Habilita una capacidad crediticia ampliada para nuevos préstamos en los ciclos subsiguientes.