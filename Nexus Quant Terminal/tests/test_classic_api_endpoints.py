import pytest
import json
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

class TestClassicApiEndpoints:
    def test_six_bullets_campaign_endpoint(self, client):
        res = client.post('/api/campaign/six-bullets', json={
            'pair': 'BTCUSDT',
            'interval': '4h',
            'strategy': 'volatility_squeeze',
            'sl_atr': 1.5,
            'tp_atr': 3.5,
            'bullet_risk': 33.3333
        })
        assert res.status_code == 200
        data = res.get_json()
        assert 'trades' in data
        assert 'summary' in data

    def test_download_csv_endpoint(self, client):
        sample_trades = [
            {
                'entry_time': 1700000000,
                'direction': 'LONG',
                'entry_price': 50000.0,
                'sl_price': 49000.0,
                'tp_price': 53000.0,
                'exit_price': 53000.0,
                'duration': 5,
                'r_multiple': 3.0,
                'pnl': 100.0,
                'exit_reason': 'TP',
                'fee': 0.05
            }
        ]
        res = client.post('/api/download/csv', json={
            'trades': sample_trades,
            'pair': 'BTCUSDT',
            'strategy': 'EMA_Cross',
            'interval': '4h'
        })
        assert res.status_code == 200
        assert res.mimetype == 'text/csv'
        assert b'Stop_Loss' in res.data
        assert b'Take_Profit' in res.data
        cd = res.headers.get('Content-Disposition', '')
        assert 'Nexus_Trades_EMA_Cross_BTCUSDT_4h_' in cd
        assert cd.endswith('.csv')

    def test_download_pdf_endpoint(self, client):
        res = client.post('/api/download/pdf', json={
            'summary': {'profit_factor': 1.85, 'net_pnl': 350.0, 'win_rate': 0.45},
            'trades': [{'entry_time': 1700000000, 'direction': 'LONG', 'entry_price': 2000.0, 'exit_price': 2100.0, 'pnl': 100.0}],
            'pair': 'ETHUSDT',
            'interval': '4h',
            'strategy': 'Volatility Squeeze'
        })
        assert res.status_code == 200
        assert b'NEXUS QUANT TERMINAL' in res.data
        assert b'Reporte de Desempe' in res.data
        assert b'Periodo Auditado' in res.data
        cd = res.headers.get('Content-Disposition', '')
        assert 'Nexus_Report_Volatility_Squeeze_ETHUSDT_4h_' in cd
        assert cd.endswith('.html')
