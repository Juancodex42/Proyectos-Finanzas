# Manual Maestro de Reglas Anti-Baneo Binance P2P (Global & LATAM / ARS)

Este documento constituye la **fuente única de verdad (Single Source of Truth)** sobre las reglas comerciales, técnicas y de control de riesgo de Binance P2P aplicables al bot. Consolida:
1. **Directrices Oficiales para Comerciantes de Binance P2P** (*Binance P2P Merchant Guidelines*, FAQ Oficial `360043895111`, Sección V — Regla 5.1).
2. **Manual Técnico Oficial de la API** ([`manuales_api/Binance_C2C_SAPI_v7.4_Manual.pdf`](manuales_api/Binance_C2C_SAPI_v7.4_Manual.pdf)).
3. **Reglas de Validación Sincrónica (HTTP 400) y Auditoría Asincrónica de Riesgo (`Error 83714`)**.
4. **Criterios de Equilibrio Operativo (Guardarraíles Exactos: Ni ausentes, ni exagerados, ni sobreescritos)**.

---

## Arista 1: Reglas Comerciales de Publicación de Anuncios (FAQ `360043895111` — Regla 5.1)

### 1.1 Cantidad Máxima de Anuncios por Activo y Dirección
- **Regla Oficial:** Un comerciante puede tener un máximo de **3 anuncios activos (`advStatus = 1`, Online)** en la misma dirección (`BUY` o `SELL`) para el mismo par Cripto-Fiat (ej. `USDT/ARS`: Grupo 1, Grupo 2, Grupo 3).
- **Guardarraíl esperado en el bot:** Exactamente 3 grupos por activo (`AD_GROUPS = {1, 2, 3}`), cerrando o reciclando cualquier excedente en reconciliación.

### 1.2 Prohibición Estricta de Parámetros Idénticos / Clonación (Regla 5.1.1 y 5.1.2)
> **Texto Oficial Literal (FAQ 360043895111):**
> *"You are not permitted to post two or more advertisements for the same crypto-fiat pair if they share the same price, order limit, or total order amount in the same direction."*

Para cualquier activo donde tengamos 2 o 3 anuncios activos (`G1`, `G2`, `G3`), **está prohibido que dos anuncios compartan cualquiera de estos 3 parámetros**:
1. **Precio (`price`):** Nunca pueden tener el mismo precio ni solaparse.
2. **Cantidad Total de la Orden (`initAmount`):** Nunca pueden tener la misma cantidad total de cripto publicada (ej. prohibido que `G2` y `G3` tengan ambos `624.88 USDT`).
   - *Guardarraíl esperado:* Escalonamiento obligatorio por grupo (`GROUP_INIT_MULTIPLIERS = {1: 1.00, 2: 0.985, 3: 0.975}`).
3. **Límites de Transacción (`minSingleTransAmount` y `maxSingleTransAmount`):** Nunca pueden compartir el mismo límite mínimo o máximo en ARS.
   - *Guardarraíl esperado:* Factores diferenciados por grupo (`GROUP_LIMIT_FACTORS = {1: (0.45, 0.99), 2: (0.60, 0.98), 3: (0.50, 0.97)}`) y multiplicadores de piso mínimo (`{1: 1.00, 2: 1.15, 3: 1.30}`).

### 1.3 Diferencia Mínima de Precio (Spread Mínimo entre Anuncios — Regla 5.1.3 vs Error 187055)
> **Texto Oficial Literal (FAQ 360043895111):**
> - **Price Spread Requirements (Global):** *"If you intend to post multiple ads for the same crypto-fiat pair, the price difference between them must be at least **0.5%**."*
> - **Exceptions (USD & LATAM, incluye ARS):** *"For **USD and LATAM markets**, the required price difference between multiple ads is reduced to at least **0.1%**."*

#### A. En Anuncios de COMPRA (BUY Ads — Tú pagas ARS, recibes Crypto):
- El piso reglamentario para LATAM/ARS es **`0.10%` (`0.001`)** de diferencia entre anuncios del mismo activo.
- **Guardarraíl implementado en el bot:** `MIN_AD_PRICE_DIFF_RATIO = 0.0015` (**`0.15%`**, que equivale a `~$2.43 ARS` sobre un precio de `$1620 ARS`). Otorga un margen de seguridad del `+50%` por encima del `0.10%` exigido en LATAM sin inflar el spread innecesariamente.
- **Condición matemática:** La separación entre dos anuncios adyacentes de compra `(precio_alto, precio_bajo)` garantiza siempre $\ge 0.10\%$ respecto al precio superior.

#### B. En Anuncios de VENTA (SELL Ads — Tú vendes Crypto, recibes ARS):
- **Restricción Técnica Exacta de Binance SAPI v7.4 (Error 187055):**
  Binance NO exige el 0.10% porcentual en las ventas en ARS; su validador sincrónico únicamente rechaza con `187055` si el nuevo precio se solapa dentro de la ventana de exclusión:
  $$\text{Rango Prohibido: } [X - 0.15 \text{ ARS}, \ X + 0.15 \text{ ARS}]$$
- **Guardarraíl implementado en el bot:** `SELL_AD_PRICE_DIFF_ARS = 0.35` (**`$0.35 ARS`** de separación fija entre peldaños).
- **Ventaja de Mercado:** Al usar `$0.35 ARS` en lugar de `$2.43 ARS`, los 3 anuncios de venta se mantienen en un rango compacto de `~$0.70 ARS` ($1,621.36 a $1,622.06), permitiendo que el cluster de nicho (Prex/Banco del Sol) y el cluster bancario (Santander/Galicia) capturen ventas en el Puesto #1 sin que los anuncios queden descolgados del libro de órdenes ni sufran rechazos de API.

---

## Arista 2: Reglas Técnicas de Validación Sincrónica SAPI v7.4 (`HTTP 400`)

Según [`Binance_C2C_SAPI_v7.4_Manual.pdf`](manuales_api/Binance_C2C_SAPI_v7.4_Manual.pdf), el servidor de Binance aplica validaciones inmediatas al llamar a `POST /sapi/v1/c2c/ads/post`, `update` o `updateStatus`:

| Código SAPI | Mensaje Oficial de Binance | Causa Técnica | Guardarraíl Exacto Requerido |
| :--- | :--- | :--- | :--- |
| **`187055`** | `Considering your existing Ad price(s) at X, the range for this Ad should not overlap with the existing range [X-0.15, X+0.15]` | Dos anuncios del mismo activo quedan a $\le \$0.15 \text{ ARS}$ o se cruzan en el camino mientras se actualizan de a uno. | 1. **Compras:** Separación `MIN_AD_PRICE_DIFF_RATIO` (`0.15%` $\approx \$2.43 \text{ ARS}$).<br>2. **Ventas:** Separación fija `SELL_AD_PRICE_DIFF_ARS = 0.35` ($0.35 > 0.15 \text{ ARS}$).<br>3. **Orden de ejecución en transición:** Si los precios **bajan**, actualizar primero el más bajo (`G3 -> G2 -> G1`); si **suben**, actualizar primero el más alto (`G1 -> G2 -> G3`).<br>4. Separación contra **anclas fijas** (anuncios pausados, en guerra o retenidos por histéresis). |
| **`187031`** | `El precio que estableciste debe estar dentro del rango de ...` | El precio enviado cae fuera de la banda oficial permitida por Binance respecto al precio de referencia (~`90%` a `110%`). | 1. Piso legal `min_credible_price = round(fair_spot_ars * 0.90, 2)` y techo `max_allowed_price`.<br>2. Si al escalonar hacia abajo se toca `min_credible_price`, anclar en el piso y escalonar hacia arriba.<br>3. Ignorar competidores que estén fuera de la banda (`< min_credible_price`). |
| **`187000`** | `You can only create a new Ad 4/5/6 seconds after the latest one.` | Llamar a `POST /sapi/v1/c2c/ads/post` con menos de 6 segundos de pausa entre creaciones. | Pausa obligatoria (`AD_CREATION_DELAY_SECONDS >= 6.5s`) entre cada `create_buy_ad` y backoff automático si aparece `187000`. |
| **`187005`** | `Ads can't be closed in batches, please close 1 by 1.` | Enviar múltiples `advNos` en una sola petición `updateStatus` cuando `advStatus = 4` (Cerrar). | Enviar `updateStatus(status=4)` estrictamente de a 1 anuncio por vez con delay entre llamadas. |

---

## Arista 2.1: Sistema de Guardarraíles y Filtrado Previo de Órdenes Salvajes (Anti-Outliers)

Para evitar que órdenes infladas, precios cebo, errores humanos (fat-finger) o competidores con cotizaciones atípicas (como Reba disparado o compras a precios ridículos) distorsionen los cálculos de promedios y reposicionamiento, el bot ejecuta un **filtrado previo estricto en 5 capas antes de computar cualquier decisión**:

1. **Capa 1 — Filtro de Reputación / Anti-Cebo (`market_scanner.py`):**
   - Se descartan automáticamente competidores con menos de 15 órdenes históricas (`MIN_COMPETITOR_ORDERS = 15`) o una tasa de finalización inferior al 88% (`MIN_COMPETITOR_COMPLETION_RATE = 0.88`).
2. **Capa 2 — Filtro Anti-Outliers Simétrico por Mediana (`market_scanner.py` y `sell_advisor.py`):**
   - Cuando hay $\ge 3$ precios en el libro, se calcula la mediana (`median_p`).
   - Solo se admiten cotizaciones dentro de la banda $\pm 2.5\%$ de la mediana:
     $$[\text{median\_p} \times 0.975, \ \text{median\_p} \times 1.025]$$
   - Cualquier precio disparado (ej. $+5\%$ por encima del mercado) o artificialmente deprimido queda fulminado antes de entrar a la suma del promedio.
3. **Capa 3 — Oráculo Externo de Cordura (`sell_guardrails.py`):**
   - Verificación cruzada en tiempo real contra el Bid oficial de Fiwind (`validate_oracle_sanity`).
   - Si el precio P2P desvía más de un 5% por debajo de Fiwind Bid o supera el 15% por encima (banda creíble), la decisión se bloquea automáticamente por anomalía de mercado.
4. **Capa 4 — Break-Even y Cero Pérdidas (`sell_guardrails.py`):**
   - Se audita que el precio de venta propuesto cubra el Costo Promedio Ponderado de Compra (`WAC`) más el margen mínimo o colchón configurado (`validate_break_even`). Jamás se vende a pérdida.
5. **Capa 5 — Profundidad Mínima del Libro (`sell_guardrails.py`):**
   - Se exige un mínimo de 2 vendedores reales en el método (`min_sellers >= 2`) para no anclarse a cotizaciones arbitrarias de competidores solitarios en métodos ilíquidos.

---

## Arista 3: Reglas del Motor Asincrónico Anti-Abuso (`Error 83714` — *Abnormal Advertising Behaviors*)

El bloqueo más severo de Binance P2P es el **`Error 83714`**:
> `You do not have rights to post Buy Ads due to Abnormal advertising behaviors. Please check the relevant Ad number and resolve the issue: <advNo>. Suspension in effect until <timestamp>.`

### ¿Qué dispara el `Error 83714` y cómo se previene sin exagerar?
1. **Causa 1 — Ediciones Redundantes (*No-Op Updates*):**
   - Llamar a `POST /sapi/v1/c2c/ads/update` enviando el mismo `price` (y mismos montos/límites) que el anuncio ya tiene publicado en Binance.
   - **Guardarraíl exacto:** Guardia estricta `noop_filtered` en `execute_repositioning` y en `_recompute_ad_amounts_and_limits` evaluada sobre el `final_price` **después** de la resolución de colisiones. Si `not price_changed and not has_param_changes`, **jamás se llama a la API**.
2. **Causa 2 — Micro-oscilaciones Pasivas (Cambios de centavos sin competidor):**
   - Cuando el anuncio está en techo de margen (`reposition_max_margin` o `reposition_capped`) y el spot o el benchmark fluctúa `±\$0.05 ARS` cada ciclo, editar el anuncio cada 30 segundos sin que ningún competidor nos haya superado es spam innecesario.
   - **Guardarraíl exacto (Ni exagerado ni permisivo):**
     - En **modo pasivo** (sin amenaza competitiva): aplicar `PASSIVE_PRICE_HYSTERESIS_PCT = 0.0015` (`0.15%`, escape inmediato si $\ge 0.375\%$) y `PASSIVE_UPDATE_COOLDOWN_SECONDS = 120.0` (2 minutos).
     - En **modo competitivo** (cuando un competidor real nos supera el #1 o #2, o cuando sobrepagamos por encima del rival): **NO bloquear la actualización** con el cooldown pasivo de 120s para no perder la punta, salvo que el ajuste sea irrelevante.
3. **Causa 3 — Martilleo de Errores `HTTP 400` (`187031` / `187055`):**
   - Si un anuncio recibe un rechazo `400` de la API y el bot vuelve a enviar la misma petición fallida cada 30 segundos, acumula decenas de errores consecutivos.
   - **Guardarraíl exacto:** Circuit-breaker por anuncio (`_error_cooldown_until` con `AD_API_ERROR_COOLDOWN_SECONDS = 600.0`, 10 minutos de enfriamiento tras un fallo de API en ese `advNo`).
4. **Causa 4 — Guerra de Bots Infinita:**
   - Dos bots subiéndose `+\$0.01` indefinidamente.
   - **Guardarraíl exacto:** `WarDetector` (`WAR_ESCALATION_THRESHOLD = 3` subidas en `WAR_ESCALATION_WINDOW_SECONDS = 180.0s`, enfriamiento de `WAR_COOLDOWN_MINUTES = 5` / `300s`).

---

## Arista 4: Criterios de Auditoría del Código (Anti-Exageración y Anti-Sobreescritura)

Todo guardarraíl en el código debe cumplir simultáneamente estas **4 leyes de ingeniería**:
1. **Existencia Real:** La protección debe estar conectada en el flujo de ejecución real (`main.py` -> `repositioner.py` / `ads_manager.py` -> `binance_client.py`), no solo declarada como constante o método sin llamar.
2. **No Exageración (Competitividad intacta):** Ningún guardarraíl debe impedir que el bot tome el puesto #1 en `ARS` cuando existe margen rentable y un competidor nos supera, ni separar los grupos más allá de lo razonable para LATAM (`0.15%` en vez de valores exagerados que inutilicen `G2` y `G3`).
3. **No Sobreescritura / Sin Efectos Secundarios Ocultos:** Un paso posterior del algoritmo (como `passive_hysteresis_hold` o el fallback de bajo saldo) **nunca debe pisar ni invalidar** la separación de precios o la diferenciación de `initAmount`/límites calculada en el paso anterior.
4. **Alineación entre Código y Tests (`tests/test_core_units.py`):** Los tests unitarios deben validar exactamente las constantes y reglas vigentes del bot (sin tests desfasados que esperen constantes antiguas).
