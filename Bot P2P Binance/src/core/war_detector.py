"""
Detector de guerras de precios.
Identifica cuando un competidor sube consecutivamente su precio
en respuesta a nuestras subidas, y decide no perseguirlo.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from data.database import Database
from data.models import WarTracker, ExchangeRate
from config.settings import WAR_ESCALATION_THRESHOLD, WAR_ESCALATION_WINDOW_SECONDS, WAR_COOLDOWN_MINUTES

logger = logging.getLogger(__name__)


class WarDetector:
    """Detecta y gestiona guerras de precios con competidores."""

    def __init__(self, db: Database):
        self.db = db
        # {(competitor_no, asset, method): WarTracker}
        self._trackers: dict[tuple[str, str, str], WarTracker] = {}
        self._hydrate_from_db()

    def _hydrate_from_db(self):
        """Hidrata guerras de precios activas desde SQLite para persistencia tras reinicio."""
        try:
            active_wars = self.db.get_active_price_wars()
            for w in active_wars:
                started_raw = w.get("started_at")
                started_at = datetime.fromisoformat(started_raw) if started_raw else datetime.now()
                key = (w["competitor_no"], w["asset"], w["payment_method"])
                tracker = WarTracker(
                    competitor_no=w["competitor_no"],
                    competitor_nickname=w.get("competitor_nickname", ""),
                    asset=w["asset"],
                    payment_method=w["payment_method"],
                    escalations=int(w.get("escalations", WAR_ESCALATION_THRESHOLD)),
                    my_price_at_start=float(w.get("my_price_at_start", 0)),
                    competitor_price_at_start=float(w.get("competitor_price_at_start", 0)),
                    started_at=started_at,
                    last_escalation=started_at,
                )
                self._trackers[key] = tracker
            if active_wars:
                logger.info("Hidratadas %d guerras activas desde la base de datos", len(active_wars))
        except Exception as e:
            logger.warning("No se pudieron hidratar guerras activas de BD: %s", e)

    def check_escalation(
        self,
        asset: str,
        payment_method: str,
        competitor: ExchangeRate,
        my_current_price: float,
    ) -> bool:
        """
        Registra una observación del competidor y detecta si hay guerra.

        Returns:
            True si hay guerra activa y NO se debe perseguir.
            False si se puede competir normalmente.
        """
        key = (competitor.advertiser_no, asset, payment_method)
        now = datetime.now()

        # Podar entradas viejas que NO están en guerra y superaron 2x la ventana de escalada
        stale_cutoff = WAR_ESCALATION_WINDOW_SECONDS * 2
        for k, t in list(self._trackers.items()):
            if not t.is_war and t.last_escalation:
                if (now - t.last_escalation).total_seconds() > stale_cutoff:
                    del self._trackers[k]

        if key not in self._trackers:
            self._trackers[key] = WarTracker(
                competitor_no=competitor.advertiser_no,
                competitor_nickname=competitor.advertiser_nickname,
                asset=asset,
                payment_method=payment_method,
                my_price_at_start=my_current_price,
                competitor_price_at_start=competitor.price_ars,
                started_at=now,
            )

        tracker = self._trackers[key]

        # Si pasó más de WAR_ESCALATION_WINDOW_SECONDS desde la última escalada, resetear contador
        if tracker.last_escalation and not tracker.is_war:
            if (now - tracker.last_escalation).total_seconds() > WAR_ESCALATION_WINDOW_SECONDS:
                tracker.escalations = 0

        # ¿El competidor subió desde la última vez y nos disputa la punta (>= nuestro precio)?
        if competitor.price_ars > tracker.competitor_price_at_start:
            # Y nosotros también habíamos subido → escalada
            if my_current_price > tracker.my_price_at_start and competitor.price_ars >= my_current_price:
                was_war = tracker.is_war
                tracker.escalations += 1
                tracker.last_escalation = now

                if tracker.escalations >= WAR_ESCALATION_THRESHOLD:
                    if not was_war:
                        logger.warning(
                            "⚔️ GUERRA DE PRECIOS DETECTADA: %s (%s) en %s/%s "
                            "— %d escaladas, NO perseguir",
                            tracker.competitor_nickname,
                            tracker.competitor_no,
                            asset, payment_method,
                            tracker.escalations,
                        )
                        # Guardar en DB únicamente al entrar en guerra por primera vez
                        self.db.save_price_war(
                            asset=asset,
                            payment_method=payment_method,
                            competitor_no=tracker.competitor_no,
                            competitor_nickname=tracker.competitor_nickname,
                            escalations=tracker.escalations,
                            my_price=my_current_price,
                            competitor_price=competitor.price_ars,
                        )
                    tracker.competitor_price_at_start = competitor.price_ars
                    tracker.my_price_at_start = my_current_price
                    return True
            tracker.competitor_price_at_start = competitor.price_ars
            tracker.my_price_at_start = my_current_price
        elif competitor.price_ars < tracker.competitor_price_at_start and not tracker.is_war:
            # Si el competidor bajó su precio, no hay guerra de subidas
            tracker.escalations = 0
            tracker.competitor_price_at_start = competitor.price_ars
            tracker.my_price_at_start = my_current_price

        return False

    def is_in_war(self, asset: str, payment_method: str) -> bool:
        """Verifica si hay alguna guerra activa para este asset/método."""
        now = datetime.now()
        for key, tracker in list(self._trackers.items()):
            if key[1] == asset and key[2] == payment_method:
                if tracker.is_war and tracker.last_escalation:
                    cooldown = timedelta(minutes=WAR_COOLDOWN_MINUTES)
                    if now - tracker.last_escalation < cooldown:
                        return True
                    else:
                        # Cooldown expirado, resetear
                        self._reset_tracker(key)
        return False

    def _reset_tracker(self, key: tuple[str, str, str]):
        """Resetea un tracker después del cooldown."""
        tracker = self._trackers.get(key)
        if tracker:
            self.db.end_price_war(
                competitor_no=tracker.competitor_no,
                asset=key[1],
                outcome="timeout",
                payment_method=key[2],
            )
            del self._trackers[key]

    def get_active_wars(self) -> list[WarTracker]:
        """Retorna todas las guerras activas (limpiando automáticamente las que cumplieron su cooldown)."""
        active = []
        for key, tracker in list(self._trackers.items()):
            if tracker.is_war and self.is_in_war(tracker.asset, tracker.payment_method):
                if key in self._trackers:
                    active.append(tracker)
        return active

    def get_wars_text(self) -> str:
        """Texto formateado de guerras activas."""
        wars = self.get_active_wars()
        if not wars:
            return "✅ Sin guerras de precios activas"

        lines = ["⚔️ Guerras activas:"]
        for w in wars:
            remaining = ""
            if w.last_escalation:
                elapsed = datetime.now() - w.last_escalation
                remaining_min = max(0, WAR_COOLDOWN_MINUTES - int(elapsed.total_seconds() // 60))
                remaining = f" ({remaining_min}min restantes)"
            lines.append(
                f"  • {w.competitor_nickname} en {w.asset}/{w.payment_method} "
                f"— {w.escalations} escaladas{remaining}"
            )
        return "\n".join(lines)
