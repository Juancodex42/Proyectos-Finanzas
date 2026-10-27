"""
Suite de Pruebas de Integración para Endpoints HTTP REST y WebSockets.
Valida con TestClient la autenticación, simuladores, transferencias y descargas.
Referencia de diseño: docs/diagrama_logica_negocio_banco.md
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from src.database.connection import get_db_connection, init_db
from src.main import app


@pytest.fixture(scope="module")
def api_client():
    """Inicializa la aplicación FastAPI y cliente de pruebas sobre base aislada."""
    tmp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()

    # Sobrescribir temporalmente la ruta de base de datos
    os.environ["BANCO_DB_PATH"] = tmp_path
    init_db(db_path=tmp_path, seed_demo=True)

    with TestClient(app) as client:
        yield client

    try:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    except OSError:
        pass


def test_health_check_root(api_client):
    """Valida que el endpoint raíz responda ONLINE con estado 200 OK."""
    response = api_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["estado"] == "ONLINE"
    assert "Banco del Valle" in data["entidad"]


def test_simular_prestamo_endpoint(api_client):
    """Valida la cotización francesa de $1.000.000 a 12 meses."""
    payload = {
        "monto_capital": 1000000.0,
        "cantidad_cuotas": 12,
        "ingreso_mensual": 3000000.0,
        "categoria_laboral": "EMPLEADO_PRIVADO",
        "score_externo": 720,
        "peor_situacion_bcra": 1,
        "antiguedad_meses": 24,
    }
    response = api_client.post("/api/scoring/simular-prestamo", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["cuota_mensual"] > 0
    assert data["pre_aprobado"] is True
    assert len(data["cronograma"]) == 12
    assert data["supera_tope_35_porciento"] is False


def test_simular_empresa_endpoint(api_client):
    """Valida la cotización para una PyME con CUIT y facturación anual."""
    payload = {
        "monto_capital": 5000000.0,
        "cantidad_cuotas": 24,
        "facturacion_anual": 80000000.0,
        "tipo_societario": "SRL",
        "score_externo": 700,
        "peor_situacion_bcra": 1,
    }
    response = api_client.post("/api/scoring/simular-empresa", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["pre_aprobado"] is True
    assert "cuota_mensual" in data


def test_simular_deposito_comparador(api_client):
    """Valida la comparación paralela entre Plazo Fijo y Cuenta Flexible."""
    payload = {"monto": 1000000.0, "plazo_dias": 30}
    response = api_client.post("/api/scoring/simular-deposito", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["plazo_fijo"]["intereses_generados"] > 0
    assert data["cuenta_flexible"]["ganancia_diaria"] > 0


def test_auth_login_juan_jose_y_resumen(api_client):
    """Valida el inicio de sesión y la consulta autenticada del saldo de $3M de Juan José."""
    login_payload = {"identificador": "35123456", "password": "Valle1234!"}
    res_login = api_client.post("/api/auth/login", json=login_payload)
    assert res_login.status_code == 200
    token = res_login.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}
    res_resumen = api_client.get("/api/client/resumen", headers=headers)
    assert res_resumen.status_code == 200
    datos = res_resumen.json()
    assert "Juan José" in datos["titular"]
    assert datos["saldo_actual"] == 3000000.0
    assert datos["alias"] == "JUAN.BANCO.VALLE"
    assert datos["rendimiento_diario_estimado"] == pytest.approx(2342.47, abs=0.5)


def test_transferencia_entre_cuentas(api_client):
    """Valida el débito y crédito inmediato entre cuentas internas del banco."""
    # Login Juan José
    res_login = api_client.post("/api/auth/login", json={"identificador": "35123456", "password": "Valle1234!"})
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    transf_payload = {
        "cbu_o_alias_destino": "CATAMARCA.MINERIA",
        "monto": 50000.0,
        "concepto": "PAGO_PROVEEDORES",
    }
    res_transf = api_client.post("/api/client/transferir", json=transf_payload, headers=headers)
    assert res_transf.status_code == 200
    assert res_transf.json()["exito"] is True
    assert res_transf.json()["nuevo_saldo"] == 2950000.0


def test_constituir_plazo_fijo_cliente(api_client):
    """Valida la imposición de un plazo fijo por parte de Juan José."""
    res_login = api_client.post("/api/auth/login", json={"identificador": "35123456", "password": "Valle1234!"})
    token = res_login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    pf_payload = {"monto": 200000.0, "plazo_dias": 30}
    res_pf = api_client.post("/api/client/constituir-plazo-fijo", json=pf_payload, headers=headers)
    assert res_pf.status_code == 200
    assert res_pf.json()["exito"] is True
    assert res_pf.json()["plazo_fijo_id"] > 0


def test_dashboard_kpis_y_rates(api_client):
    """Valida las métricas gerenciales de patrimonio neto y encajes."""
    res_kpis = api_client.get("/api/dashboard/kpis")
    assert res_kpis.status_code == 200
    kpis = res_kpis.json()
    assert kpis["capital_propio_patrimonio"] == 50000000.0
    assert kpis["encaje_obligatorio_bcra"] > 0

    res_rates = api_client.get("/api/dashboard/live-rates")
    assert res_rates.status_code == 200
    assert "spread_porcentaje" in res_rates.json()


def test_dashboard_exportar_reportes(api_client):
    """Valida la descarga de reportes en PDF y CSV desde el dashboard."""
    res_pdf = api_client.get("/api/dashboard/exportar?tipo=balance&formato=pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF")

    res_csv = api_client.get("/api/dashboard/exportar?tipo=balance&formato=csv")
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"] == "text/csv; charset=utf-8"


def test_websocket_simulacion_connection_and_advance(api_client):
    """Valida el handshake WebSocket y la recepción del evento inicial y tick diario."""
    with api_client.websocket_connect("/ws/simulacion") as websocket:
        msg_inicial = websocket.receive_json()
        assert msg_inicial["tipo"] == "ESTADO_INICIAL"

        # Enviar comando de avanzar un día
        websocket.send_json({"action": "advance_day"})
        msg_tick = websocket.receive_json()
        assert msg_tick["tipo"] == "TICK"
        assert "fecha_simulada" in msg_tick
        assert "balance" in msg_tick
