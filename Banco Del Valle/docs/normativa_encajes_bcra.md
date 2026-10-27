# Normativa de Efectivo Mínimo (Encajes Bancarios) — Banco Central de la República Argentina (BCRA)

## 1. Definición y Fundamento
El **Efectivo Mínimo (o encaje legal)** es la proporción de los depósitos captados del público que las entidades financieras están obligadas por ley y regulación del BCRA a mantener inmovilizados como reservas líquidas.

### Objetivos Principales:
1. **Prudencial y Solvencia:** Garantizar que el banco cuente con liquidez suficiente e inmediata para responder ante la demanda de retiros de los ahorristas, evitando corridas bancarias.
2. **Política Monetaria:** Regula la cantidad de dinero en circulación en la economía. A mayor tasa de encaje, menor capacidad prestable tiene el banco y menor es la expansión secundaria de dinero.

---

## 2. Tipos de Depósitos y Plazos según Normativa BCRA

El BCRA clasifica las obligaciones bancarias según su exigibilidad en el tiempo:

### A. Depósitos a la Vista / Disponibilidad Inmediata (Flexibles)
* **Composición:** Cuentas corrientes bancarias, cajas de ahorro y cuentas remuneradas de liquidez inmediata.
* **Características:** El depositante puede retirar o transferir su dinero en cualquier momento sin penalización.
* **Régimen de Encaje:** Posee la tasa de encaje más alta del sistema financiero (históricamente entre el **21% y el 45%** según la categoría de la entidad y franquicias especiales), debido al alto riesgo de salida repentina de fondos.

### B. Depósitos a Plazo (Plazo Fijo Tradicional y UVA)
* **Plazos mínimos regulatorios:**
  * Plazo Fijo en pesos: Mínimo 30 días.
  * Plazo Fijo UVA (con cláusula de ajuste por inflación): Mínimo 180 días.
* **Características:** El depositante inmoviliza los fondos a cambio de una Tasa Nominal Anual (TNA) fija acordada. Los fondos no pueden ser retirados antes del vencimiento.
* **Régimen de Encaje:** La tasa de encaje es significativamente **menor** que en las cuentas a la vista (típicamente entre el **0% y el 15%** según el plazo residual). A mayor plazo pactado, menor exigencia de encaje por parte del BCRA.

---

## 3. Integración y Cómputo de la Posición de Efectivo Mínimo

La normativa del BCRA establece dos controles temporales:
1. **Control Diario:** El saldo de reservas no puede caer por debajo de un mínimo técnico diario (generalmente el 70% de la exigencia total mensual).
2. **Control Mensual (Promedio):** Se calcula el promedio diario del saldo mantenido a lo largo del mes calendario y se compara contra la exigencia promedio mensual.

### ¿Dónde se integran los encajes?
* Cuentas corrientes que cada banco posee abiertas en el BCRA (fondos en pesos a la vista sin remunerar).
* Billetes y monedas en poder de la entidad (tesoro y cajeros automáticos, con topes de cómputo según normativa vigente).
* Instrumentos de deuda autorizados expresamente por el BCRA (títulos públicos nacionales elegibles, letras del tesoro como LECAPs, o pases pasivos según el marco vigente).

---

## 4. Consecuencias del Incumplimiento (Déficit de Encaje)
Si una entidad financiera no alcanza a integrar el promedio de efectivo mínimo exigido:
* **Cargo por Incumplimiento:** El BCRA aplica una penalización pecuniaria severa, cobrando una tasa punitoria sobre el monto del déficit diario (habitualmente calculada como 1.5 a 2 veces la tasa de interés de referencia del mercado).
* **Supervisión Especial:** Infracciones reiteradas disparan inspecciones de la Superintendencia de Entidades Financieras y Cambiarias (SEFyC) y restricciones para otorgar nuevos créditos o pagar dividendos.

---

## 5. Parámetros para el Sistema *Scoring Calculator*

Para el modelo computacional de tesorería del sistema, se parametrizan las tasas de encaje promedio del régimen:

| Tipo de Depósito | Identificador | Tasa de Encaje Regulatorio ($e$) | Disponibilidad para Crédito |
| :--- | :--- | :--- | :--- |
| **Depósitos Flexibles / A la vista** | `ENC_FLEX` | **30.0%** (0.30) | **70.0%** |
| **Plazo Fijo 30 a 59 días** | `ENC_PF_CORTO` | **12.0%** (0.12) | **88.0%** |
| **Plazo Fijo 60 a 89 días** | `ENC_PF_MEDIO` | **6.0%** (0.06) | **94.0%** |
| **Plazo Fijo 90+ días** | `ENC_PF_LARGO` | **0.0% - 3.0%** (0.02) | **98.0%** |
