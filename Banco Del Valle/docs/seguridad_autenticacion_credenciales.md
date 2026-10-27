# Seguridad, Autenticación y Gestión de Credenciales Bancarias

## 1. Mecanismos de Seguridad y Criptografía

El sistema implementa estándares de seguridad bancaria y de la industria financiera (OWASP Top 10, BCRA Com. "A" 6879 sobre seguridad en canales electrónicos):

### A. Hashing de Contraseñas (Argon2id / Bcrypt)
* **Prohibición de Texto Plano:** Las contraseñas nunca se almacenan en texto legible ni con funciones hash vulnerables (MD5, SHA-1 o SHA-256 sin salting).
* **Algoritmo:** Se utiliza **Bcrypt** con factor de coste de trabajo `cost = 12` (o **Argon2id**, estándar ganador del *Password Hashing Competition*):
  * Genera una sal criptográfica aleatoria (*salt*) única por cada usuario.
  * Ralentiza deliberadamente los ataques de fuerza bruta por GPU o tablas arcoíris (*rainbow tables*).

### B. Gestión de Sesiones y Tokens de Acceso (JWT)
* **Protocolo:** Tokens de autenticación basados en **JWT (JSON Web Tokens)** firmados con clave secreta criptográfica (algoritmo `HS256`):
  * **Payload del Token:** Contiene `sub` (ID de usuario), `rol` ('CLIENTE', 'EMPLEADO', 'GERENTE') y `exp` (expiración a 30 minutos).
* **Almacenamiento Seguro:** En navegadores web, los tokens se transmiten en cabeceras `Authorization: Bearer <token>` o cookies con flags `HttpOnly`, `SameSite=Strict` y `Secure` para prevenir ataques de Cross-Site Scripting (XSS) y CSRF.

### C. Control de Acceso Basado en Roles (RBAC - Role-Based Access Control)
El sistema implementa 3 roles fundamentales en base de datos y tokens (`rol`):
* **`CLIENTE`:** Autorizado únicamente para consultar su propia información (saldo, movimientos, préstamos) y operar en su Home Banking (vía vinculación con `persona_id` o `empresa_id`). Si intenta invocar endpoints gerenciales (`/api/dashboard/*`), la API responde con `403 Forbidden`.
* **`EMPLEADO`:** Acceso operativo a la cartera de clientes, estados de mora, cobranzas y consultas de scoring Veraz.
* **`GERENTE`:** Acceso total al dashboard de métricas patrimoniales, proyecciones multi-escenario, auditoría UIF y **control maestro del reloj de simulación**.

### D. Protección contra Ataques de Fuerza Bruta
* **Contador de Intentos Fallidos:** Si un usuario ingresa una contraseña incorrecta 5 veces consecutivas:
  * El sistema bloquea temporalmente el inicio de sesión durante **15 minutos** (`bloqueado_hasta = CURRENT_TIMESTAMP + 15 min`).
  * Se registra el incidente en la tabla `auditoria_accesos`.

---

## 2. Esquema de Base de Datos para Credenciales y Accesos

Las credenciales residen en la misma base de datos unificada SQLite (`banco_scoring.db`) dentro de tablas protegidas:

```sql
-- Tabla de Credenciales de Usuarios
CREATE TABLE usuarios_credenciales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id INTEGER NULL,              -- FK a personas si es individuo
    empresa_id INTEGER NULL,              -- FK a empresas si es corporativo
    identificador TEXT UNIQUE NOT NULL,   -- DNI, CUIT o Legajo/Email de empleado
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,          -- Hash seguro generado por bcrypt
    rol TEXT NOT NULL,                    -- 'CLIENTE', 'EMPLEADO', 'GERENTE'
    intentos_fallidos INTEGER DEFAULT 0,
    bloqueado_hasta TEXT NULL,            -- Timestamp si fue bloqueado por fuerza bruta
    ultimo_login TEXT NULL,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY (persona_id) REFERENCES personas(id),
    FOREIGN KEY (empresa_id) REFERENCES empresas(id)
);

-- Tabla de Auditoría de Accesos
CREATE TABLE auditoria_accesos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    fecha_hora TEXT NOT NULL,
    direccion_ip TEXT,
    exitoso INTEGER NOT NULL,            -- 1 = Login OK, 0 = Fallido
    motivo_falla TEXT NULL,              -- 'PASSWORD_INCORRECTA', 'CUENTA_BLOQUEADA'
    FOREIGN KEY (usuario_id) REFERENCES usuarios_credenciales(id)
);
```

---

## 3. Credenciales Precargadas para la Simulación / Demo

Para facilitar las pruebas del evaluador en la interfaz web, el sistema cuenta con dos perfiles demo preconfigurados con acceso de 1 clic:

| Perfil de Acceso | Identificador / Usuario | Contraseña Demo | Rol y Permisos |
| :--- | :--- | :--- | :--- |
| **Cliente Demo (Home Banking)** | `35123456` (DNI Juan José Gonzalez) | `Valle1234!` | **`CLIENTE`**: Acceso al saldo de $3.000.000, transferencias, plazos fijos y cancelación anticipada. |
| **Gerencia / Dueño (Terminal Ejecutiva)** | `gerencia@bancodelvalle.com.ar` | `admin2026` | **`GERENTE`**: Acceso a balances, encajes BCRA, proyecciones multi-escenario y **botón maestro de aceleración del tiempo**. |
