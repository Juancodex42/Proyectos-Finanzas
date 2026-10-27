# Home Banking Clientes: Especificación UX/UI, Cuentas Sueldo y Operatoria Realista

## 1. Visión de la Experiencia Autenticada (Cliente Particular)

A diferencia de un mock estático o fachada visual, el **Portal de Cliente Autenticado (Home Banking)** está conectado directamente con la base de datos **SQLite**. Cada acción que el usuario realiza (invertir a plazo fijo, solicitar un préstamo o transferir) modifica el libro contable de la entidad y se refleja de inmediato en la **Terminal de Gerencia/Empleados**.

---

## 2. Usuario Demo Inicial: "Juan José"

* **Nombre:** Juan José Gonzalez
* **DNI / CUIL:** `20-35123456-7` (`35123456`)
* **Localidad:** San Fernando del Valle de Catamarca
* **Tipo de Cuenta:** Caja de Ahorro / Cuenta Sueldo
* **Saldo Inicial Precargado:** **$3.000.000 (Tres millones de pesos)**
* **Condición Laboral:** Empleado en Relación de Dependencia
* **Sueldo Acreditado Mensual:** $3.000.000 (Se acredita automáticamente el día 1 de cada mes simulado)
* **CBU Asignado:** `0000003100012345678901` (22 dígitos bancarios)
* **Alias Bancario:** `JUAN.BANCO.VALLE`

---

## 3. Módulos y Flujos de Pantalla (UX/UI Fintech)

Inspirado en los estándares de usabilidad de las principales aplicaciones financieras (Mercado Pago, Ualá, Galicia, Brubank):

```
+-----------------------------------------------------------------+
|  BANCO DEL VALLE              Hola, Juan José 👋  [Cerrar Sesión]|
+-----------------------------------------------------------------+
|                                                                 |
|  SALDO DISPONIBLE EN CUENTA                                     |
|  $ 3.000.000,00                                                 |
|  📈 Rendimiento Flexible Activo: 28.5% TNA  (+$2.342,47 hoy)    |
|                                                                 |
|  [ 💸 Transferir ]   [ 📥 Ingresar / CBU ]   [ ⏱️ Plazo Fijo ]  |
|  [ 💳 Pedir Préstamo ]                       [ ⏩ Acelerar Sim ]|
|                                                                 |
|-----------------------------------------------------------------|
|  MIS INVERSIONES Y CRÉDITOS                                     |
|  - Plazo Fijo #104: $1.000.000 (Vence en 18 días)               |
|    [ Botón: Cancelar Plazo Fijo sin Intereses ]                 |
|  - Préstamo Activo: Cuota 3/24 ($48.200) - Estado: Al Día       |
|                                                                 |
|-----------------------------------------------------------------|
|  ÚLTIMOS MOVIMIENTOS                                            |
|  • Rendimiento Flexible Diario (+ $2.342,47)                    |
|  • Acreditación Sueldo Empleador (+ $3.000.000,00)                |
+-----------------------------------------------------------------+
```

---

## 4. Detalle Operativo de los Flujos de Acción

### A. Flujo "Transferir Dinero"
1. **Paso 1 (Ingreso de Datos):**
   * Input de Monto a transferir (con validación de no superar el saldo disponible).
   * Input de CBU / CVU (22 dígitos) o Alias de destino.
2. **Paso 2 (Pantalla de Confirmación):**
   * Diálogo modal de seguridad: *"¿Estás seguro que deseas transferir $X a [Destinatario]?"*.
3. **Paso 3 (Mensaje Realista de Simulación):**
   * Al hacer clic en "Confirmar Transferencia", la aplicación despliega un modal elegante de estado del sistema:  
     > ⚠️ **Mantenimiento del Sistema Nacional de Pagos:**  
     > *"La red interbancaria COELSA / BCRA se encuentra en ventana de mantenimiento programado. Tu saldo permanece intacto y seguro en tu cuenta."*

### B. Flujo "Depositar / Ingresar Dinero"
* Muestra la tarjeta de datos de la cuenta de Juan José:
  * **CBU:** `0000003100012345678901` con botón `[Copiar CBU]`.
  * **Alias:** `JUAN.BANCO.VALLE` con botón `[Copiar Alias]`.
* **Herramienta de Simulación para Testing:**
  * Botón interactivo: `[ + Simular Depósito de Prueba ]`.
  * Permite ingresar un monto ficticio (ej. $500.000) para inyectar saldo a la cuenta, creando el registro en `movimientos_cuenta` y actualizando el efectivo en caja del banco en tiempo real.

### C. Flujo "Plazo Fijo" y Opción de Cancelación Anticipada
1. **Constitución de Plazo Fijo:**
   * Juan José ingresa el monto a invertir (ej. $1.000.000) y selecciona el plazo (30, 60 o 90 días).
   * El sistema calcula los intereses ganados al vencimiento.
   * Al confirmar: Se descuenta el saldo de su cuenta transaccional y se inserta el registro en la tabla `plazos_fijos` de SQLite.
   * **Impacto en Gerencia:** Inmediatamente se incrementa el pasivo del banco y el Cashflow Prestable se recalcula en el Dashboard de Empleados.
2. **Regla de Cancelación Anticipada (Sin Ganancias):**
   * En la realidad bancaria argentina, los plazos fijos tradicionales con opción de cancelación anticipada (normativa BCRA) permiten al cliente rescatar su dinero antes del plazo pactado, pero **perdiendo la totalidad de los intereses ganados**.
   * Juan José cuenta con el botón **"Cancelar Plazo Fijo Anticipadamente"**:
     * Se reintegra el 100% del capital inicial a su cuenta transaccional.
     * Los intereses devengados pasan a `$0,00`.
     * El estado del plazo fijo en SQLite pasa a `'CANCELADO_ANTICIPADO'`.

### D. Rendimiento Flexible Diario Automático
* Todo dinero que Juan José mantenga en su cuenta genera intereses diarios automáticos al **28.5% TNA**.
* Con el botón de **"Acelerar Simulación (1s = 1d)"**, el usuario ve en pantalla cómo cada segundo transcurrido suma un nuevo movimiento de rendimiento acreditado a su saldo.

---

## 5. Estructura de Cuentas Sueldo en SQLite

En la base de datos se normaliza la condición de cuenta sueldo:
* **En `cuentas_transaccionales`:**
  * `es_cuenta_sueldo` (INTEGER DEFAULT 1): Flag que identifica si percibe haberes en la entidad.
* **En `personas`:**
  * `monto_sueldo_acreditado` (REAL): Valor del sueldo mensual acordado ($3.000.000).
  * `dia_cobro_sueldo` (INTEGER DEFAULT 1): Día del mes simulado en que se ejecuta la acreditación automática.
* **En `movimientos_cuenta`:**
  * Registro mensual con `tipo_movimiento = 'ACREDITACION_SUELDO'`.
