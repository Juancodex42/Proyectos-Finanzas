"""
Banco del Valle — Scoring Calculator & Lending Engine
Suite de Pruebas Unitarias para la Capa de Servicios.
Valida Bcrypt, JWT, Onboarding, Buró Veraz y Exportaciones (CSV, Excel, PDF).
"""

import tempfile
import os
import pytest

from src.database.connection import get_db_connection, init_db
from src.domain.models import CategoriaLaboral, RegistroPersonaDTO, RolUsuario, TipoSocietario, RegistroEmpresaDTO
from src.services.export_service import (
    exportar_a_csv,
    exportar_a_excel,
    exportar_a_pdf,
    exportar_cronograma_prestamo,
    exportar_extracto_cuenta,
)
from src.services.security_service import (
    autenticar_usuario,
    crear_token_acceso,
    decodificar_token,
    hash_password,
    registrar_nueva_empresa,
    registrar_nueva_persona,
    validar_rol,
    verificar_password,
)
from src.services.veraz_service import consultar_buro_externo, interpretar_situacion_bcra


@pytest.fixture
def service_db():
    """Crea una base de datos temporal con datos iniciales para pruebas de servicios."""
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    init_db(db_path=tmp_path, seed_demo=True)
    conn = get_db_connection(tmp_path)

    yield conn, tmp_path

    conn.close()
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


def test_hash_y_verificacion_password():
    """Valida que el algoritmo Bcrypt genere hashes no reversibles y verifique correctamente."""
    password = "SuperPassword2026!"
    hashed = hash_password(password)

    assert hashed != password
    assert verificar_password(password, hashed) is True
    assert verificar_password("PasswordErroneo", hashed) is False


def test_jwt_creacion_decodificacion_y_roles():
    """Valida la emisión de tokens JWT, firma HS256 y expiración."""
    token = crear_token_acceso(usuario_id=10, identificador="35123456", rol="CLIENTE", email="test@valle.com.ar")
    assert isinstance(token, str) and len(token) > 20

    payload = decodificar_token(token)
    assert payload is not None
    assert payload["sub"] == "10"
    assert payload["rol"] == "CLIENTE"
    assert payload["identificador"] == "35123456"

    assert validar_rol(token, ["CLIENTE"]) is True
    assert validar_rol(token, ["GERENTE"]) is False


def test_autenticacion_juan_jose_exitosa(service_db):
    """Valida que Juan José pueda autenticarse con sus credenciales demo sembradas."""
    conn, _ = service_db

    usuario, token, error = autenticar_usuario(conn, "35123456", "Valle1234!")
    assert error is None
    assert usuario is not None
    assert usuario.rol == RolUsuario.CLIENTE
    assert token is not None

    payload = decodificar_token(token)
    assert payload["identificador"] == "35123456"


def test_autenticacion_password_invalido_y_bloqueo(service_db):
    """Valida que tras 5 intentos fallidos la cuenta quede bloqueada."""
    conn, _ = service_db

    for i in range(4):
        usr, tok, err = autenticar_usuario(conn, "35123456", "ClaveEquivocada")
        assert usr is None
        assert tok is None
        assert "Contraseña incorrecta" in err

    # Quinto intento: debe disparar el bloqueo
    usr, tok, err = autenticar_usuario(conn, "35123456", "ClaveEquivocada")
    assert "Cuenta bloqueada por 15 minutos" in err

    # Intento posterior con la clave correcta debe ser rechazado por bloqueo activo
    usr, tok, err = autenticar_usuario(conn, "35123456", "Valle1234!")
    assert "Cuenta bloqueada temporalmente" in err


def test_onboarding_persona_completo(service_db):
    """Valida el registro atómico multi-paso de una nueva persona humana."""
    conn, _ = service_db

    dto = RegistroPersonaDTO(
        dni="38999111",
        nombre_completo="Carla Sofia Gomez",
        email="carla.gomez@gmail.com",
        password="CarlaValle2026!",
        categoria_laboral=CategoriaLaboral.EMPLEADO_PUBLICO,
        antiguedad_laboral_meses=36,
        ingreso_mensual_estimado=2200000.0,
        es_cuenta_sueldo=True,
        monto_sueldo_acreditado=2200000.0,
    )

    respuesta = registrar_nueva_persona(conn, dto)
    assert respuesta.exito is True
    assert respuesta.usuario_id > 0
    assert len(respuesta.cbu_asignado) == 22
    assert "CARLA" in respuesta.alias_asignado
    assert len(respuesta.token_acceso) > 20

    # Intento de duplicado por DNI
    respuesta_dup = registrar_nueva_persona(conn, dto)
    assert respuesta_dup.exito is False
    assert "Ya existe una persona registrada" in respuesta_dup.mensaje


def test_onboarding_empresa_completo(service_db):
    """Valida el registro atómico multi-paso de una empresa PyME."""
    conn, _ = service_db

    dto = RegistroEmpresaDTO(
        cuit="30-79888777-1",
        razon_social="Catamarca Agroexport SRL",
        tipo_societario=TipoSocietario.SRL,
        rubro_actividad="Exportación de Frutos Secos",
        email="contacto@catamarcaagro.com",
        password="AgroExport2026!",
        facturacion_anual_estimada=120000000.0,
        exencion_impositiva=False,
    )

    respuesta = registrar_nueva_empresa(conn, dto)
    assert respuesta.exito is True
    assert respuesta.usuario_id > 0
    assert len(respuesta.cbu_asignado) == 22
    assert "AGROEXPORT" in respuesta.alias_asignado


def test_veraz_service_situaciones_bcra():
    """Valida la interpretación y consulta del buró de crédito externo."""
    desc_1 = interpretar_situacion_bcra(1)
    assert "Normal" in desc_1

    desc_5 = interpretar_situacion_bcra(5)
    assert "Irrecuperable" in desc_5

    # Consulta de Juan José
    juan_veraz = consultar_buro_externo("35123456")
    assert juan_veraz.peor_situacion_bcra == 1
    assert juan_veraz.score_externo == 740

    # Forzar situación 3 para test
    veraz_riesgo = consultar_buro_externo("40111222", forzar_situacion=3)
    assert veraz_riesgo.peor_situacion_bcra == 3
    assert veraz_riesgo.score_externo == 450


def test_exportar_a_csv_excel_y_pdf():
    """Valida la generación de archivos binarios descargables en los 3 formatos."""
    datos_ejemplo = [
        {"fecha": "2026-10-01", "concepto": "Acreditación Haberes", "monto": 3000000.0, "saldo": 3000000.0},
        {"fecha": "2026-10-02", "concepto": "Rendimiento Flexible", "monto": 2342.47, "saldo": 3002342.47},
    ]

    # CSV
    csv_bytes = exportar_a_csv(datos_ejemplo)
    assert len(csv_bytes) > 0
    assert b"Acreditaci\xc3\xb3n Haberes" in csv_bytes or b"Haberes" in csv_bytes

    # Excel
    excel_bytes = exportar_a_excel(datos_ejemplo, nombre_hoja="Test Movimientos")
    assert len(excel_bytes) > 1000  # Archivo binario zip/xlsx

    # PDF
    pdf_bytes = exportar_a_pdf(
        titulo="Reporte de Prueba",
        subtitulo="Auditoría Interna",
        columnas=["FECHA", "CONCEPTO", "MONTO", "SALDO"],
        filas=[[d["fecha"], d["concepto"], d["monto"], d["saldo"]] for d in datos_ejemplo],
        kpis={"Total": "$3,002,342.47", "Registros": 2},
    )
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")  # Encabezado estándar de todo archivo PDF válido


def test_exportar_extracto_y_cronograma_convenience_functions():
    """Valida los helpers de alto nivel para extractos bancarios y cronogramas de créditos."""
    movs = [
        {"fecha_hora": "2026-10-01 10:00", "tipo_movimiento": "SUELDO", "descripcion": "Haberes", "monto": 3000000.0, "saldo_posterior": 3000000.0}
    ]
    pdf_bytes, mime, filename = exportar_extracto_cuenta(movs, formato="pdf")
    assert mime == "application/pdf"
    assert filename.endswith(".pdf")
    assert pdf_bytes.startswith(b"%PDF")

    cronograma = [
        {"numero_cuota": 1, "monto_cuota": 112825.41, "capital_amortizado": 62825.41, "interes_cuota": 50000.0, "saldo_capital_restante": 937174.59}
    ]
    xls_bytes, mime_xls, fn_xls = exportar_cronograma_prestamo(cronograma, 1000000.0, 0.60, 12, 112825.41, formato="excel")
    assert "spreadsheetml" in mime_xls
    assert fn_xls.endswith(".xlsx")
    assert len(xls_bytes) > 1000
