# Proyecciones Macroeconómicas: Inflación de Consultoras Privadas y REM del BCRA

## 1. Fundamentos: ¿Por qué la Inflación Proyectada Determina la Tasa de Interés?

En una economía con inflación persistente, prestar dinero a tasa fija o pactar depósitos sin considerar la pérdida de poder adquisitivo del dinero destruye el patrimonio del banco (*tasa real negativa*).

### La Ecuación de Fisher
La relación entre la Tasa de Interés Nominal ($i$), la Tasa de Interés Real requerida ($r$) y la Inflación Proyectada o Esperada ($\pi^e$) se rige por:

$$(1 + i) = (1 + r)(1 + \pi^e) \iff i \approx r + \pi^e$$

* Si el banco proyecta una inflación a 12 meses ($\pi^e$) del **45%** y exige una tasa real de rentabilidad ($r$) del **10%**, la tasa nominal activa no puede ser inferior al **59.5%**:
  $$i = (1 + 0.10) \times (1 + 0.45) - 1 = 0.595 \text{ (59.5\% TNA)}$$

---

## 2. Fuentes de Información y Relevamiento de Expectativas

El módulo macroeconómico del sistema releva dos canales complementarios:

### A. Relevamiento de Expectativas de Mercado (REM) — BCRA
* **Naturaleza:** Encuesta mensual oficial elaborada por el Banco Central sobre los principales bancos, consultoras y centros de investigación económica de Argentina.
* **Métricas clave:**
  * Inflación minorista mensual proyectada para los próximos 6 meses.
  * Inflación interanual esperada a 12 y 24 meses (TOP 10 de pronosticadores vs. mediana general).
  * Tasa BADLAR / TAM esperada y evolución proyectada del tipo de cambio oficial.

### B. Consenso de Consultoras Privadas Independientes
* **Fuentes:** Informes y relevamientos semanales/quincenales de consultoras económicas (ej. Ecolatina, FIEL, Empiria, Equilibra, Orlando Ferreres).
* **Utilidad:** Provee un *termómetro de alta frecuencia* para anticipar shocks de precios antes de que se publiquen los reportes mensuales oficiales del BCRA o INDEC.

---

## 3. Modelo Matemático de Ajuste Dinámico de Tasas en el Sistema

El motor de pricing incorpora la expectativa inflacionaria en el piso de la tasa pasiva y activa:

```
[ REM BCRA (Mediana 12m) ] \
                             --> [ Índice de Inflación Esperada π_e ]
[ Consultoras Privadas   ] /                    |
                                                v
                              +-----------------------------------+
                              | Costo de Fondeo Pasivo (PF):      |
                              | TNA_pasiva = π_e - spread_ahorro  |
                              +-----------------------------------+
                                                |
                                                v
                              +-----------------------------------+
                              | Tasa Activa Préstamo Base:        |
                              | TNA_base = TNA_pasiva + π_e_ajuste|
                              +-----------------------------------+
                                                |
                                                v
                              +-----------------------------------+
                              | Tasa Final = TNA_base             |
                              |   + Spread Riesgo Cliente         |
                              |   + Spread Liquidez/Cashflow      |
                              +-----------------------------------+
```

### Fórmulas del Módulo:

1. **Inflación Ponderada Esperada ($\pi^e_{\text{sistema}}$):**
   $$\pi^e_{\text{sistema}} = (w_{\text{REM}} \times \pi_{\text{REM}}) + (w_{\text{Privadas}} \times \bar{\pi}_{\text{Privadas}})$$
   *Por defecto:* $w_{\text{REM}} = 0.60$, $w_{\text{Privadas}} = 0.40$.

2. **Piso de Tasa Pasiva (Plazos Fijos):**
   Para que los ahorristas no retiren sus fondos, el banco debe ofrecer una tasa cercana o superior a la inflación proyectada:
   $$\text{TNA}_{\text{pasiva}} = \max(\text{Tasa Mínima Regulatoria BCRA}, \pi^e_{\text{sistema}} \times (1 - \delta_{\text{pasiva}}))$$

3. **Impacto en la Tasa Activa de Créditos:**
   $$\text{TNA}_{\text{activa}} = \text{TNA}_{\text{pasiva}} + \text{Margen Bruto de Intermediación} + \text{Spread Riesgo Persona} + \text{Spread Escasez Liquidez}$$

---

## 4. Estructura de Datos para Simulación

En la base de datos se registra la tabla o entidad:

* **`proyecciones_inflacion`**:
  * `id` (INTEGER PRIMARY KEY)
  * `fecha_relevamiento` (TEXT)
  * `inflacion_proyectada_12m` (REAL): Porcentaje anualizado (ej. 0.48).
  * `fuente` (TEXT: 'REM_BCRA', 'CONSULTORAS_CONSENSO', 'MANUAL_SIMULADOR')
  * `tasa_referencia_politica_monetaria` (REAL)
