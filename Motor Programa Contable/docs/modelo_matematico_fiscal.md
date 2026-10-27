# Modelo Matemático y Normativa Fiscal Argentina
### Liquidación de Impuesto a las Ganancias (Régimen Cedular) e Ingresos Brutos (IIBB)

> **Ubicación:** `docs/modelo_matematico_fiscal.md`  
> **Referencia Metodológica:** Paso 1: Recopilación Documental y Modelado Matemático  
> **Proyecto:** *CryptoTax Pro / Motor Programa Contable*

---

## 1. Impuesto a las Ganancias (Régimen Cedular - Monedas Digitales)

### Marco Normativo
Ley de Impuesto a las Ganancias (t.o. 2019 y modificatorias), Artículo 95:
Las ganancias obtenidas por personas humanas derivadas de la enajenación de monedas digitales se encuentran alcanzadas por una alícuota fija del **15% sobre la renta neta de fuente argentina**.

### Fórmula de la Renta Neta

Para cada venta $i$ liquidada en el período fiscal:

$$\text{Precio\_Venta}_i = \text{monto\_venta\_cripto}_i \times \text{cotizacion\_venta}_i$$
$$\text{Costo\_Base\_FIFO}_i = \text{monto\_venta\_cripto}_i \times \text{cotizacion\_compra\_fifo}_i$$
$$\text{Resultado\_Bruto}_i = \text{Precio\_Venta}_i - \text{Costo\_Base\_FIFO}_i$$

$$\text{Renta\_Neta\_Total} = \sum_{i=1}^{N} \text{Resultado\_Bruto}_i - \text{Gastos\_Deducibles\_Arbitraje}$$

$$\text{Base\_Imponible} = \max(0, \text{Renta\_Neta\_Total} - \text{Deduccion\_Especial})$$

$$\text{Impuesto\_Ganancias\_Determinado} = \text{Base\_Imponible} \times 0.15$$

---

## 2. Gastos Deducibles de la Actividad

Son computables como quebranto o gasto deducible directo:
* Comisiones de red (*network fees / gas*) de transferencias entre billeteras operativas.
* Comisiones de exchange (*taker / maker fees*).
* Impuesto a los Débitos y Créditos Bancarios (Ley 25.413) efectivamente retenido en cuentas operativas de arbitraje.
* Retenciones de SIRCREB y percepciones provinciales de IIBB vinculadas a la operatoria.

---

## 3. Impuesto sobre los Ingresos Brutos (IIBB)

El hecho imponible se perfecciona sobre los ingresos brutos derivados del ejercicio habitual del comercio de activos digitales en la jurisdicción correspondiente:

$$\text{Base\_Imponible\_IIBB} = \sum \text{Precio\_Venta\_ARS}$$
$$\text{Impuesto\_IIBB} = \text{Base\_Imponible\_IIBB} \times \text{Alicuota\_Jurisdiccion}$$

* Alícuota General CABA / PBA: Según código fiscal aplicable (típicamente $3.0\%$ a $5.0\%$ sobre base bruta o diferencial de compra-venta según categorización como intermediario).

---

## 4. Fórmulas Compartidas para el Libro Excel Operativo

Para evitar desfasajes entre el reporte web y el libro operativo generado en Excel (`operational_excel_service.py`), se definen las siguientes identidades que se mapean unívocamente:

1. **Variación de Stock Cripto en Fila $r$:**
   $$=\text{IF}(C_r = \text{"Compra"}, E_r, \text{IF}(C_r = \text{"Venta"}, -E_r, \dots))$$
2. **Total Capital Puesto en Juego (B):**
   $$=\text{Capital\_Inicial} + \text{Inyecciones} - \text{Retiros} + \text{Prestamos} - \text{Devoluciones}$$
3. **Ganancia Patrimonial Neta Real:**
   $$\text{Resultado\_Neto} = \text{Activos\_Finales\_Reales (A)} - \text{Capital\_Neto\_Invertido (B)}$$
