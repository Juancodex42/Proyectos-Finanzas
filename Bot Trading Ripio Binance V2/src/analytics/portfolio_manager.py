"""
Gestor profesional de portafolio multi-moneda y control de exposición.
Calcula valuación en USD, límites de riesgo por activo y señales de rebalanceo.
Referencia de diseño: docs/ARQUITECTURA.md
"""

import logging
from typing import Dict, Tuple, List
import asyncio

logger = logging.getLogger(__name__)


class AdvancedPortfolioManager:
    """
    Gestión profesional de capital multi-moneda con:
    - Tracking de inventario en tiempo real
    - Límites de exposición por moneda
    - Rebalanceo automático
    - P&L tracking por estrategia
    - Conversión a USD equivalente
    """

    def __init__(self, ripio_api, config: Dict):
        self.ripio = ripio_api
        self.config = config

        # Límites desde config
        portfolio_config = config.get('portfolio', {})
        self.limites = {
            'max_exposicion_ars_pct': portfolio_config.get('max_exposicion_ars_pct', 0.30),
            'max_exposicion_crypto_pct': portfolio_config.get('max_exposicion_crypto_pct', 0.20),
            'min_stablecoins_pct': portfolio_config.get('min_stablecoins_pct', 0.50),
            'max_desbalance_usdt_usdc_pct': portfolio_config.get('max_desbalance_usdt_usdc_pct', 0.15),
            'rebalanceo_threshold': portfolio_config.get('rebalanceo_threshold', 0.10)
        }

        # Estado del portfolio
        self.inventario = {
            'USDT': 0.0,
            'USDC': 0.0,
            'ARS': 0.0,
            'BTC': 0.0,
            'ETH': 0.0
        }

        # Precios de referencia en USD
        self.precios_usd = {
            'USDT': 1.0,
            'USDC': 1.0,
            'ARS': 0.0,
            'BTC': 0.0,
            'ETH': 0.0
        }

        # P&L por estrategia
        self.pnl_por_estrategia = {
            'statistical_arbitrage': {'trades': [], 'pnl_total': 0.0},
            'market_making': {'trades': [], 'pnl_total': 0.0},
            'triangular_arbitrage': {'trades': [], 'pnl_total': 0.0}
        }

    async def actualizar_inventario(self) -> bool:
        """
        Sincroniza inventario con Ripio

        Returns:
            True si exitoso
        """
        try:
            balance = await self.ripio.get_balance()

            if not balance:
                logger.error("❌ No se pudo obtener balance")
                return False

            # Actualiza inventario
            for moneda in self.inventario.keys():
                if moneda in balance:
                    self.inventario[moneda] = balance[moneda].get('available', 0.0)

            logger.info(f"💼 Inventario actualizado:")
            for moneda, cantidad in self.inventario.items():
                if cantidad > 0:
                    logger.info(f"   {moneda}: {cantidad:.4f}")

            return True

        except Exception as e:
            logger.error(f"❌ Error actualizando inventario: {e}")
            return False

    async def actualizar_precios(self) -> bool:
        """
        Actualiza precios de referencia en USD

        Returns:
            True si exitoso
        """
        try:
            # USDT/ARS
            usdt_ticker = await self.ripio.get_ticker('USDT_ARS')
            if usdt_ticker:
                # Precio ARS por 1 USD
                self.precios_usd['ARS'] = 1.0 / usdt_ticker['ask']

            # BTC/USDC
            btc_ticker = await self.ripio.get_ticker('BTC_USDC')
            if btc_ticker:
                self.precios_usd['BTC'] = btc_ticker['ask']

            # ETH/USDC
            eth_ticker = await self.ripio.get_ticker('ETH_USDC')
            if eth_ticker:
                self.precios_usd['ETH'] = eth_ticker['ask']

            logger.debug("📊 Precios actualizados")
            return True

        except Exception as e:
            logger.error(f"❌ Error actualizando precios: {e}")
            return False

    def calcular_valor_portfolio_usd(self) -> float:
        """
        Calcula valor total del portfolio en USD

        Returns:
            Valor total en USD
        """
        valor_total = 0.0

        for moneda, cantidad in self.inventario.items():
            precio_usd = self.precios_usd.get(moneda, 0)
            valor_usd = cantidad * precio_usd
            valor_total += valor_usd

        return valor_total

    def calcular_exposicion_por_moneda(self) -> Dict[str, float]:
        """
        Calcula % de exposición por moneda

        Returns:
            {'USDT': 0.35, 'USDC': 0.30, 'ARS': 0.25, ...}
        """
        valor_total = self.calcular_valor_portfolio_usd()

        if valor_total == 0:
            return {m: 0.0 for m in self.inventario.keys()}

        exposicion = {}
        for moneda, cantidad in self.inventario.items():
            valor_usd = cantidad * self.precios_usd.get(moneda, 0)
            exposicion[moneda] = valor_usd / valor_total

        return exposicion

    async def validar_limites_exposicion(self) -> Tuple[bool, List[str]]:
        """
        Valida que exposición cumple límites

        Returns:
            (es_valido, [lista de violaciones])
        """
        exposicion = self.calcular_exposicion_por_moneda()
        violaciones = []

        # 1. Límite ARS
        if exposicion.get('ARS', 0) > self.limites['max_exposicion_ars_pct']:
            violaciones.append(
                f"❌ Exposición ARS ({exposicion['ARS']:.1%}) "
                f"excede límite ({self.limites['max_exposicion_ars_pct']:.1%})"
            )

        # 2. Límite crypto
        exposicion_crypto = exposicion.get('BTC', 0) + exposicion.get('ETH', 0)
        if exposicion_crypto > self.limites['max_exposicion_crypto_pct']:
            violaciones.append(
                f"❌ Exposición crypto ({exposicion_crypto:.1%}) "
                f"excede límite ({self.limites['max_exposicion_crypto_pct']:.1%})"
            )

        # 3. Mínimo stablecoins
        exposicion_stables = exposicion.get('USDT', 0) + exposicion.get('USDC', 0)
        if exposicion_stables < self.limites['min_stablecoins_pct']:
            violaciones.append(
                f"⚠️ Exposición stablecoins ({exposicion_stables:.1%}) "
                f"bajo mínimo ({self.limites['min_stablecoins_pct']:.1%})"
            )

        # 4. Balance USDT/USDC
        usdt_pct = exposicion.get('USDT', 0)
        usdc_pct = exposicion.get('USDC', 0)
        desbalance = abs(usdt_pct - usdc_pct)

        if desbalance > self.limites['max_desbalance_usdt_usdc_pct']:
            violaciones.append(
                f"⚠️ Desbalance USDT/USDC ({desbalance:.1%}) "
                f"excede threshold ({self.limites['max_desbalance_usdt_usdc_pct']:.1%})"
            )

        es_valido = len(violaciones) == 0
        return es_valido, violaciones

    async def necesita_rebalanceo(self) -> Tuple[bool, str]:
        """
        Determina si portfolio necesita rebalanceo

        Returns:
            (necesita, tipo_rebalanceo)
        """
        exposicion = self.calcular_exposicion_por_moneda()

        # Target: 50% USDT, 50% USDC, 0% ARS
        target = {'USDT': 0.50, 'USDC': 0.50, 'ARS': 0.0}

        # Calcula desviación total
        desviacion_total = sum(
            abs(exposicion.get(m, 0) - target_pct)
            for m, target_pct in target.items()
        )

        if desviacion_total > self.limites['rebalanceo_threshold']:
            # Determina tipo de acción
            ars_pct = exposicion.get('ARS', 0)
            usdt_pct = exposicion.get('USDT', 0)
            usdc_pct = exposicion.get('USDC', 0)

            if ars_pct > 0.10:
                return True, "convertir_ars_a_stables"
            elif usdt_pct > usdc_pct + 0.15:
                return True, "convertir_usdt_a_usdc"
            elif usdc_pct > usdt_pct + 0.15:
                return True, "convertir_usdc_a_usdt"
            else:
                return True, "rebalanceo_general"

        return False, "balanceado"

    def registrar_trade(self, estrategia: str, trade: Dict):
        """
        Registra trade para tracking de P&L

        Args:
            estrategia: 'statistical_arbitrage', 'market_making', etc.
            trade: Dict con datos del trade
        """
        if estrategia in self.pnl_por_estrategia:
            self.pnl_por_estrategia[estrategia]['trades'].append(trade)
            self.pnl_por_estrategia[estrategia]['pnl_total'] += trade.get('pnl', 0)

            logger.info(
                f"📝 Trade registrado: {estrategia} "
                f"P&L={trade.get('pnl', 0):.2f} USD"
            )

    def get_estadisticas_portfolio(self) -> Dict:
        """
        Retorna estadísticas completas del portfolio

        Returns:
            Dict con todas las métricas
        """
        valor_total_usd = self.calcular_valor_portfolio_usd()
        exposicion = self.calcular_exposicion_por_moneda()
        pnl_total = sum(
            e['pnl_total'] for e in self.pnl_por_estrategia.values()
        )

        return {
            'valor_total_usd': valor_total_usd,
            'inventario': self.inventario,
            'exposicion_pct': exposicion,
            'precios_usd': self.precios_usd,
            'pnl_total': pnl_total,
            'pnl_por_estrategia': {
                k: {
                    'pnl': v['pnl_total'],
                    'num_trades': len(v['trades'])
                }
                for k, v in self.pnl_por_estrategia.items()
            }
        }

    async def generar_reporte(self) -> str:
        """
        Genera reporte legible del portfolio

        Returns:
            String formateado con reporte
        """
        # Actualiza datos
        await self.actualizar_inventario()
        await self.actualizar_precios()

        stats = self.get_estadisticas_portfolio()
        valor_total = stats['valor_total_usd']
        exposicion = stats['exposicion_pct']

        reporte = f"""
=== PORTFOLIO STATUS ===
Valor Total: ${valor_total:,.2f} USD
P&L Total: ${stats['pnl_total']:+,.2f}

Inventario:
"""

        for moneda, cantidad in stats['inventario'].items():
            if cantidad > 0.01:
                valor_usd = cantidad * stats['precios_usd'][moneda]
                reporte += f"  - {moneda}: {cantidad:.4f} (${valor_usd:,.2f})\n"

        reporte += f"\nExposicion:\n"
        for moneda, pct in exposicion.items():
            if pct > 0.01:
                status = "[OK]" if pct < 0.60 else "[WARN]"
                reporte += f"  - {moneda}: {pct:.1%} {status}\n"

        reporte += f"\nP&L por Estrategia:\n"
        for estrategia, data in stats['pnl_por_estrategia'].items():
            if data['num_trades'] > 0:
                reporte += (
                    f"  - {estrategia}: ${data['pnl']:+,.2f} "
                    f"({data['num_trades']} trades)\n"
                )

        return reporte
