"""Lettura e scrittura della configurazione bande (OID ``cellwan_band``).

Il pannello scrive con ``PUT /cgi-bin/DAL?oid=cellwan_band&sessionkey=...`` rimandando
indietro l'oggetto intero. Il corpo va cifrato con la stessa sessione AES che
l'integrazione usa per leggere: una login separata in chiaro viene rifiutata.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

import requests

_LOGGER = logging.getLogger(__name__)

# Il modem ci mette qualche secondo a rinegoziare: non usare il timeout dei poll.
_HTTP_TIMEOUT = 45

# Campi che il router accetta in scrittura. Gli altri sono di sola lettura e
# rimandarglieli indietro fa fallire la richiesta su alcuni firmware.
_WRITABLE = ("INTF_Preferred_Access_Technology", "INTF_Preferred_Bands")


def band_object(coordinator: Any) -> dict[str, Any]:
    """Estrae l'oggetto bande dai dati del coordinator, qualunque forma abbia."""
    data = (getattr(coordinator, "data", None) or {}).get("band")
    if not data:
        return {}
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else {}
    if not isinstance(data, dict):
        return {}
    inner = data.get("Object")
    if isinstance(inner, list) and inner and isinstance(inner[0], dict):
        return inner[0]
    if isinstance(inner, dict):
        return inner
    return data


def split_list(value: str | None) -> list[str]:
    """Trasforma "B1,B3,n78" in una lista, tollerando spazi e stringa vuota."""
    if not value:
        return []
    return [piece.strip() for piece in str(value).split(",") if piece.strip()]


class ZyxelBandClient:
    """Scrive la configurazione bande riusando la sessione viva di nr7101."""

    def __init__(self, get_router: Callable[[], Any]) -> None:
        self._get_router = get_router
        # Il router accetta una sessione sola: le scritture vanno in fila.
        self._lock = threading.Lock()

    def write(self, changes: dict[str, str], current: dict[str, Any]) -> tuple[bool, str]:
        """Applica ``changes`` sopra ``current`` e invia. Ritorna (esito, messaggio)."""
        payload = {
            key: changes.get(key, current.get(key, ""))
            for key in _WRITABLE
        }

        with self._lock:
            for attempt in range(2):
                router = self._get_router()
                try:
                    if not getattr(router, "sessionkey", None):
                        if not router.login():
                            return False, "Login al router fallito"
                except Exception as err:  # noqa: BLE001
                    return False, f"Login al router fallito: {err}"

                ok, message, retry = self._put(router, payload)
                if ok:
                    return True, message
                if not retry or attempt == 1:
                    return False, message
                # Sessione invalidata da qualcun altro: rifai login e riprova.
                router.sessionkey = None

        return False, "Scrittura non riuscita"

    def _put(self, router: Any, payload: dict[str, str]) -> tuple[bool, str, bool]:
        url = (
            f"{router.url}/cgi-bin/DAL?"
            f"oid=cellwan_band&sessionkey={router.sessionkey}"
        )

        if getattr(router, "encryption_required", False):
            body = router.encrypt_request(payload)
        else:
            body = json.dumps(payload, separators=(",", ":"))

        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": router.url,
            "Referer": f"{router.url}/",
        }
        params = dict(getattr(router, "params", {}) or {})
        params["timeout"] = _HTTP_TIMEOUT
        params["headers"] = {**params.get("headers", {}), **headers}

        try:
            resp = requests.put(url, data=body.encode("utf-8"), **params)
        except requests.RequestException as err:
            return False, f"Richiesta fallita: {err}", False

        if resp.status_code in (401, 403):
            return False, f"Sessione rifiutata ({resp.status_code})", True

        try:
            raw = resp.json()
        except Exception:  # noqa: BLE001
            raw = {}

        if (
            getattr(router, "encryption_required", False)
            and isinstance(raw, dict)
            and "content" in raw
        ):
            try:
                raw = router.decrypt_response(raw)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Risposta bande non decifrabile: %s", err)
                raw = {}

        esito = raw.get("result") if isinstance(raw, dict) else None
        if resp.status_code == 200 and esito in (None, "ZCFG_SUCCESS"):
            return True, "ok", False

        return False, f"Il router ha risposto {resp.status_code} {esito or ''}".strip(), False
