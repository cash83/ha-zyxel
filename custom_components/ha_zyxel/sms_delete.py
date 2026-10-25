"""Cancellazione dei messaggi dalla casella del router.

Il pannello manda ``DELETE /cgi-bin/DAL?oid=cellwan_sms`` con ``{"objIndex": n}``.
Un messaggio lungo occupa piu' voci: vanno cancellate tutte, e **dalla piu' alta
alla piu' bassa**, perche' il router rinumera le voci rimaste.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import requests
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVIZIO = "elimina_sms"
_TIMEOUT = 30
_lucchetto = threading.Lock()

SCHEMA = vol.Schema(
    {
        vol.Required("indici"): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    }
)


def _elimina_uno(router: Any, indice: int) -> tuple[bool, str]:
    # Il pannello, per DELETE e GET, mette l'oggetto **nella query in chiaro** e
    # NON manda nessun corpo: solo POST e PUT hanno il corpo cifrato. Mandare
    # un corpo qui fa chiudere la connessione senza risposta.
    url = (
        f"{router.url}/cgi-bin/DAL?oid=cellwan_sms"
        f"&sessionkey={router.sessionkey}"
        f"&objIndex={indice}"
    )

    parametri = dict(getattr(router, "params", {}) or {})
    parametri["timeout"] = _TIMEOUT
    parametri["headers"] = {
        **parametri.get("headers", {}),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": router.url,
        "Referer": f"{router.url}/",
    }

    try:
        risposta = requests.delete(url, **parametri)
    except requests.RequestException as err:
        return False, f"Richiesta fallita: {err}"

    if risposta.status_code in (401, 403):
        return False, "sessione"
    if risposta.status_code != 200:
        return False, f"il router ha risposto {risposta.status_code}"
    return True, "ok"


def elimina(router: Any, indici: list[int]) -> tuple[bool, str]:
    """Cancella le voci indicate. Ritorna (esito, messaggio)."""
    with _lucchetto:
        if not getattr(router, "sessionkey", None):
            if not router.login():
                return False, "Login al router fallito"

        # Dalla piu' alta: cancellare la 1 farebbe scalare tutte le altre.
        for indice in sorted(set(indici), reverse=True):
            ok, msg = _elimina_uno(router, indice)
            if not ok and msg == "sessione":
                router.sessionkey = None
                if not router.login():
                    return False, "Login al router fallito"
                ok, msg = _elimina_uno(router, indice)
            if not ok:
                return False, f"Voce {indice} non cancellata: {msg}"

    return True, "ok"


async def async_registra_servizio(hass: HomeAssistant) -> None:
    """Registra ``ha_zyxel.elimina_sms``."""
    if hass.services.has_service(DOMAIN, SERVIZIO):
        return

    async def _gestisci(call: ServiceCall) -> None:
        indici = call.data["indici"]
        voci = list(hass.data.get(DOMAIN, {}).values())
        if not voci:
            _LOGGER.error("Nessun router Zyxel configurato")
            return
        dati = voci[0]
        ok, messaggio = await hass.async_add_executor_job(
            elimina, dati["router"], indici
        )
        if not ok:
            _LOGGER.error("SMS non cancellato: %s", messaggio)
            return
        coordinator = dati.get("coordinator")
        if coordinator:
            await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, SERVIZIO, _gestisci, schema=SCHEMA)
