# Margen Financiero (P&L Bancario) y Modelo de Proyecciones Multi-Escenario

## 1. El Margen Financiero Neto (Net Interest Income - NII)

La principal fuente de ingresos y capitalización de una entidad financiera es el **spread de tasas**: la diferencia entre los intereses que cobra por prestar dinero (tasa activa) y los intereses que paga a los ahorristas por sus depósitos (tasa pasiva).

### Ecuación del Resultado Financiero Diario / Mensual:

$$\text{Margen Financiero Bruto} = \sum \text{Intereses Cobrados (Préstamos)} - \sum \text{Intereses Pagados (PF + Flexibles)}$$
$$\text{Resultado Operativo Neto} = \text{Margen Financiero Bruto} + \text{Punitorios Cobrados} - \text{Pérdidas por Mora Incobrable}$$

---

## 2. Destino y Reinversión de los Intereses Obtenidos

> [!IMPORTANT]
> **¿Qué hace el banco con las ganancias obtenidas?**
> Las ganancias netas por intereses **no desaparecen ni se apartan del circuito**: se capitalizan inmediatamente en la institución financiera.

### El Ciclo Virtuoso de Reinversión:
1. **Aumento del Patrimonio Neto (Equity):** Las utilidades netas pasan a la cuenta contable de utilidades acumuladas, aumentando el respaldo patrimonial del banco.
2. **Inyección Directa a Caja Líquida:** El cobro efectivo de intereses ingresa en dinero líquido al tesoro de la entidad.
3. **Ampliación del Cashflow Seguro Prestable:**
   Al crecer los fondos líquidos libres de encaje y el patrimonio propio, el sistema recalcula en tiempo real una **mayor capacidad para otorgar nuevos préstamos**:
   $$\Delta CF_{\text{seguro}} = \text{Resultado Neto del Período}$$
4. **Reinversión en el Activo:** Esos nuevos fondos disponibles se prestan a nuevos solicitantes con buen score, retroalimentando el flujo de ingresos futuros.

---

## 3. Modelo de Proyección de Ganancias y Patrimonio Multi-Escenario

El módulo de inteligencia financiera proyecta la evolución del **Patrimonio Neto** y las **Ganancias Acumuladas** en el tiempo (semanas, meses, y horizontes extendidos a 1, 3 y 5 años) bajo tres escenarios macroeconómicos:

```
                                  [ Horizonte Temporal ]
                    (Semanas / Meses / 1 año / 3 años / 5 años)
                                           |
           +-------------------------------+-------------------------------+
           |                               |                               |
           v                               v                               v
[ Escenario Optimista (Bull) ]   [ Escenario Base (Consenso) ]   [ Escenario Pesimista (Stress) ]
- Inflación a la baja.          - Cumplimiento mediana REM.     - Shock inflacionario al alza.
- PBI / EMAE en expansión (+3%). - PBI estable (0% a +1%).       - Recesión económica (PBI -3%).
- Mora mínima (< 2%).           - Mora promedio histórica (~5%).- Mora severa (> 12%).
- Máxima reinversión y spread.  - Crecimiento equilibrado.      - Absorción de pérdidas con capital.
```

### A. Parámetros de Calibración por Escenario

| Parámetro | Escenario Optimista | Escenario Base (Consenso) | Escenario Pesimista (Estrés) |
| :--- | :--- | :--- | :--- |
| **Inflación Proyectada ($\pi^e$)** | Baja 10-15 pts vs. REM | Mediana exacta del REM | Sube 20-30 pts vs. REM |
| **Actividad Económica (PBI/EMAE)** | Crecimiento $+3.0\%$ anual | Crecimiento $+0.5\%$ anual | Caída recesiva $-3.5\%$ anual |
| **Tasa de Morosidad Cartera** | $\approx 2.0\%$ | $\approx 5.5\%$ | $\ge 12.0\%$ |
| **Renovación de Plazos Fijos** | $75\%$ de los ahorristas | $60\%$ de los ahorristas | $35\%$ (fuerte salida de liquidez) |
| **Spread de Tasa (Activa - Pasiva)**| Spread amplio y seguro | Spread de mercado estándar | Spread comprimido por riesgo |

---

## 4. Visualización en la Gráfica Gerencial

En el Dashboard de Gerencia, la gráfica proyectiva representa:
* **Eje X (Temporal):**
  * Vista Corto Plazo: Marcadores semanales con cierre a fin de mes.
  * Vista Mediano/Largo Plazo: Meses consecutivos (1 a 12 meses) y proyección extendida (3 a 5 años).
* **Eje Y (Financiero):** Monto acumulado en Pesos Argentinos ($) para:
  * **Curva 1 (Verde Sólida):** Proyección Ganancias / Patrimonio en Escenario Optimista.
  * **Curva 2 (Azul Sólida):** Proyección Ganancias / Patrimonio en Escenario Base.
  * **Curva 3 (Naranja Discontinua):** Proyección Ganancias / Patrimonio en Escenario Pesimista.
* **Gráfica Secundaria Vinculada:**
  * Curva de evolución de las **Tasas de Interés Proyectadas** (TNA Activa vs. TNA Pasiva) según cómo cada escenario condiciona la política monetaria.
