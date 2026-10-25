"""Riavvio del router, fatto come lo fa il pannello.

``nr7101.reboot()`` mette la chiave di sessione **nell'URL**; i firmware recenti
la vogliono in un header ``CSRFToken`` e rispondono 401/403 all'altra forma.
In piu' la sessione del router e' una sola: se il pannello e' aperto da
qualche parte, quella dell'integrazione viene invalidata e il comando fallisce.
Qui si riprova una volta rifacendo il login.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import requests

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = 20
_lucchetto = threading.Lock()


def reboot_router(router: Any) -> None:
    """Manda il comando di riavvio. Solleva se il router lo rifiuta davvero."""
    with _lucchetto:
        if not getattr(router, "sessionkey", None):
            if not router.login():
                raise RuntimeError("Login al router fallito")

        for tentativo in range(2):
            parametri = dict(getattr(router, "params", {}) or {})
            parametri["timeout"] = _TIMEOUT
            parametri["headers"] = {
                **parametri.get("headers", {}),
                "X-Requested-With": "XMLHttpRequest",
                "CSRFToken": str(router.sessionkey),
            }

            try:
                with requests.post(f"{router.url}/cgi-bin/Reboot", **parametri) as risposta:
                    if risposta.status_code in (401, 403) and tentativo == 0:
                        _LOGGER.debug(
                            "Riavvio rifiutato (%s): rifaccio il login e riprovo",
                            risposta.status_code,
                        )
                        router.sessionkey = None
                        if not router.login():
                            raise RuntimeError("Login al router fallito")
                        continue
                    risposta.raise_for_status()
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
                # Il router e' caduto prima di rispondere: sta gia' riavviando.
                _LOGGER.debug("Nessuna risposta al riavvio: il router sta ripartendo")
            break

        # La sessione non sopravvive al riavvio.
        router.sessionkey = None
