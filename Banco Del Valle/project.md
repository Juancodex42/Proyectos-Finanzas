# Banco del Valle — Scoring Calculator & Lending Engine — Definición del Proyecto

> **Estado del Proyecto:** Fase de Diseño Integral, UX/UI y Arquitectura  
> **Área:** Riesgo Crediticio (Individuos y Empresas), Tesorería Bancaria (ALM), Simulación Dinámica, Macroeconómica y Exportación de Datos

---

## 1. Visión y Propósito General

La plataforma unifica la gestión operativa, analítica y comercial de una entidad financiera moderna:
1. **Público / Individuos y Familias ("Vendemos un sueño"):** Un portal humano, aspiracional y confiable que conecta a familias con la posibilidad concreta de acceder a bienes materiales clave (vivienda propia, vehículos familiares, bienes durables) a través de préstamos transparentes y opciones de ahorro rentable.
2. **Público / Empresas y PyMEs ("Impulsamos el desarrollo productivo"):** Soluciones de financiamiento corporativo para capital de trabajo, adquisición de maquinaria industrial, galpones y flotas de vehículos comerciales, además de cuentas corrientes remuneradas y plazos fijos mayoristas para optimizar la tesorería de empresas.
3. **Interno / Empleados y Gerencia (Terminal de Control Bancario):** Un dashboard cuantitativo de alta precisión para monitorear en tiempo real el patrimonio neto, liquidez, encajes del BCRA, colocaciones mensuales/anuales (desglosadas por personas y empresas), proyecciones macroeconómicas y ejecutar la simulación acelerada del paso del tiempo.

---

## 2. Identidad Visual, Paleta Cromática y UX/UI

### A. Paleta de Colores Institucional (Inspiración: *Catamarca Ciudad*)
Tomando como base la identidad visual de Catamarca Ciudad (combinación de formalidad institucional, valles y calidez solar):

* **Azul Institucional Profundo (`#0F3A5D` / `#1E3A8A`):** Transmite solidez bancaria, seguridad jurídica, confianza y respaldo institucional. Utilizado en barra de navegación, tipografías principales y fondos del portal de empleados.
* **Naranja Cálido y Dinámico (`#FF7A00` / `#F07623`):** Transmite cercanía, optimismo, calidez humana, sol norteño y oportunidad. Utilizado en botones de acción principal (CTA), destacados de simuladores e indicadores de alerta.
* **Blanco Puro y Neutros Claros (`#FFFFFF` / `#F8FAFC` / `#F1F5F9`):** Superficies amplias, tarjetas limpias, luminosidad y lectura descansada.
* **Acentos de Estado:**
  * Verde Solvencia (`#10B981`): Préstamos al día, encajes cubiertos, ganancia generada.
  * Rojo Alerta (`#EF4444`): Días de mora $> 30$, déficit de encajes, rechazo de crédito.

### B. Isotipo y Logotipo Oficial (Identidad de Marca B+V)
* **Logotipo Tipográfico (Wordmark):**
  * `BANCO`: En tipografía blanca pura (`#FFFFFF`), peso *Bold*, sobria e institucional.
  * `DEL VALLE`: En color naranja enérgico (`#FF7A00`), peso *SemiBold*, destacando el origen territorial y la calidez.
* **Isotipo Geométrico Minimalista (Símbolo SVG):**
  * Contenedor: Cuadrado con esquinas redondeadas en fondo Azul Profundo (`#0F3A5D`).
  * Composición: Fusión de las letras **B** y **V** formando el perfil de los cerros y el valle central de Catamarca.
  * Paleta del Isotipo: Trazos geométricos en blanco puro entrelazados con el vértice central en naranja (`#FF7A00`), simbolizando el sol en el valle y la convergencia financiera.

### C. Tipografía y Escala de Lectura Cómoda
* **Títulos y Encabezados:** **`Poppins`** (Pesos *Bold* y *SemiBold*). Moderna, geométrica y cálida.
* **Cuerpo de Texto y Datos Cuantitativos:** **`Inter`** o **`Poppins Regular`**. Máxima legibilidad numérica en tablas financieras y formularios con numeración tabular (`font-variant-numeric: tabular-nums`).
* **Escala Tipográfica Estandarizada (FinTech Design System):**
  * *Texto Base (Body):* `15px - 16px` (`text-[15px]` / `text-base`), con interlineado holgado (`leading-relaxed`). Se prohíbe el uso de `text-xs` (12px) como cuerpo de texto principal para evitar la fatiga visual de "letra chica bancaria".
  * *Labels de Formularios y Controles:* `14px font-semibold` (`text-sm`).
  * *Microcopy y Badges:* Mínimo `12px` (`text-xs font-bold`) como piso absoluto para chips de estado y situaciones BCRA.
  * *Cifras y Saldo Financiero:* `24px - 36px` (`text-2xl` a `text-4xl`) con numeración tabular nítida.

### D. Filosofía UX/UI: Densidad de Información, Contenedor 1600px y Estilo Bento Grid
* **Ancho de Pantalla Ampliado (Eje X):** Se reemplaza el contenedor estrecho previo (`max-w-7xl` = 1280px) por un contenedor centralizado de **`1600px`** (`max-w-[1600px] mx-auto px-4 sm:px-8 xl:px-12`).
  * En monitores 1080p (1920px), esto **reduce los espacios muertos laterales en un 50% exacto** (de 320px de margen a 160px a cada lado), permitiendo que los simuladores, tablas contables y gráficos respiren sin apiñarse.
* **Bento Grid Layout:** Inspirado en fintechs de referencia global (Stripe, Mercury, Revolut). Paneles modulares con bordes finos (`ring-1 ring-slate-200/80` en claro, `border-[#223552]` en oscuro), fondos con micro-contrastes y sombras sutiles (`shadow-sm`).
* **Cero Espacio Vacío Inerte:** Cada módulo presenta métricas financieras ricas, badges comparativos de desempeño (`+12.4% vs mes anterior`), estados de transacción en tiempo real y micro-interacciones fluidas.
* **Iconografía Vectorial:** Integración completa de la suite **Lucide Icons** (`lucide-react`) para consistencia visual institucional.

### E. Sistema Dual de Temas: Modo Claro (WCAG AAA) y Modo Noche (Andean Obsidian)
* **Modo Claro de Alto Contraste:**
  * Se eliminan los tonos grises lavados (`slate-400` sobre blanco que tenían un contraste ilegible de 2.8:1).
  * Texto Primario en `Slate 900` (`#0F172A`, ratio 16.1:1 - WCAG AAA).
  * Texto Secundario en `Slate 700` (`#334155`, ratio 9.6:1 - WCAG AAA).
  * Texto Descriptivo en `Slate 600` (`#475569`, ratio 5.9:1 - WCAG AA).
  * Navbar, Hero y Encabezados en tonos claros y luminosos para una experiencia diurna armónica.
* **Modo Noche (Andean Obsidian FinTech):**
  * Fondo general (Canvas): Azul obsidiana profundo `#080D1A` (evitando negros planos OLED que fatigan la lectura de números).
  * Superficies Bento Cards: `#0F1A2E` con sutil resplandor.
  * Bordes Delimitadores: `#223552`.
  * Acentos Lumniscentes: Naranja solar `#FF8C1A` y Verde Esmeralda `#10B981`.
  * Secciones 100% integradas: Ningún panel o modal queda con fondos claros descolgados.
* **Selector Segmentado Inequívoco:** Switch en la barra superior con dos botones claramente identificables `[ ☀️ Claro ✓ ]` y `[ 🌙 Noche ✓ ]`, donde el modo activo se distingue con fondo sólido y tilde, eliminando toda confusión entre el estado actual y la acción a realizar.

### F. Estrategia de Imágenes ("Vendemos un sueño")
* **Concepto:** Familias sonrientes en el jardín o living de su casa propia, parejas recibiendo las llaves de su vehículo, personas impulsando sus proyectos personales con bienes tangibles.
* **Origen de activos:** Curaduría de bancos de imágenes de alta definición libres de derechos de autor (licencia Unsplash / Pexels de uso comercial sin regalías).

---

## 3. Arquitectura Frontend: Dual Portal (Cliente vs. Empleado)

```
                              [ Portal Web Bancario ]
                                         |
            +----------------------------+----------------------------+
            |                                                         |
     [ Portal Público Clientes ]                              [ Portal Empleados / Gerencia ]
     - Hero: "Vendemos un sueño"                              - Login Especial de Seguridad
     - Simulador Préstamos (Francés en vivo)                  - KPI Cards Patrimoniales en Tiempo Real
     - Simulador Inversiones PF / Flexible                    - Monitoreo de Encajes BCRA
     - Menú: Inicio, Nosotros, Simuladores,                   - Curva Dinámica de Tasas
       Crear Cuenta, Ingresar                                 - Botón: "Acelerar Simulación (1s = 1d)"
     - Descarga de Comprobantes (PDF/Excel)                   - Motor Universal de Exportación (PDF, XLSX, CSV)
```

### A. Portal Público para Clientes e Integración con BD

#### 1. Menú Superior Dinámico según Estado de Autenticación y Rol
A diferencia de barras estáticas que exponen todas las vistas en simultáneo, el encabezado superior (**`Navbar.jsx`**) implementa un **comportamiento adaptativo estricto según la sesión del usuario**:

* **A. Estado No Autenticado (Visitante / Público):**
  * Exhibe el Selector de Segmento: `[ 👥 Individuos & Familias ]` | `[ 🏢 Empresas & PyMEs ]`.
  * Accesos centrales: *Portal Público*, *Simuladores*, *Acerca de*.
  * Botones de acción derecha: `[ Crear Cuenta ]` e `[ Ingresar ]`.
  * Selector de Tema: `[ ☀️ Claro ✓ ]` / `[ 🌙 Noche ]`.
* **B. Estado Autenticado como GERENTE (`user.rol === 'GERENTE'` o `'EMPLEADO'`):**
  * **Desaparecen las opciones irrelevantes:** Se ocultan inmediatamente el selector de segmento (*Individuos & Familias*, *Empresas & PyMEs*) y el acceso al portal público general.
  * **La barra queda en modo exclusivamente gerencial:** Muestra el isotipo del banco, el badge destacado `Terminal Ejecutiva de Tesorería & ALM`, el perfil del operador (`Gerencia de Tesorería`), el switch de tema y el botón para `[ Cerrar Sesión ]`.
* **C. Estado Autenticado como CLIENTE (`user.rol === 'CLIENTE'`):**
  * **Desaparecen las opciones corporativas:** Se oculta el botón de acceso a la terminal de *Gerencia* y el conmutador de segmentos.
  * **La barra queda en modo transaccional:** Muestra el isotipo, el acceso a `Mi Cuenta (Home Banking)`, el saludo al titular (`Juan José Cano`), avatar con iniciales y el botón para `[ Cerrar Sesión ]`.

#### 2. Modal de Inicio de Sesión (`LoginModal.jsx`) y "Cuentas Guardadas"
* **Sustitución Terminológica Oficial:** En el modal de login se elimina la denominación *"Cuentas Demo"* o *"Accesos Demo de 1-Clic"*, reemplazándola formalmente por **"Cuentas Guardadas"**.
* **Comportamiento:** Permite iniciar sesión directa con credenciales almacenadas para agilizar las pruebas de roles:
  * **Juan José Cano (Cliente):** Ingreso a Home Banking (`35123456` / `Valle1234!`).
  * **Gerencia de Tesorería (Gerente):** Ingreso a Dashboard ALM (`gerencia@bancodelvalle.com.ar` / `Gerencia2026!`).
* Al iniciar sesión con cualquiera de las cuentas, la aplicación redirige de forma atómica a la vista respectiva y reconfigura la Navbar según el rol asignado.

#### 3. Sección Hero Dinámica según Segmento
* **Si el usuario elige "Individuos & Familias":**
  * Fotografía de impacto emocional (familia disfrutando de su nueva vivienda o vehículo).
  * Lema: *"El sueño de tu casa, tu auto y tu futuro, hoy más cerca"*.
  * Propuesta: Préstamos personales y prendarios con cuotas a tu medida.
* **Si el usuario elige "Empresas & PyMEs":**
  * Fotografía de desarrollo productivo (parque industrial, camiones de logística, galpones o maquinaria moderna).
  * Lema: *"Financiamiento estratégico para el crecimiento de tu empresa"*.
  * Propuesta: Créditos para capital de trabajo, adquisición de bienes de capital y descuento de cheques con tasas preferenciales.

#### 3. Simuladores Inteligentes Conectados en Tiempo Real a SQLite
A diferencia de calculadoras estáticas genéricas, el simulador del sistema **se conecta vía API con la base de datos SQLite**:

```
[ Input: DNI o CUIT + Monto Deseado ]
                  |
                  v
       ( API / Database Lookup )
                  |
  +---------------+---------------+
  | Si el Cliente EXISTE en BD:   | Si es NUEVO (Sin historial):
  | 1. Lee ingresos o facturación | 1. Aplica matriz estándar
  |    comprobada en `personas` o |    de mercado base.
  |    `empresas`.                | 2. Invoca simulación de
  | 2. Obtiene peor situación     |    buró (Veraz mock) en
  |    Veraz y mora previa.       |    tiempo real para calificar.
  | 3. Calcula TASA EXACTA        | 3. Solicita declarar ingreso
  |    PERSONALIZADA (Pricing).   |    estimado para validar cuota.
  +---------------+---------------+
                  |
                  v
[ Validación de Liquidez de Tesorería en BD ]
Consulta `balance_patrimonio_banco.cashflow_seguro_prestable`:
- Si hay liquidez -> Emite Certificado de PRE-APROBACIÓN INMEDIATA.
- Si no hay liquidez -> Ofrece monto menor o recalcula fecha de desembolso.
```

* **Simulador de Préstamos para Individuos:** Sistema Francés, cuota fija, validación de cuota $\le 35\%$ del ingreso mensual comprobado en BD.
  * **Segmentación por `categoria_laboral` en el Scoring:**
    * *Empleados Públicos y Jubilados:* Máxima estabilidad laboral/previsional $\rightarrow$ Bonificación de 2 a 3 puntos en la tasa activa y habilitación de plazos extendidos de hasta 60 cuotas.
    * *Empleados Privados Formals:* Se valida `antiguedad_laboral_meses` ($\ge 12$ meses para aprobación directa; $< 12$ meses con cupo acotado).
    * *Monotributistas y Autónomos:* Ingresos variables $\rightarrow$ Ratio cuota/ingreso más prudente (máximo 25% a 30%) con verificación de constancia AFIP.
* **Simulador y Clasificación para Empresas:**
  * **Tipos Societarios Soportados:**
    * *Comerciales con Fines de Lucro:* `SA`, `SRL`, `SAS` (con fianza de socios si es nueva), `SAU`.
    * *Economía Social y Solidaria:* `COOPERATIVA`, `MUTUAL` (exentas de ganancias, evaluación de excedentes).
    * *Entidades Sin Fines de Lucro:* `ONG_FUNDACION` (asociaciones civiles, clubes, foco en líneas de fomento y plazos fijos de tesorería).
    * *Especiales:* `FIDEICOMISO`.
  * **Lógica de Scoring PyME:** Capacidad de repago sobre facturación mensual promedio (cuota máxima $\le 20\%$ de la facturación), detección automática de exenciones impositivas y requerimiento de fianza solidaria según tipo societario.
* **Simulador de Inversión y Tesorería:** Plazo Fijo tradicional vs. Cuentas remuneradas de liquidez inmediata (con tramos minoristas y mayoristas para empresas).
* **Cuentas Transaccionales y Rendimiento Flexible Diario:**
  * Para usuarios que solo utilizan la plataforma para depositar, transferir y retirar dinero (Caja de Ahorro / CBU / Alias).
  * **Activación Automática de Rendimiento:** El saldo a la vista no queda estéril; genera intereses diarios de forma automática (modelo *Money Market* / billetera remunerada).
  * **¿De cuánto es el rendimiento flexible?**
    $$\text{TNA}_{\text{flexible}} \approx \text{TNA}_{\text{plazo\_fijo}} \times 0.75 \text{ (ej. 28.5\% TNA)}$$
    Es inferior al Plazo Fijo porque el banco debe mantener un encaje técnico del 30% en el BCRA y garantizar liquidez inmediata.
  * **Acreditación Diaria en Cierre (Daily Tick):**
    $$\text{Rendimiento Diario} = \text{Saldo en Cuenta} \times \frac{\text{TNA}_{\text{flexible}}}{365}$$
  * **El Spread del Banco (Nuestra Ganancia):**
    El banco toma ese dinero a la vista pagando el **28.5% TNA** y lo coloca en préstamos personales y comerciales al **60% o 65% TNA**. La diferencia (**~33% TNA**) es el margen financiero directo que engrosa las utilidades del banco y su patrimonio líquido.
* **Ciclo de Vida, Bajas (Soft Delete) y Cumplimiento AML / Antifraude (UIF):**
  * **Prohibición de borrado físico:** Las cuentas nunca se eliminan con `DELETE` por exigencia de la UIF (conservación mínima de 10 años).
  * **Soft Delete:** Solo se permite solicitar baja (`BAJA_SOLICITADA`) si la persona no registra deudas activas en préstamos ni depósitos vigentes.
  * **Protocolo Oficial Antifraude y PLA/FT (UIF / BCRA):**
    * Basado en el **Enfoque Basado en Riesgo (EBR)** y la **Resolución UIF N° 78/2025**. Se prohíben bloqueos automáticos intempestivos.
    * Si las operaciones acumuladas en el mes se desvían sustancialmente del perfil habitual y superan los umbrales oficiales en SMVM (ej. $> 40\text{ SMVM}$):
      1. Se dispara una **Alerta de Monitoreo Interno** en Compliance sin alterar la operativa del cliente.
      2. Se emite un requerimiento formal de origen de fondos (*RFI*) otorgando un plazo legal razonable de **15 a 30 días hábiles** para presentar comprobantes (boleto de compraventa, factura, donación).
      3. Solo se procede a inmovilización preventiva (`SUSPENDIDO_AML`) ante vencimiento del plazo sin descargo, documentación apócrifa, orden judicial expresa o listado en RePET. Documentado en detalle en [`docs/compliance_aml_fraude_bajas.md`](docs/compliance_aml_fraude_bajas.md).
* **Sección "Nuevas Inversiones (Alto Riesgo)":**
  * Card promocional destacada en la sección de inversiones con badge distintivo: `[ Próximamente ]`.
  * **Interacción Hover (Tooltip dinámico):** Al pasar el cursor del mouse, se despliega una tarjeta animada que indica:  
    > *"Pronto: Acciones, Bonos soberanos/corporativos, Índices y Derivados financieros"*.
  * Permite medir el interés de los usuarios (lead-capture) para futuras integraciones con el mercado de capitales (ALyC).
* **Exportación Inmediata:** Botón para descargar en **PDF** la cotización membretada oficial con validez por 48 horas.

#### 4. Flujo de Registro y Onboarding de Nuevos Clientes (UX/UI y Normalización de Datos)

El botón `[ Crear Cuenta ]` del Navbar abre un asistente interactivo multi-paso (**Stepper Modal / `RegisterModal.jsx`**) que guía al solicitante en un proceso de 3 pasos sin fricción:

```
[ Click en "Crear Cuenta" ]
             |
             v
+--------------------------------------------------------------------------+
|  PASO 1: Identificación y Credenciales                                   |
|  - Switch: [ Persona Humana ] | [ Empresa / PyME ]                       |
|  - Inputs Persona: DNI/CUIL, Nombre Completo, Email, Contraseña          |
|  - Inputs Empresa: CUIT, Razón Social, Tipo Societario, Email, Password  |
+--------------------------------------------------------------------------+
             |
             v
+--------------------------------------------------------------------------+
|  PASO 2: Perfil Socioeconómico y Coordenadas                             |
|  - Persona: Categoría Laboral, Antigüedad (meses), Ingreso mensual       |
|    Checkbox: [x] "Quiero cobrar mi sueldo aquí (Cuenta Sueldo)"          |
|  - Empresa: Rubro, Facturación Anual estimada, Exención impositiva       |
|  - Ubicación: Localidad (San Fernando del Valle de Catamarca / etc.)     |
+--------------------------------------------------------------------------+
             |
             v
+--------------------------------------------------------------------------+
|  PASO 3: Validación, Términos y Creación Atómica (ACID)                  |
|  - Consentimiento informado y políticas UIF / PLA-FT                     |
|  - Botón: [ Confirmar y Abrir Mi Cuenta ]                                |
|  - Generación en vivo de CBU (22 dígitos) y Alias bancario único         |
|  - Asignación de estado inicial ('ACTIVO') y TNA Flexible (28.5%)        |
|  - Emisión de Token JWT e ingreso directo al Home Banking                |
+--------------------------------------------------------------------------+
```

##### A. Reglas de Normalización y Transformación de Datos (Frontend ➔ DTO ➔ SQLite)
1. **Documentos Fiscales (`dni`, `cuil`, `cuit`):**
   * El frontend permite ingresar máscaras comunes (`20-35123456-7` o `35.123.456`).
   * El backend normaliza extrayendo estrictamente los dígitos numéricos (`re.sub(r'\D', '', val)`), validando longitud (8 dígitos para DNI, 11 para CUIL/CUIT) y aplicando algoritmo Módulo 11 para CUITs.
2. **Nombres y Razón Social:**
   * Se eliminan espacios redundantes (`strip()`) y se aplica capitalización uniforme (*Title Case* o mayúsculas canónicas).
3. **Correos Electrónicos:**
   * Normalización obligatoria a minúsculas (`email.strip().lower()`) con validación de formato RFC 5322.
4. **Contraseñas y Seguridad:**
   * Validación frontend: mínimo 8 caracteres, al menos 1 número y 1 carácter en mayúscula.
   * En backend: Se hashea de inmediato con **Bcrypt** (`cost = 12`) y sal criptográfica única. **Bajo ninguna circunstancia se persiste en texto plano ni se registra en logs**.
5. **Generación Automática de Coordenadas Bancarias:**
   * **CBU (22 dígitos):**
     * Bloque 1 (Entidad y Sucursal, 8 dígitos): `00000031` (Código asignado a Banco del Valle).
     * Bloque 2 (Tipo cuenta + correlativo + dígito verificador, 14 dígitos): `000` + correlativo autoincremental asegurado en transacción.
   * **Alias Único:**
     * Algoritmo generador: `NOMBRE.APELLIDO.VALLE` (sin espacios, eñes ni caracteres especiales). En caso de homónimo, se sufija un número correlativo (`NOMBRE.APELLIDO.VALLE.2`).

##### B. Transacción Atómica de Persistencia (Orquestación en Repositorios)
La creación del usuario se realiza en un único bloque transaccional ACID (`BEGIN TRANSACTION` ... `COMMIT`):
1. **Verificación de duplicados:** Chequeo en `personas` (DNI), `empresas` (CUIT) y `usuarios_credenciales` (identificador y email). Si existe $\rightarrow$ `HTTP 409 Conflict`.
2. **Insert en `personas` o `empresas`:** Registra la entidad con `estado_cuenta = 'ACTIVO'`.
3. **Insert en `usuarios_credenciales`:** Guarda identificador, email y `password_hash` con `rol = 'CLIENTE'` enlazado al `persona_id` o `empresa_id`.
4. **Insert en `cuentas_transaccionales`:** Crea la Caja de Ahorro / Cuenta Corriente con CBU, Alias, `tna_rendimiento_diario = 0.285`, `saldo_actual = 0.0` y estado `'ACTIVO'`.
5. **Insert en `auditoria_accesos`:** Registra el evento de alta con dirección IP del cliente.
6. **Autenticación Inmediata:** Se genera el token JWT y se redirige al cliente a su Home Banking personalizado sin necesidad de re-ingresar credenciales.

---

### B. Portal Privado de Cliente Autenticado (Home Banking de Juan José)

Al iniciar sesión como cliente individual estándar, la plataforma presenta un Home Banking completo conectado a SQLite:

#### 1. Perfil del Usuario Demo ("Juan José")
* **Nombre:** Juan José Cano (`20-35123456-7` / `35123456`), San Fernando del Valle de Catamarca.
* **Saldo Inicial Precargado:** **$3.000.000,00** en Caja de Ahorro remunerada.
* **Cuenta Sueldo Activa:** Cobro mensual automático de **$3.000.000,00** el día 1 de cada mes simulado.
* **Coordenadas Bancarias:** CBU `0000003100012345678901` | Alias `JUAN.BANCO.VALLE`.

#### 2. Operatoria y Flujos UX/UI
* **Dashboard Principal:** Visualización de Saldo Disponible, tarjeta con intereses flexibles devengados hoy (+28.5% TNA) y lista de últimos movimientos.
* **Flujo "Transferir":**
  1. Input de Monto a transferir y CBU/Alias destino.
  2. Modal de confirmación: *"¿Estás seguro que deseas transferir $X a [Destinatario]?"*.
  3. Al confirmar: Pantalla realista de contingencia: *"⚠️ Sistema COELSA en mantenimiento programado. Tu dinero permanece seguro en tu cuenta."*
* **Flujo "Depositar / Ingresar Dinero":**
  * Exhibe CBU y Alias con botones de copiado rápido.
  * Botón interactivo: `[ + Simular Depósito de Prueba ]` para inyectar fondos ficticios a la cuenta y validar la actualización del balance contable.
* **Flujo "Constitución y Cancelación de Plazo Fijo":**
  * Juan José puede constituir un Plazo Fijo descontando de su saldo (ej. $1.000.000).
  * **Conexión en Vivo:** El plazo fijo se graba en SQLite e impacta en tiempo real en la Terminal de Gerencia (aumenta depósitos y recalcula el Cashflow Prestable).
  * **Cancelación Anticipada (Norma BCRA):** Botón *"Cancelar Plazo Fijo sin Intereses"*, que devuelve el 100% del capital original a la cuenta corriente pero anula las ganancias devengadas ($0 interés).
* **Control de Simulación para el Cliente:**
  * Incluye el botón interactivo **"Acelerar Simulación (1s = 1d)"**, permitiendo a Juan José ver cómo día a día se acreditan los intereses flexibles y cómo llega su sueldo el primer día de cada mes. Documentado en [`docs/homebanking_ux_cuentas_sueldo.md`](docs/homebanking_ux_cuentas_sueldo.md).

---

### C. Portal Especial para Empleados y Gerencia (Dashboard Ejecutivo)

#### 1. Tarjetas de Métricas Principales (Bento Grid de Alta Densidad en Tiempo Real)
Diseñadas con estética de alta densidad financiera (tipo Bloomberg / Mercury / Stripe), sin espacios muertos y con indicadores comparativos (*badge pills*):
* **Patrimonio Neto Total:** Capital propio + utilidades acumuladas ($50.000.000 base + utilidades del tick). Badge comparativo: `+2.8% vs mes anterior`.
* **Base de Depósitos:** Desglose en vivo de volumen en Plazos Fijos vs. Cuentas Flexibles.
* **Colocaciones Crediticias:** Monto total prestado en el mes corriente y acumulado del año, segmentado por Individuos y PyMEs.
* **Cashflow Seguro Prestable:** Capital líquido disponible en caja autorizado para nuevos créditos sin violar encajes mínimos.
* **Posición de Efectivo Mínimo BCRA:** Indicador gráfico de cumplimiento legal (Superávit de encaje en verde `#10B981` / Alerta preventiva en naranja `#FF7A00`).
* **Tasa de Interés Activa y Pasiva:** Curva en movimiento según liquidez e inflación esperada (Spread bancario instantáneo).

#### 2. Centro de Control de Simulación Temporal ("Acelerar Simulación")
* **Botón Maestro: "Acelerar Simulación"**:
  * Velocidad acelerada donde **1 segundo real = 1 día bancario**.
  * Selector de velocidad (1x = 1 día/seg, 5x = 5 días/seg, Pausa, Avanzar 1 Día).
* **Efecto Visual Reactivo:** A medida que pasan los días simulados, las gráficas, balances, cobranzas, mora y tasas oscilan en directo vía WebSocket `/ws/simulacion`.

#### 3. Segmentación Visual de Gráficos Analíticos (Librería Recharts)
El panel gerencial se organiza en **tres apartados analíticos claramente segmentados**:

1. **Gráfico de Torta / Donut (`BalanceDonutChart.jsx`) — Composición del Balance y Encajes:**
   * Muestra visualmente la estructura de activos del banco:
     * Cartera de Préstamos Personales y PyMEs (colocaciones activas generadoras de interés).
     * Encaje Obligatorio Inmovilizado en BCRA (30% flexibles, 15% plazos fijos).
     * Liquidez Disponible y Títulos de Tesorería.
   * Tooltip interactivo con porcentajes y montos exactos en pesos argentinos.

2. **Gráfico de Barras (`AlmGapsBarChart.jsx`) — Descalce de Plazos ALM y Brechas de Liquidez:**
   * Segmentación temporal de vencimientos de pasivos (depósitos a devolver) frente a cobranzas de activos (cuotas a percibir) en tramos de 30 días, 60 días y 90 días.
   * Permite anticipar tensiones de liquidez y calcular la brecha marginal acumulada.

3. **Gráficos de Líneas y Proyecciones Multi-Escenario (`ProfitProjectionsChart.jsx` y `LiveRatesChart.jsx`):**
   * **Eje Y:** Ganancias netas acumuladas ($) y valor total del Patrimonio Neto.
   * **Eje X:** Meses del año y selector de horizonte temporal (**1 año, 3 años y 5 años**).
   * **Tres Curvas de Escenarios Macroeconómicos Simulados:**
     1. *Escenario Optimista (Bull):* Inflación a la baja, PBI en expansión (+3%), mora < 2%.
     2. *Escenario Base (Consenso REM):* Inflación mediana REM, mora controlada (~5.5%).
     3. *Escenario Pesimista (Stress Test):* Shock inflacionario, contracción (-3.5%), mora > 12%.
   * **Curva de Spread:** Comparativa en vivo de TNA Activa (cobrada) vs TNA Pasiva (pagada).

#### 4. Gestión del Margen Financiero (P&L) y Destino de los Intereses
* **Net Interest Income (NII):**
  $$\text{Ganancia Neta} = \sum \text{Intereses Cobrados (Préstamos)} - \sum \text{Intereses Pagados (PF + Flexibles)} - \text{Incobrables}$$
* **Ciclo de Reinversión Inmediata:** La ganancia neta por intereses se capitaliza contablemente en el **Patrimonio Neto** y expande en tiempo real el **Cashflow Seguro Prestable**. Documentado en [`docs/margen_financiero_y_proyecciones_escenarios.md`](docs/margen_financiero_y_proyecciones_escenarios.md).

---

## 4. Motor Universal de Exportación de Datos (PDF, Excel, CSV) con Selector de Fechas (Calendario)

En **cada módulo y tabla** del sistema (tanto para empleados como para clientes en su panel) se incorpora un componente estándar de exportación profesional (**`ExportModal.jsx`** integrado con **`DateRangePicker.jsx`**):

### A. Selector de Rango de Fechas Interactivo (Calendario Financiero)
* **Selectores Fecha Inicio y Fecha Fin:** Inputs visuales tipo calendario con validación de fechas (`Desde [AAAA-MM-DD]` - `Hasta [AAAA-MM-DD]`).
* **Botones de Rango Rápido (Presets bancarios):**
  * `[ Hoy ]`: Operaciones del día simulado en curso.
  * `[ Mes Actual ]`: Liquidación contable del mes calendario corriente.
  * `[ Último Trimestre ]`: Balance trimestral para auditoría y BCRA.
  * `[ Histórico Completo ]`: Todos los registros archivados en base de datos.
* **Filtros por Estado:** `TODOS`, `ACTIVOS`, `VENCIDOS`, `EN_MORA`.

### B. Formatos de Salida Soportados y Descarga Inmediata
1. **Excel (.xlsx) (Análisis Contable):** Archivo con hojas estructuradas, formatos de celda monetarios y fórmulas de totales para análisis en tablas dinámicas.
2. **PDF (Documento Oficial Membretado):** Reporte corporativo con el Isotipo oficial B+V, resumen de métricas clave del período, tablas formateadas y pie de página de auditoría contable.
3. **CSV (Integración Analítica):** Archivo delimitado por comas (`UTF-8` con BOM para compatibilidad con Excel) para exportación masiva y consumo de datos.

### C. Módulos con Exportación Habilitada
* **Módulo de Préstamos:** Historial de créditos otorgados, cartera viva, cobranzas del período y detalle de cuotas en mora.
* **Módulo de Plazos Fijos:** Depósitos captados en el rango, vencimientos, renovaciones e intereses liquidados.
* **Módulo de Depósitos Flexibles:** Movimientos de ingresos/retiros y rendimientos diarios devengados.
* **Módulo de Tesorería y Balance:** Snapshots diarios de patrimonio neto, encajes obligatorios BCRA y cashflow prestable.

---

## 5. Entorno Macroeconómico: Inflación y Actividad Económica

Para calibrar la tasa de interés y los límites de riesgo, el motor conecta dos variables macroeconómicas clave:

### A. Inflación Proyectada (REM BCRA y Consultoras)
* Aplica la **Ecuación de Fisher** para garantizar tasas reales positivas:
  $$\text{TNA Base} \approx \text{Inflación Esperada 12m} + \text{Margen de Intermediación}$$
* Documentado en: [`docs/proyecciones_inflacion_consultoras.md`](docs/proyecciones_inflacion_consultoras.md).

### B. Actividad Económica (EMAE / PBI Proyectado)
* **Canal de Transmisión del Ciclo Económico:**
  * **En recesión (EMAE en caída / PBI $< -1\%$):** Se contrae el ratio máximo de endeudamiento familiar (baja de 35% a 25% del ingreso) y se incrementa el factor de mora proyectada ($F_{\text{macro}} = 1.25\text{ a }1.40$).
  * **En expansión (PBI $> +1\%$):** Se normaliza la morosidad y se amplía la capacidad de crédito.
* Documentado en: [`docs/proyecciones_macro_actividad_economica.md`](docs/proyecciones_macro_actividad_economica.md).

---

## 6. Esquema Relacional de Base de Datos SQLite Unificada (`banco_scoring.db`)

```
   [ personas ] (Individuos)                [ empresas ] (PyMEs / Corp)
        |                                        |
        +-------------------+--------------------+
                            |
           +----------------+----------------+----------------+
           |                                 |                |
           v                                 v                v
[ historial_veraz_externo ]             [ prestamos ]   [ plazos_fijos ]
                                             |                |
                                             v                v
                                         [ cuotas ]  [ cuentas_transaccionales ]
                                      (mora exacta)           |
                                                              v
                                                    [ movimientos_cuenta ]
                                                    (depósitos, retiros,
                                                     transferencias, yield)

[ balance_patrimonio_banco ]           (Snapshots diarios de solvencia y liquidez)
[ proyecciones_inflacion ]              (Histórico REM y consultoras para calibración de tasas)
[ proyecciones_actividad_economica ]    (PBI, EMAE y factor de riesgo macroeconómico)
```

1. **`personas`**: `id`, `dni` (UNIQUE), `nombre_completo`, `localidad`, `categoria_laboral`, `antiguedad_laboral_meses`, `ingreso_mensual_comprobado`, `monto_sueldo_acreditado` (REAL DEFAULT 3000000.0), `dia_cobro_sueldo` (INTEGER DEFAULT 1), `estado_cuenta` ('ACTIVO', 'SUSPENDIDO_AML', 'PENDIENTE_DOCS', 'BAJA_SOLICITADA', 'CERRADO'), `fecha_alta`.
2. **`empresas`**: `id`, `cuit` (UNIQUE), `razon_social`, `tipo_societario`, `rubro_actividad`, `localidad`, `facturacion_anual_comprobada`, `requiere_fianza_socios`, `exencion_impositiva`, `estado_cuenta` ('ACTIVO', 'SUSPENDIDO_AML', 'PENDIENTE_DOCS', 'BAJA_SOLICITADA', 'CERRADO'), `fecha_alta`.
3. **`cuentas_transaccionales`** (Cajas de Ahorro / Cuentas Corrientes remuneradas): `id`, `persona_id` (NULLable), `empresa_id` (NULLable), `cbu` (TEXT UNIQUE 22 dígitos), `alias` (TEXT UNIQUE), `saldo_actual` (REAL), `tna_rendimiento_diario` (REAL), `es_cuenta_sueldo` (INTEGER DEFAULT 1), `permite_extraccion_inmediata` (INTEGER DEFAULT 1), `estado` ('ACTIVA', 'SUSPENDIDO_AML', 'CERRADA').
4. **`movimientos_cuenta`** (Auditoría de fondos y transferencias): `id`, `cuenta_id` (FK), `tipo_movimiento` ('DEPOSITO', 'EXTRACCION', 'TRANSFERENCIA_IN', 'TRANSFERENCIA_OUT', 'RENDIMIENTO_FLEXIBLE_DIARIO', 'COBRO_CUOTA_PRESTAMO', 'LIQUIDACION_PLAZO_FIJO', 'ACREDITACION_SUELDO'), `monto` (REAL), `saldo_posterior` (REAL), `fecha_hora` (TEXT), `descripcion` (TEXT), `alerta_aml` (INTEGER DEFAULT 0).
5. **`historial_veraz_externo`**: `id`, `persona_id` (NULLable), `empresa_id` (NULLable), `fecha_consulta`, `score_externo`, `peor_situacion_bcra`, `monto_deuda_externa_total`, `cantidad_bancos_acreedores`, `cheques_rechazados_monto`.
6. **`prestamos`**: `id`, `persona_id` (NULLable), `empresa_id` (NULLable), `tipo_credito`, `monto_capital`, `tasa_nominal_anual`, `cantidad_cuotas`, `fecha_otorgamiento`, `estado`.
7. **`cuotas`**: `id`, `prestamo_id`, `numero_cuota`, `monto_cuota`, `fecha_vencimiento`, `fecha_pago`, `dias_mora`, `intereses_punitorios`.
8. **`plazos_fijos`**: `id`, `persona_id` (NULLable), `empresa_id` (NULLable), `monto_depositado`, `tasa_nominal_anual`, `fecha_inicio`, `fecha_vencimiento`, `intereses_a_generar`, `estado`.
9. **`balance_patrimonio_banco`**: `id`, `fecha_corte`, `total_depositos_plazo_fijo`, `total_depositos_flexibles`, `encaje_obligatorio_bcra`, `capital_propio_patrimonio`, `total_prestado_activo`, `cashflow_seguro_prestable`.
10. **`proyecciones_inflacion`**: `id`, `fecha_relevamiento`, `inflacion_proyectada_12m`, `fuente`, `tasa_referencia_politica_monetaria`.
11. **`proyecciones_actividad_economica`**: `id`, `fecha_relevamiento`, `variacion_pbi_proyectada_anual`, `emae_ultimo_interanual`, `fase_ciclo`, `factor_macro_riesgo`.
12. **`usuarios_credenciales`**: `id`, `persona_id` (NULLable), `empresa_id` (NULLable), `identificador` (TEXT UNIQUE: DNI/CUIT o Legajo/Email), `email` (TEXT UNIQUE), `password_hash` (TEXT NOT NULL con Bcrypt), `rol` ('CLIENTE', 'EMPLEADO', 'GERENTE'), `intentos_fallidos` (INTEGER DEFAULT 0), `bloqueado_hasta` (TEXT NULL), `ultimo_login` (TEXT NULL), `fecha_creacion` (TEXT).
13. **`auditoria_accesos`**: `id`, `usuario_id` (FK), `fecha_hora` (TEXT), `direccion_ip` (TEXT), `exitoso` (INTEGER: 1 o 0), `motivo_falla` (TEXT).

---

## 7. Arquitectura de Software y Estructura de Carpetas (Fullstack)

El proyecto adopta una arquitectura desacoplada donde el backend en Python/FastAPI/SQLite provee la lógica pura y endpoints (REST + WebSocket), mientras que el frontend en React/Vite/Tailwind materializa la experiencia dual (Clientes vs. Empleados).

```text
Scoring calculator/
├── docs/                               # Documentación normativa, matemática, macro y diagramas
│   ├── normativa_encajes_bcra.md
│   ├── multiplicador_y_cashflow_prestable.md
│   ├── margen_financiero_y_proyecciones_escenarios.md
│   ├── proyecciones_inflacion_consultoras.md
│   ├── proyecciones_macro_actividad_economica.md
│   ├── compliance_aml_fraude_bajas.md
│   ├── homebanking_ux_cuentas_sueldo.md
│   ├── seguridad_autenticacion_credenciales.md
│   ├── diagrama_logica_negocio_banco.md
│   ├── diagrama_usuarios_empresas_aml_bloqueos.md
│   └── diagrama_plazos_fijos_flexibles_prestamos.md
├── tests_unitarios/                    # Suite de pruebas unitarias (Pytest)
├── src/                                # BACKEND (Python / FastAPI / SQLite)
│   ├── domain/                         # Capa de Dominio (Reglas de negocio puras)
│   │   ├── models.py                   # Entidades y Dataclasses
│   │   ├── scoring.py                  # Lógica de scoring de riesgo y mora
│   │   ├── treasury.py                 # Encajes BCRA, cashflow seguro y ALM
│   │   ├── compliance_aml.py           # Reglas antifraude, validación UIF y soft delete
│   │   ├── macro_projections.py        # REM BCRA, inflación, EMAE/PBI y Fisher
│   │   └── interest_rate.py            # Pricing de tasas (Francés, spreads)
│   ├── database/                       # Capa de Persistencia (SQLite)
│   │   ├── connection.py               # Pool y transacciones ACID
│   │   ├── schema.sql                  # DDL de tablas e índices
│   │   └── repositories/               # Repositorios por entidad
│   │       ├── usuario_repo.py
│   │       ├── persona_repo.py
│   │       ├── empresa_repo.py
│   │       ├── cuenta_repo.py
│   │       ├── movimiento_repo.py
│   │       ├── prestamo_repo.py
│   │       ├── deposito_repo.py
│   │       ├── balance_repo.py
│   │       ├── inflacion_repo.py
│   │       └── actividad_repo.py
│   ├── services/                       # Servicios e Integraciones
│   │   ├── security_service.py         # Hashing Bcrypt, tokens JWT y RBAC
│   │   ├── veraz_service.py            # Consulta y mock de buró externo
│   │   └── export_service.py           # Generador de PDFs, Excels y CSVs
│   ├── simulation/                     # Motor de Simulación Temporal
│   │   ├── clock.py                    # Reloj virtual
│   │   ├── daily_tick.py               # Cierre diario (mora, devengamientos)
│   │   └── synthetic_traffic.py        # Generador de clientes sintéticos
│   ├── api/                            # Capa de Exposición (FastAPI)
│   │   ├── router_scoring.py           # Endpoints de evaluación y simuladores
│   │   ├── router_dashboard.py         # Endpoints de KPIs y exportaciones
│   │   └── websocket_sim.py            # Streaming en vivo de la simulación
│   └── config.py                       # Configuración y parámetros BCRA
│
└── frontend/                           # FRONTEND (React / Vite / Tailwind CSS / Recharts / Lucide)
    ├── public/                         # Assets estáticos (logos SVG, fotos aspiracionales)
    └── src/
        ├── components/
        │   ├── common/                 # Reutilizables (Navbar, Footer, BrandLogo, ExportModal, DateRangePicker, RegisterModal, Toast)
        │   ├── public/                 # Portal Clientes (HeroBanner, LoanSimulator, CorporateSimulator, DepositSimulator, HighRiskInvestmentsTeaser, AboutSection)
        │   ├── client/                 # Home Banking Autenticado (ClientBalanceCard, TransferModal, DepositModal, FixedTermModal, TransactionsTable)
        │   └── employee/               # Portal Empleados (KpiGrid, BalanceDonutChart, AlmGapsBarChart, LiveRatesChart, ProfitProjectionsChart, OperationsTable, SimController)
        ├── pages/                      # Vistas (HomePage, ClientHomeBanking, LoanSimPage, DepositSimPage, EmployeeDashboard)
        ├── services/                   # apiClient.js (Axios/Fetch a FastAPI), simSocket.js (WebSocket /ws/simulacion)
        └── styles/                     # theme.css (Tokens de color: Azul #0F3A5D, Naranja #FF7A00, Bento Grid shadows)
```

---

## 8. Documentación Técnica Anexa
* [**`docs/normativa_encajes_bcra.md`**](docs/normativa_encajes_bcra.md): Regulación y alícuotas del Efectivo Mínimo BCRA.
* [**`docs/diagrama_logica_negocio_banco.md`**](docs/diagrama_logica_negocio_banco.md): Diagrama integral del funcionamiento del banco a nivel lógica de negocios.
* [**`docs/diagrama_usuarios_empresas_aml_bloqueos.md`**](docs/diagrama_usuarios_empresas_aml_bloqueos.md): Diagrama y protocolo de manejo de usuarios, empresas, AML y gestión de bloqueos (UIF).
* [**`docs/diagrama_plazos_fijos_flexibles_prestamos.md`**](docs/diagrama_plazos_fijos_flexibles_prestamos.md): Diagrama y lógica de manejo de plazos fijos, cuentas flexibles y préstamos amortizables.
* [**`docs/multiplicador_y_cashflow_prestable.md`**](docs/multiplicador_y_cashflow_prestable.md): Multiplicador monetario y fórmula del Cashflow Seguro Prestable.
* [**`docs/margen_financiero_y_proyecciones_escenarios.md`**](docs/margen_financiero_y_proyecciones_escenarios.md): Margen financiero neto, reinversión de ganancias y modelos proyectivos multi-escenario (Optimista, Base, Pesimista).
* [**`docs/proyecciones_inflacion_consultoras.md`**](docs/proyecciones_inflacion_consultoras.md): REM del BCRA, consultoras privadas y ajuste de tasas por inflación esperada.
* [**`docs/proyecciones_macro_actividad_economica.md`**](docs/proyecciones_macro_actividad_economica.md): EMAE, PBI proyectado y modelado de morosidad sistémica.
* [**`docs/compliance_aml_fraude_bajas.md`**](docs/compliance_aml_fraude_bajas.md): Políticas KYC/AML de la UIF, bloqueo preventivo y ciclo de vida de cuentas (Soft Delete).
* [**`docs/homebanking_ux_cuentas_sueldo.md`**](docs/homebanking_ux_cuentas_sueldo.md): Experiencia de Home Banking, simulación de Juan José ($3M), cuentas sueldo y cancelación anticipada de plazos fijos.
* [**`docs/seguridad_autenticacion_credenciales.md`**](docs/seguridad_autenticacion_credenciales.md): Seguridad bancaria, hashing Bcrypt/Argon2id, tokens JWT, roles RBAC y credenciales demo.
* [**`tests_unitarios/README.md`**](tests_unitarios/README.md): Plan de pruebas unitarias, casos de prueba para scoring, tesorería, compliance y simulación.
* [**`.agents/skills/code-architecture-standards/SKILL.md`**](.agents/skills/code-architecture-standards/SKILL.md): Estándares de desarrollo (límite de 500 líneas, nombres expresivos y catálogo de módulos).
