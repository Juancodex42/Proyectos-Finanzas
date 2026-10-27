# Especificación de Contratos de Datos e Interfaces I/O
### Normalización Transversal de Entidades Contables y Transacciones

> **Ubicación:** `docs/contratos_io_transacciones.md`  
> **Referencia Metodológica:** Paso 2: Diseño de Contratos de Datos e Interfaces  
> **Proyecto:** *CryptoTax Pro / Motor Programa Contable*

---

## 1. Propósito y Alcance

Este documento define formalmente los contratos inmutables de entrada y salida (I/O) que rigen el intercambio de información entre la capa de ingestión (Parsers y Clientes API), la capa de Dominio Puro, la base de datos de persistencia SQLite (`transactions.db`), y el motor de generación de reportes y Excel.

**Regla Inquebrantable:** Ningún módulo del sistema puede propagar estructuras heterogéneas, diccionarios sin validar o tipos de datos indefinidos. Toda transacción debe conformar la entidad formal `Transaction`.

---

## 2. Contrato Principal: Entidad `Transaction`

La entidad `Transaction` representa un evento económico material ejecutado en un exchange o billetera virtual.

### Esquema Formal de Tipos

| Campo | Tipo Python | Obligatorio | Restricciones / Validación | Descripción |
| :--- | :--- | :---: | :--- | :--- |
| `tx_hash` | `str` | Sí | 32 caracteres hex (MD5 canónico) | Hash determinista unívoco del evento físico. |
| `fecha` | `datetime` | Sí | UTC estandarizado (ISO 8601) | Momento exacto de ejecución en milisegundos o segundos. |
| `exchange` | `str` | Sí | Nombre canónico de exchange | Nombre del broker o exchange (ej: `Binance Spot`, `Ripio Trade`). |
| `exchange_root` | `str` | Sí | Mayúsculas, sin sub-marcas | Exchange matriz (ej: `BINANCE`, `BITSO`, `RIPIO`, `FIWIND`). |
| `tipo_operacion` | `OperationType` | Sí | Valor de Enum cerrado | Naturaleza económica de la transacción (`COMPRA`, `VENTA`, etc.). |
| `moneda` | `str` | Sí | Ticker limpio en mayúsculas | Símbolo estándar de la criptomoneda (ej: `USDT`, `BTC`, `ETH`). |
| `monto_compra_cripto`| `float` / `Decimal`| Sí | $\ge 0.0$ | Cantidad de criptoactivo ingresado/adquirido. |
| `monto_venta_cripto` | `float` / `Decimal`| Sí | $\ge 0.0$ | Cantidad de criptoactivo egresado/entregado. |
| `cotizacion_compra` | `float` | No | $\ge 0.0$ | Precio unitario ponderado en ARS de adquisición. |
| `cotizacion_venta` | `float` | No | $\ge 0.0$ | Precio unitario de liquidación en ARS. |
| `monto_ars` | `float` | Sí | $\ge 0.0$ | Volumen total operado en moneda de curso legal (ARS). |
| `comentarios` | `str` | No | Longitud máxima 500 | Metadatos de auditoría, Order ID o Trade ID del exchange. |
| `source` | `str` | Sí | `CERTIFICATION`, `EXCHANGE_API`, `FILE_UPLOAD` | Canal de procedencia del dato. |
| `is_certified` | `int` | Sí | `0` o `1` | Bandera de inmutabilidad jurídica C.P.N. |
| `certification_id` | `Optional[int]` | No | ID de certificación o `None` | Vínculo con el dictamen contable sellado. |
| `order_id` | `Optional[str]` | No | Alfanumérico limpio | Identificador de la orden padre en el exchange. |
| `trade_id` | `Optional[str]` | No | Alfanumérico limpio | Identificador de la ejecución parcial individual (*fill*). |
| `file_row_index` | `Optional[int]` | No | $\ge 0$ | Número de fila en el archivo de origen (para desempate de fills). |

---

## 3. Contrato de Ingesta: Normalización de Husos Horarios

### Regla Obligatoria de Conversión UTC

Todo dato ingresado a través de parsers de archivos CSV o Excel locales debe seguir la siguiente regla estricta:
1. Si la fecha ya contiene un desplazamiento explícito de huso horario (`Z`, `+00:00`, `-03:00`, `ART`):
   $$\text{fecha\_utc} = \text{fecha}.\text{astimezone}(\text{timezone.utc})$$
2. Si la fecha es **ingenua (naive)** y proviene de un extracto de banco local o exchange argentino (Fiwind, Ripio, Lemon, Buenbit, Bitso Alpha con formato local):
   $$\text{fecha\_local} = \text{timezone}(\text{"America/Argentina/Buenos\_Aires"}).\text{localize}(\text{fecha})$$
   $$\text{fecha\_utc} = \text{fecha\_local}.\text{astimezone}(\text{timezone.utc})$$
3. **Prohibición:** Está terminantemente prohibido almacenar marcas de tiempo en hora argentina local (`ART`) en la columna `fecha` de la base de datos de transacciones de exchange.

---

## 4. Contrato del Hash Canónico (`compute_canonical_tx_hash`)

Para garantizar que un mismo evento económico material importado vía API o vía archivo mensual genere exactamente la misma huella determinista, la función de hash se calcula sobre los componentes normalizados:

$$\text{hash\_input} = \text{fecha\_utc\_iso} + \text{"\_"} + \text{exchange\_root} + \text{"\_"} + \text{tipo\_operacion} + \text{"\_"} + \text{moneda} + \text{"\_"} + \text{monto\_compra\_16f} + \text{"\_"} + \text{monto\_venta\_16f} + \text{"\_"} + \text{monto\_ars\_2f} + \text{"\_"} + \text{clean\_ref}$$

Donde:
* `fecha_utc_iso`: Cadena formateada `YYYY-MM-DD HH:MM:SSZ`.
* `clean_ref`: Identificador de orden o trade numérico extraído de `comentarios` o `trade_id`. Si no existe ID explícito, se utiliza la posición relativa en el lote o se fija como cadena vacía.

---

## 5. Contrato de Respuesta: Detección de Brechas (`InventoryGap`)

Toda brecha o descubierto detectado por el motor de inventario debe responder a la estructura tipada:

```python
class InventoryGap(BaseModel):
    exchange: str
    origin_exchange: str
    coin: str
    date: datetime
    deficit: float
    running_deficit: float
    sold_qty: float
    available_qty: float
    mode: str  # 'global' o 'per_exchange'
    suggested_action: Optional[str]
```
