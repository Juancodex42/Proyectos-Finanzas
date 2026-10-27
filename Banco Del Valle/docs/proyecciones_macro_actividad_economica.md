# Proyecciones Macroeconómicas: Actividad Económica (EMAE / PBI) y Ciclo Crediticio

## 1. Fundamentos: El Ciclo Económico y la Morosidad Bancaria

La solvencia y el riesgo de una entidad financiera no dependen únicamente del comportamiento individual del cliente, sino fuertemente del contexto macroeconómico:
* **Fases Expansivas (Crecimiento del PBI / EMAE):** Crece el empleo formal, los ingresos reales aumentan y la morosidad sistémica desciende. El banco puede relajar selectivamente sus filtros de aprobación y ampliar su cartera.
* **Fases Recesivas o Estanflacionarias (Caída del EMAE):** Aumenta el desempleo, cae el poder adquisitivo y las familias priorizan el consumo de subsistencia sobre el pago de deudas. La probabilidad de mora se dispara de forma generalizada (*riesgo sistémico*).

---

## 2. Fuentes de Indicadores de Actividad Económica

### A. Estimador Mensual de Actividad Económica (EMAE) — INDEC
* **Definición:** Medición mensual oficial que anticipa la variación trimestral del Producto Bruto Interno (PBI).
* **Frecuencia:** Mensual con rezago de 60 días.
* **Utilidad:** Permite detectar cambios de tendencia económica (meses consecutivos de variación interanual negativa señalan inicio de recesión técnica).

### B. Proyecciones del Relevamiento de Expectativas de Mercado (REM) y Consultoras
* **Pronóstico de PBI real:** Tasa de variación esperada del PBI para el año en curso y el año siguiente (mediana REM y estimaciones de consultoras como FIEL, Ecolatina, OJF).
* **Indicadores líderes:** Índice de Confianza del Consumidor (ICC), producción industrial (IPI) y ventas minoristas (CAME).

---

## 3. Canal de Transmisión al Motor de Riesgo Crediticio

El sistema aplica un factor multiplicador de riesgo macroeconómico ($F_{\text{macro}}$) sobre la probabilidad de mora y la capacidad de repago:

```
[ EMAE / PBI Proyectado ] ---> [ Indicador de Ciclo Económico (ICE) ]
                                            |
                                            v
                 +------------------------------------------------------+
                 | Factor Ajustador Macroeconómico (F_macro):           |
                 | - En Recesión (PBI < -1%): F_macro = 1.25 a 1.40     |
                 | - Estable (PBI -1% a +1%): F_macro = 1.00            |
                 | - En Crecimiento (PBI > +1%): F_macro = 0.85 a 0.90  |
                 +------------------------------------------------------+
                                            |
                         +------------------+------------------+
                         |                                     |
                         v                                     v
          [ Endurecimiento de Ratios ]            [ Recargo de Spread Mora ]
          - Ratio Cuota/Ingreso baja de           - Spread de riesgo base
            35% a 25% en recesión.                  se incrementa un 20%-30%.
```

### Fórmulas del Módulo:

1. **Ajuste del Ratio Máximo de Endeudamiento ($\text{RME}$):**
   $$\text{RME}_{\text{ajustado}} = \frac{\text{RME}_{\text{base}}}{F_{\text{macro}}}$$
   * *Ejemplo:* Si el ratio base es 35% y entramos en recesión severa ($F_{\text{macro}} = 1.40$):
     $$\text{RME} = \frac{35\%}{1.40} = 25\% \text{ del ingreso mensual}$$
   Esto previene sobreendeudar a las familias cuando la economía se contrae.

2. **Probabilidad de Mora Simulada en el Motor de Tiempo:**
   $$\text{Probabilidad Mora Diaria} = \text{Mora Base por Veraz} \times F_{\text{macro}}$$
   En la simulación acelerada, un escenario recesivo provoca que más clientes tarden en pagar o caigan en mora leve/grave.

---

## 4. Estructura de Datos en SQLite

Tabla de registro macroeconómico:
* **`proyecciones_actividad_economica`**:
  * `id` (INTEGER PRIMARY KEY)
  * `fecha_relevamiento` (TEXT)
  * `variacion_pbi_proyectada_anual` (REAL): Ej. -0.025 (-2.5%) o +0.03 (+3.0%).
  * `emae_ultimo_interanual` (REAL)
  * `fase_ciclo` (TEXT: 'EXPANSION', 'ESTABLE', 'RECESION_LEVE', 'RECESION_SEVERA')
  * `factor_macro_riesgo` (REAL)
