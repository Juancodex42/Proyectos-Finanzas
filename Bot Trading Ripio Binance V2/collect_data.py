"""
Recolector asíncrono de cotizaciones y spreads históricos de Ripio Trade.
Captura snapshots periódicos en CSV para backtesting y análisis de cointegración.
Referencia de diseño: docs/DATA_COLLECTION.md
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Union
import csv

ROOT_DIR = Path(__file__).resolve().parent

# Add src to path
sys.path.insert(0, str(ROOT_DIR / 'src'))

from core.ripio_api import ProfessionalRipioAPI

# Setup logging
log_dir = ROOT_DIR / 'data' / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_dir / 'data_collector.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Recolecta precios de Ripio cada N minutos
    """

    def __init__(self, api_token: str, secret_key: str, output_dir: Optional[Union[str, Path]] = None):
        self.ripio = ProfessionalRipioAPI(api_token, secret_key)
        self.output_dir = Path(output_dir) if output_dir else ROOT_DIR / 'data' / 'historical'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Pares a recolectar
        self.pairs = ['USDT_ARS', 'USDC_ARS']

        # Estado
        self.data_points = 0
        self.errors = 0

        logger.info("[COLLECTOR] Data Collector initialized")
        logger.info(f"[COLLECTOR] Output directory: {self.output_dir}")
        logger.info(f"[COLLECTOR] Pairs: {', '.join(self.pairs)}")

    async def initialize(self):
        """Inicializa conexión con Ripio API"""
        await self.ripio.init_session()

        # Health check
        health = await self.ripio.health_check()
        if not health:
            raise Exception("Ripio API no responde")

        logger.info("[COLLECTOR] Connected to Ripio API")

    async def collect_snapshot(self) -> dict:
        """
        Recolecta snapshot de precios actuales

        Returns:
            Dict con precios por par
        """
        snapshot = {
            'timestamp': datetime.now().isoformat(),
        }

        for pair in self.pairs:
            try:
                # Obtener ticker
                ticker = await self.ripio.get_ticker(pair)

                if ticker:
                    # Calcular mid price
                    mid = (ticker['bid'] + ticker['ask']) / 2

                    snapshot[f'{pair}_bid'] = ticker['bid']
                    snapshot[f'{pair}_ask'] = ticker['ask']
                    snapshot[f'{pair}_mid'] = mid
                    snapshot[f'{pair}_spread'] = ticker['ask'] - ticker['bid']
                else:
                    logger.warning(f"[COLLECTOR] No ticker for {pair}")
                    snapshot[f'{pair}_bid'] = None
                    snapshot[f'{pair}_ask'] = None
                    snapshot[f'{pair}_mid'] = None
                    snapshot[f'{pair}_spread'] = None

            except Exception as e:
                logger.error(f"[COLLECTOR] Error collecting {pair}: {e}")
                self.errors += 1
                snapshot[f'{pair}_bid'] = None
                snapshot[f'{pair}_ask'] = None
                snapshot[f'{pair}_mid'] = None
                snapshot[f'{pair}_spread'] = None

        return snapshot

    def save_snapshot(self, snapshot: dict, filename: str = None):
        """
        Guarda snapshot en CSV

        Args:
            snapshot: Dict con datos
            filename: Nombre del archivo (default: ripio_YYYY-MM-DD.csv)
        """
        if filename is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filename = f'ripio_{date_str}.csv'

        filepath = self.output_dir / filename

        # Determinar si archivo existe (para headers)
        file_exists = filepath.exists()

        try:
            with open(filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=snapshot.keys())

                # Escribir headers si es nuevo
                if not file_exists:
                    writer.writeheader()
                    logger.info(f"[COLLECTOR] Created new file: {filename}")

                # Escribir datos
                writer.writerow(snapshot)

                self.data_points += 1

        except Exception as e:
            logger.error(f"[COLLECTOR] Error saving snapshot: {e}")
            self.errors += 1

    async def run(self, duration_days: int = 30, interval_minutes: int = 5):
        """
        Ejecuta recolección por N días

        Args:
            duration_days: Días a recolectar
            interval_minutes: Minutos entre recolecciones
        """
        logger.info("="*60)
        logger.info("[COLLECTOR] Starting data collection")
        logger.info(f"[COLLECTOR] Duration: {duration_days} days")
        logger.info(f"[COLLECTOR] Interval: {interval_minutes} minutes")
        logger.info(f"[COLLECTOR] Expected data points: {(duration_days * 24 * 60) // interval_minutes}")
        logger.info("="*60)

        # Calcular iteraciones totales
        total_iterations = (duration_days * 24 * 60) // interval_minutes
        iteration = 0

        try:
            while iteration < total_iterations:
                iteration += 1

                # Recolectar snapshot
                logger.info(f"[COLLECTOR] Iteration {iteration}/{total_iterations}")
                snapshot = await self.collect_snapshot()

                # Mostrar precios
                if snapshot.get('USDT_ARS_mid') and snapshot.get('USDC_ARS_mid'):
                    usdt = snapshot['USDT_ARS_mid']
                    usdc = snapshot['USDC_ARS_mid']
                    ratio = usdt / usdc if usdc > 0 else 0
                    logger.info(f"[PRICES] USDT: {usdt:.2f}, USDC: {usdc:.2f}, Ratio: {ratio:.6f}")

                # Guardar
                self.save_snapshot(snapshot)

                # Stats cada 100 iteraciones
                if iteration % 100 == 0:
                    logger.info(f"[STATS] Data points: {self.data_points}, Errors: {self.errors}")
                    logger.info(f"[PROGRESS] {(iteration/total_iterations)*100:.1f}% complete")

                # Esperar intervalo
                await asyncio.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("[COLLECTOR] Interrupted by user")

        except Exception as e:
            logger.error(f"[COLLECTOR] Error: {e}")

        finally:
            # Stats finales
            logger.info("="*60)
            logger.info("[COLLECTOR] Collection finished")
            total_ops = self.data_points + self.errors
            success_rate = (self.data_points / total_ops) * 100.0 if total_ops > 0 else 0.0
            logger.info(f"[STATS] Total data points: {self.data_points}")
            logger.info(f"[STATS] Total errors: {self.errors}")
            logger.info(f"[STATS] Success rate: {success_rate:.1f}%")
            logger.info("="*60)

            # Cerrar sesión
            await self.ripio.close_session()

    async def run_continuous(self, interval_minutes: int = 5):
        """
        Ejecuta recolección continua (sin límite de tiempo)

        Útil para dejar corriendo indefinidamente

        Args:
            interval_minutes: Minutos entre recolecciones
        """
        logger.info("="*60)
        logger.info("[COLLECTOR] Starting CONTINUOUS data collection")
        logger.info(f"[COLLECTOR] Interval: {interval_minutes} minutes")
        logger.info("[COLLECTOR] Press Ctrl+C to stop")
        logger.info("="*60)

        iteration = 0

        try:
            while True:
                iteration += 1

                # Recolectar snapshot
                logger.info(f"[COLLECTOR] Iteration {iteration}")
                snapshot = await self.collect_snapshot()

                # Mostrar precios
                if snapshot.get('USDT_ARS_mid') and snapshot.get('USDC_ARS_mid'):
                    usdt = snapshot['USDT_ARS_mid']
                    usdc = snapshot['USDC_ARS_mid']
                    ratio = usdt / usdc if usdc > 0 else 0
                    logger.info(f"[PRICES] USDT: {usdt:.2f}, USDC: {usdc:.2f}, Ratio: {ratio:.6f}")

                # Guardar
                self.save_snapshot(snapshot)

                # Stats cada 100 iteraciones
                if iteration % 100 == 0:
                    logger.info(f"[STATS] Data points: {self.data_points}, Errors: {self.errors}")

                # Esperar intervalo
                await asyncio.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("[COLLECTOR] Interrupted by user")

        except Exception as e:
            logger.error(f"[COLLECTOR] Error: {e}")

        finally:
            # Stats finales
            logger.info("="*60)
            logger.info("[COLLECTOR] Collection stopped")
            logger.info(f"[STATS] Total data points: {self.data_points}")
            logger.info(f"[STATS] Total errors: {self.errors}")
            logger.info("="*60)

            # Cerrar sesión
            await self.ripio.close_session()


async def main():
    parser = argparse.ArgumentParser(description='Ripio Data Collector')

    parser.add_argument(
        '--mode',
        choices=['timed', 'continuous'],
        default='continuous',
        help='Collection mode'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Days to collect (only for timed mode)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Minutes between collections'
    )

    parser.add_argument(
        '--api-token',
        type=str,
        help='Ripio API token (or set RIPIO_API_TOKEN env)'
    )

    parser.add_argument(
        '--secret-key',
        type=str,
        help='Ripio secret key (or set RIPIO_SECRET_KEY env)'
    )

    args = parser.parse_args()

    # Obtener credenciales
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_token = args.api_token or os.getenv('RIPIO_API_TOKEN')
    secret_key = args.secret_key or os.getenv('RIPIO_SECRET_KEY')

    if not api_token or not secret_key:
        logger.error("Error: API credentials not provided")
        logger.error("Use --api-token and --secret-key or set RIPIO_API_TOKEN and RIPIO_SECRET_KEY env vars")
        return

    # Crear collector
    collector = DataCollector(api_token, secret_key)

    # Inicializar
    await collector.initialize()

    # Ejecutar según modo
    if args.mode == 'timed':
        await collector.run(duration_days=args.days, interval_minutes=args.interval)
    else:
        await collector.run_continuous(interval_minutes=args.interval)


if __name__ == '__main__':
    asyncio.run(main())
