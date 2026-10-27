"""
Suite de Pruebas Unitarias para Validaciones Estrictas de Registro y Autenticación.
Verifica que las restricciones de seguridad bancaria rechacen entradas malformadas,
débiles o inválidas tanto en Pydantic schemas como en la capa de servicios y endpoints HTTP.
"""

import os
import tempfile
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from src.api.schemas import LoginRequest, RegistroPersonaRequest, RegistroEmpresaRequest
from src.database.connection import get_db_connection, init_db
from src.domain.models import CategoriaLaboral, RegistroPersonaDTO, RegistroEmpresaDTO, TipoSocietario
from src.main import app
from src.services.security_service import registrar_nueva_persona, registrar_nueva_empresa


@pytest.fixture
def service_db():
    """Crea una base de datos temporal con esquema y semillas para pruebas."""
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    init_db(db_path=tmp_path, seed_demo=True)
    conn = get_db_connection(tmp_path)

    yield conn, tmp_path

    conn.close()
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture(scope="module")
def api_client():
    """Cliente de pruebas HTTP FastAPI sobre base aislada."""
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    os.environ["BANCO_DB_PATH"] = tmp_path
    init_db(db_path=tmp_path, seed_demo=True)

    with TestClient(app) as client:
        yield client

    try:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    except OSError:
        pass


# ============================================================================
# 1. Pruebas de Esquemas Pydantic (Validación de Entrada)
# ============================================================================

def test_pydantic_registro_persona_password_demasiado_corta():
    with pytest.raises(ValidationError) as exc:
        RegistroPersonaRequest(
            dni="20-38111222-4",
            nombre_completo="Esteban Quito",
            email="esteban@valle.com",
            password="Pass1",  # Menos de 8 caracteres
        )
    assert "al menos 8 caracteres" in str(exc.value)


def test_pydantic_registro_persona_password_sin_numeros():
    with pytest.raises(ValidationError) as exc:
        RegistroPersonaRequest(
            dni="20-38111222-4",
            nombre_completo="Esteban Quito",
            email="esteban@valle.com",
            password="SoloLetrasMayusYMinus",
        )
    assert "letra y un número" in str(exc.value)


def test_pydantic_registro_persona_password_solo_numeros():
    with pytest.raises(ValidationError) as exc:
        RegistroPersonaRequest(
            dni="20-38111222-4",
            nombre_completo="Esteban Quito",
            email="esteban@valle.com",
            password="1234567890",
        )
    assert "letra y un número" in str(exc.value)


def test_pydantic_registro_persona_email_invalido():
    with pytest.raises(ValidationError) as exc:
        RegistroPersonaRequest(
            dni="20-38111222-4",
            nombre_completo="Esteban Quito",
            email="correo_invalido_sin_arroba",
            password="Password123!",
        )
    assert "correo electrónico" in str(exc.value)


def test_pydantic_registro_persona_dni_invalido():
    with pytest.raises(ValidationError) as exc:
        RegistroPersonaRequest(
            dni="123",  # Demasiado corto
            nombre_completo="Esteban Quito",
            email="esteban@valle.com",
            password="Password123!",
        )
    assert "DNI" in str(exc.value)


def test_pydantic_registro_persona_nombre_corto():
    with pytest.raises(ValidationError) as exc:
        RegistroPersonaRequest(
            dni="20-38111222-4",
            nombre_completo="  A  ",  # Longitud < 3 tras strip
            email="esteban@valle.com",
            password="Password123!",
        )
    assert "nombre completo" in str(exc.value)


def test_pydantic_registro_empresa_cuit_invalido():
    with pytest.raises(ValidationError) as exc:
        RegistroEmpresaRequest(
            cuit="30-12345",  # CUIT no tiene 11 dígitos
            razon_social="Servicios Mineros SRL",
            email="empresa@mineria.com",
            password="Password123!",
        )
    assert "CUIT" in str(exc.value)


def test_pydantic_registro_empresa_razon_social_corta():
    with pytest.raises(ValidationError) as exc:
        RegistroEmpresaRequest(
            cuit="30-71234567-8",
            razon_social="X",
            email="empresa@mineria.com",
            password="Password123!",
        )
    assert "razón social" in str(exc.value)


def test_pydantic_login_identificador_vacio():
    with pytest.raises(ValidationError) as exc:
        LoginRequest(identificador="   ", password="ValidPassword123")
    assert "identificador" in str(exc.value)


# ============================================================================
# 2. Pruebas de la Capa de Servicios (security_service)
# ============================================================================

def test_service_registro_persona_rechaza_password_debil(service_db):
    conn, _ = service_db
    dto = RegistroPersonaDTO(
        dni="20-40111222-3",
        nombre_completo="Santiago del Valle",
        email="santiago@valle.com",
        password="123",  # Débil
        categoria_laboral=CategoriaLaboral.EMPLEADO_PRIVADO,
        antiguedad_laboral_meses=12,
        ingreso_mensual_estimado=1500000.0,
    )
    res = registrar_nueva_persona(conn, dto)
    assert res.exito is False
    assert "contraseña" in res.mensaje.lower()


def test_service_registro_persona_rechaza_email_invalido(service_db):
    conn, _ = service_db
    dto = RegistroPersonaDTO(
        dni="20-40111222-3",
        nombre_completo="Santiago del Valle",
        email="santiago_sin_arroba",
        password="Password123!",
        categoria_laboral=CategoriaLaboral.EMPLEADO_PRIVADO,
        antiguedad_laboral_meses=12,
        ingreso_mensual_estimado=1500000.0,
    )
    res = registrar_nueva_persona(conn, dto)
    assert res.exito is False
    assert "correo electrónico" in res.mensaje.lower()


def test_service_registro_empresa_rechaza_cuit_invalido(service_db):
    conn, _ = service_db
    dto = RegistroEmpresaDTO(
        cuit="30-123",
        razon_social="Constructora Catamarca SA",
        tipo_societario=TipoSocietario.SA,
        rubro_actividad="Construcción",
        email="contacto@constructora.com",
        password="Password123!",
        facturacion_anual_estimada=50000000.0,
    )
    res = registrar_nueva_empresa(conn, dto)
    assert res.exito is False
    assert "cuit" in res.mensaje.lower()


# ============================================================================
# 3. Pruebas de Endpoints HTTP REST (Integración FastAPI)
# ============================================================================

def test_api_registro_persona_rechaza_email_malformado(api_client):
    payload = {
        "dni": "20-41555666-9",
        "nombre_completo": "Lucia Fernandez",
        "email": "lucia_invalida_sin_dominio",
        "password": "Password123!",
    }
    response = api_client.post("/api/clientes/registro-persona", json=payload)
    assert response.status_code == 422


def test_api_registro_persona_rechaza_password_corta(api_client):
    payload = {
        "dni": "20-41555666-9",
        "nombre_completo": "Lucia Fernandez",
        "email": "lucia@valle.com",
        "password": "123",
    }
    response = api_client.post("/api/clientes/registro-persona", json=payload)
    assert response.status_code == 422


def test_api_registro_persona_exitoso(api_client):
    payload = {
        "dni": "20-41555666-9",
        "nombre_completo": "Lucia Fernandez",
        "email": "lucia.fernandez@valle.com.ar",
        "password": "Password123!",
        "categoria_laboral": "EMPLEADO_PUBLICO",
        "antiguedad_laboral_meses": 24,
        "ingreso_mensual_comprobado": 2800000,
        "es_cuenta_sueldo": True,
        "monto_sueldo_acreditado": 2800000,
    }
    response = api_client.post("/api/clientes/registro-persona", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["cbu"]) == 22
    assert "token" in data
    assert data["usuario"]["rol"] == "CLIENTE"
