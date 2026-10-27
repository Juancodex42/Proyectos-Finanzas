# Suite de Pruebas Unitarias — Banco del Valle

> **Entorno de Testing:** Python 3.11+ / Pytest  
> **Área:** Validación de Algoritmos Financieros, Lógica de Negocio y Reglas Regulatorias

---

## 1. Filosofía y Estándares de Testing

En una plataforma bancaria y de cálculo crediticio, **el margen de error numérico debe ser cero**. Las pruebas unitarias garantizan que cada función matemática, regla de encaje del BCRA y transición de estado opere de manera determinista e infalible antes de su integración con la base de datos o la interfaz gráfica.

### Reglas para los Tests:
* **Funciones Puras:** El 100% de las funciones matemáticas en `src/domain/` deben probarse con entradas y salidas aisladas de SQLite y de la red.
* **Cobertura de Casos Borde (Edge Cases):** Se deben validar situaciones límite (saldo cero, mora en día 0, mora en día 91, descalce de encaje, año bisiesto, etc.).
* **Tiempo de Ejecución:** La suite completa de tests unitarios debe ejecutarse en menos de **2 segundos**.

---

## 2. Catálogo de Archivos de Pruebas Unitarias

```text
tests_unitarios/
├── README.md                           # Documentación y plan de pruebas de la suite
├── conftest.py                         # Fixtures compartidas de Pytest (datos mock de Juan José, empresas y balances)
├── test_scoring.py                     # Validación de mora exacta, scoring individual y PyME
├── test_treasury.py                    # Validación de encajes BCRA (30% vs 12%) y Cashflow Seguro
├── test_interest_rate.py               # Validación del Sistema Francés, cuota fija y pricing ALM
├── test_macro_projections.py           # Ecuación de Fisher y factor de ciclo económico (EMAE/PBI)
├── test_compliance_aml.py              # Reglas de monitoreo transaccional en SMVM y Soft Delete
└── test_simulation_clock.py            # Avance del reloj virtual, Daily Tick y acreditación de sueldo
```

---

## 3. Especificación Detallada de Casos de Prueba por Módulo

### A. Pruebas de Scoring y Mora (`test_scoring.py`)
1. **`test_dias_mora_exactos_al_dia`:**
   * *Entrada:* Vencimiento 2026-11-10, Fecha actual 2026-11-05.
   * *Esperado:* `dias_mora = 0`, penalización = $0.
2. **`test_dias_mora_atraso_calculado`:**
   * *Entrada:* Vencimiento 2026-11-10, Fecha actual 2026-11-25 (sin pagar).
   * *Esperado:* `dias_mora = 15`. Devengamiento de punitorios diarios correcto.
3. **`test_ratio_endeudamiento_persona`:**
   * *Entrada:* Sueldo Juan José = $3.000.000. Cuota propuesta = $1.000.000 (33.3%).
   * *Esperado:* `Aprobado` (menor al tope del 35%).
   * *Entrada Borde:* Cuota = $1.200.000 (40%).
   * *Esperado:* `Rechazado` por sobreendeudamiento.
4. **`test_scoring_empresas_fianza_socios`:**
   * *Entrada:* Empresa tipo `'SAS'` con antigüedad menor a 2 años.
   * *Esperado:* Aprobación condicionada a `requiere_fianza_socios = True`.

---

### B. Pruebas de Tesorería y Encajes BCRA (`test_treasury.py`)
1. **`test_encaje_cuentas_flexibles`:**
   * *Entrada:* $10.000.000 en depósitos flexibles. Tasa de encaje = 30%.
   * *Esperado:* Reserva obligatoria BCRA = $3.000.000; Capacidad prestable bruta = $7.000.000.
2. **`test_encaje_plazos_fijos`:**
   * *Entrada:* $10.000.000 en plazos fijos a 30 días. Tasa encaje = 12%.
   * *Esperado:* Reserva obligatoria BCRA = $1.200.000; Capacidad prestable bruta = $8.800.000.
3. **`test_bloqueo_desembolso_por_iliquidez`:**
   * *Entrada:* Solicitud de crédito = $5.000.000; Cashflow seguro disponible = $3.500.000.
   * *Esperado:* `False` (Desembolso no autorizado por tesorería para no violar encajes mínimos).

---

### C. Pruebas de Amortización Francesa y Pricing (`test_interest_rate.py`)
1. **`test_sistema_frances_suma_amortizaciones`:**
   * *Entrada:* Capital $1.000.000, 12 cuotas, TNA 60%.
   * *Esperado:* La suma de la amortización de capital de las 12 cuotas debe ser exactamente igual a $1.000.000 (tolerancia de centavos: $\pm 0.05$).
2. **`test_interes_decreciente_capital_creciente`:**
   * *Esperado:* En cada período consecutivo, el componente de interés disminuye y el de amortización de capital aumenta.

---

### D. Pruebas Macroeconómicas (`test_macro_projections.py`)
1. **`test_ecuacion_fisher_piso_tasa`:**
   * *Entrada:* Inflación esperada ($\pi^e$) = 45%, Tasa real buscada ($r$) = 10%.
   * *Esperado:* $\text{TNA Base} \ge 59.5\%$ anual.
2. **`test_factor_recesion_ajusta_tope_cuota`:**
   * *Entrada:* Fase de ciclo `'RECESION_SEVERA'` ($F_{\text{macro}} = 1.40$).
   * *Esperado:* El ratio máximo de cuota se contrae del 35% al 25% del sueldo.

---

### E. Pruebas de Compliance y AML (`test_compliance_aml.py`)
1. **`test_operacion_habitual_sin_alerta`:**
   * *Entrada:* Transferencia recibida equivalente a 0.5 veces el sueldo mensual.
   * *Esperado:* `alerta_aml = 0`, cuenta permanece `'ACTIVO'`.
2. **`test_disparo_alerta_umbral_smvm`:**
   * *Entrada:* Transacciones que superan el umbral oficial de 40 SMVM sin antecedentes patrimoniales previos.
   * *Esperado:* Disparo de alerta de monitoreo interno y generación de solicitud de información (RFI) sin bloqueo intempestivo.
3. **`test_soft_delete_con_deuda_bloqueado`:**
   * *Entrada:* Solicitud de baja de cuenta con préstamo activo con saldo impago.
   * *Esperado:* Excepción o rechazo de baja: *"No es posible cerrar la cuenta con saldos deudores pendientes"*.

---

### F. Pruebas del Motor de Simulación Diaria (`test_simulation_clock.py`)
1. **`test_tick_diario_devenga_interes_flexible`:**
   * *Entrada:* Saldo Juan José $3.000.000 al 28.5% TNA. Avanza 1 día simulado.
   * *Esperado:* Acreditación exacta de $3.000.000 \times \frac{0.285}{365} \approx \$2.342,47$.
2. **`test_cierre_mensual_acredita_sueldo`:**
   * *Entrada:* La fecha simulada pasa del día 31/10 al 01/11.
   * *Esperado:* Se acredita automáticamente el sueldo de Juan José de $3.000.000 en su cuenta.
3. **`test_cancelacion_anticipada_plazo_fijo`:**
   * *Entrada:* Plazo fijo constituido por $1.000.000 a 30 días. Se cancela el día 15.
   * *Esperado:* Se reintegran exactamente $1.000.000 al saldo. Ganancia liquidada = $0.

---

## 4. Guía de Ejecución de Pruebas

Para ejecutar las pruebas desde la terminal:

```bash
# Ejecutar toda la suite de pruebas unitarias
pytest tests_unitarios/ -v

# Ejecutar una suite específica (ej. tesorería)
pytest tests_unitarios/test_treasury.py -v

# Ejecutar con reporte de cobertura de código
pytest tests_unitarios/ --cov=src --cov-report=term-missing
```
