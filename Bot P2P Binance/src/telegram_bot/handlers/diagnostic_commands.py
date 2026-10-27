"""
Manejadores de comandos de diagnóstico, estado, simulación anti-baneo, auditoría y reportería.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.formatters.alert_view import (
    escape_md,
    format_daily_report,
    format_profit_report,
    _translate_reason,
)
from telegram_bot.formatters.dashboard_view import format_simulation_report

logger = logging.getLogger(__name__)


class DiagnosticCommandsMixin:
    """Mixin que contiene comandos de diagnóstico: status, simulación, auditoría, reportes y métricas."""

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra el estado general del bot y resumen de anuncios."""
        text = await self.engine.get_status_text() if self.engine else "⚠️ Engine no disponible"
        if text and len(text) > 4000:
            cut = text.rfind("\n", 0, 4000)
            text = (text[:cut] if cut > 0 else text[:4000]) + "\n..."
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=self.get_reply_keyboard())

    async def _cmd_simulate(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Ejecuta una auditoría y simulación de precios anti-baneo (dry-run)."""
        await update.message.reply_text(
            "🛡️ *Ejecutando Simulación y Auditoría Anti-Baneo...*\n\n"
            "• Escaneando mercado real en vivo (Spot + Benchmarks USDT + Libros P2P)...\n"
            "• Evaluando precios óptimos por grupo sin tocar Binance (Dry-Run)...\n"
            "• Auditando 6 reglas de Binance P2P con AntiBanValidator...",
            parse_mode="Markdown",
        )
        sim_data = await self.engine.audit_market_dry_run() if self.engine else {}
        report = format_simulation_report(sim_data) if sim_data else "Simulación no disponible."
        await update.message.reply_text(report, parse_mode="Markdown", reply_markup=self.get_inline_panel())

    async def _cmd_stress_test(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Ejecuta la suite sintética de estrés anti-baneo (6 escenarios hostiles)."""
        await update.message.reply_text(
            "🚀 *Iniciando Batería de Pruebas de Estrés Anti-Baneo...*\n\n"
            "• Escenario 1: Guerra de Precios Blitzkrieg\n"
            "• Escenario 2: Squeeze Anti-Colisión (separación >= 0.15%)\n"
            "• Escenario 3: Flash Crash de Spot (-25%)\n"
            "• Escenario 4: Competidor Troll Outlier (+80%)\n"
            "• Escenario 5: Asfixia Progresiva de Liquidez\n"
            "• Escenario 6: Micro-fluctuación pasiva de Spot\n\n"
            "⏳ Ejecutando simulación...",
            parse_mode="Markdown",
        )
        try:
            from scripts.stress_test_antiblocking import (
                run_scenario_1_blitzkrieg_war,
                run_scenario_2_precision_squeeze,
                run_scenario_3_flash_crash,
                run_scenario_4_troll_outlier,
                run_scenario_5_liquidity_asphyxiation,
                run_scenario_6_passive_flapping,
            )
            r1 = await run_scenario_1_blitzkrieg_war()
            r2 = await run_scenario_2_precision_squeeze()
            r3 = await run_scenario_3_flash_crash()
            r4 = run_scenario_4_troll_outlier()
            r5 = await run_scenario_5_liquidity_asphyxiation()
            r6 = await run_scenario_6_passive_flapping()

            results = [r1, r2, r3, r4, r5, r6]
            passed_count = sum(1 for r in results if r["passed"])
            all_viols = sum(len(r.get("violations", [])) for r in results)

            status_icon = "🟢" if passed_count == 6 and all_viols == 0 else "🔴"
            verdict = "🛡️ *VEREDICTO:* Algoritmo 100% robusto y matemáticamente blindado." if all_viols == 0 else "⚠️ *VEREDICTO:* Fallas detectadas."
            lines = [
                f"{status_icon} *RESULTADOS DE STRESS TEST ANTI-BANEO*\n",
                f"• Escenarios aprobados: *{passed_count}/6* ({(passed_count/6)*100:.1f}%)",
                f"• Violaciones a reglas de Binance: *{all_viols}*",
                "",
                f"{'✅' if r1['passed'] else '❌'} 1. Blitzkrieg Price War",
                f"{'✅' if r2['passed'] else '❌'} 2. Precision Anti-Collision Squeeze",
                f"{'✅' if r3['passed'] else '❌'} 3. Spot Flash Crash Protection",
                f"{'✅' if r4['passed'] else '❌'} 4. Troll Outlier Rejection",
                f"{'✅' if r5['passed'] else '❌'} 5. Progressive Liquidity Asphyxiation",
                f"{'✅' if r6['passed'] else '❌'} 6. Anti-83714 Passive Flapping Hold",
                "",
                verdict,
            ]
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=self.get_inline_panel())
        except Exception as e:
            await update.message.reply_text(f"❌ Error ejecutando stress test: `{e}`", parse_mode="Markdown")

    async def _cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra estadísticas diarias del bot."""
        stats = self.db.get_daily_stats()
        await update.message.reply_text(format_daily_report(stats), parse_mode="Markdown")

    async def _cmd_orders(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra los últimos cambios de precio y órdenes recientes."""
        changes = self.db.get_recent_price_changes(10)
        if not changes:
            await update.message.reply_text("Sin órdenes recientes")
            return
        lines = ["📋 *Últimos cambios de precio:*\n"]
        for c in changes[:10]:
            reason_str = _translate_reason(c.get("reason", ""))
            asset = escape_md(str(c.get("asset", "")))
            lines.append(f"  {asset} G{c.get('ad_group', '?')}: ${c.get('old_price', 0):,.0f} → ${c.get('new_price', 0):,.0f} ({reason_str})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_wars(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra el reporte de guerras de precios detectadas."""
        text = self.engine.war_detector.get_wars_text() if self.engine else "⚠️ Engine no disponible"
        await update.message.reply_text(text)

    async def _cmd_daily(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra el reporte resumen del día actual."""
        profit_ars = None
        if self.engine and hasattr(self.engine, "profit_tracker") and self.engine.profit_tracker:
            try:
                rep = await self.engine.profit_tracker.calculate_profit()
                profit_ars = rep.total_profit_ars
            except Exception as e_prof:
                logger.debug("Error calculando ganancia en _cmd_daily: %s", e_prof)
        stats = self.db.get_daily_stats(profit_ars=profit_ars)
        await update.message.reply_text(format_daily_report(stats), parse_mode="Markdown")

    async def _cmd_profit(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra las ganancias detalladas realizadas y proyectadas."""
        if self.engine and hasattr(self.engine, "profit_tracker") and self.engine.profit_tracker:
            try:
                report = await self.engine.profit_tracker.calculate_profit()
                text = format_profit_report(report)
            except Exception as e:
                logger.error("Error calculando ganancias en /ganancias: %s", e)
                text = f"⚠️ Error calculando ganancias: {escape_md(str(e))}"
        else:
            stats = self.db.get_daily_stats()
            text = (
                f"📈 *Ganancias del Día*\n\n"
                f"• Ganancia estimada: *${stats.get('daily_profit_ars', 0.0):,.0f} ARS*\n"
                f"• Compras: {stats['buy_orders']} (${stats['buy_volume_ars']:,.0f} ARS)\n"
                f"• Ventas: {stats['sell_orders']} (${stats['sell_volume_ars']:,.0f} ARS)"
            )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_methods(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra los métodos de pago seleccionados y sus grupos."""
        methods = self.db.get_selected_methods()
        if not methods:
            await update.message.reply_text("Sin métodos seleccionados")
            return
        lines = ["💳 *Métodos seleccionados:*\n"]
        for m in methods:
            lines.append(f"  G{m.assigned_group}: {escape_md(m.identifier)} (score={m.score:.1f}, sellers={m.sellers_count})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_groups(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra el agrupamiento actual de métodos de pago."""
        methods = self.db.get_selected_methods()
        groups: dict[int, list] = {}
        for m in methods:
            groups.setdefault(m.assigned_group, []).append(m)
        lines = ["📦 *Agrupamiento de métodos:*\n"]
        for g, ms in sorted(groups.items()):
            names = [escape_md(m.identifier) for m in ms]
            lines.append(f"  Grupo {g}: {', '.join(names)}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_assets(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Muestra los activos monitoreados y cantidad de anuncios activos."""
        ads = self.db.get_my_ads()
        assets = sorted(set(ad.asset for ad in ads))
        config = self.db.load_bot_config()
        lines = ["📋 *Activos monitoreados:*\n"]
        for asset in assets:
            count = sum(1 for a in ads if a.asset == asset and a.status == 1)
            icon = "⏸️" if asset in config.paused_assets else "🟢"
            lines.append(f"  {icon} {asset} ({count} anuncios activos)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
