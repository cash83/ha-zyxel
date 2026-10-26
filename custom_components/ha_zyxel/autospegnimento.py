"""Lo spegnimento automatico del Wi-Fi (OID ``wifi_others``).

Il Wi-Fi dell'NR7302 nasce come rete di sola amministrazione e il firmware lo
spegne da solo: il manuale (p. 276) dice *\"will be automatically turned off 30
minutes after the Zyxel Device boots up\"*, e l'impostazione e' l'``Auto Switch
Off`` di p. 104 — intervallo 0, 15, 30, 45 o 60 minuti, zero per non spegnerlo
mai. Qui diventa un interruttore e un menu, cosi' non serve entrare nel pannello
del router per cambiarlo.

TRAPPOLA: in lettura questo OID vuole DUE parametri nella query —
``DalGetOneObject=y`` e ``Index`` (1 = 2.4 GHz). Senza il primo risponde
``ZCFG_INVALID_ARGUMENTS``, senza entrambi sembra che l'OID non esista.
A differenza di ``wlan``, la scrittura manda un oggetto solo, non una lista —
ma, come per ``wlan``, non riaccetta i valori come li ha dati: ``wlProtect``
torna indietro come ``auto``/``off``, il preambolo ``auto`` diventa ``long``, e
i numeri devono essere interi veri (il pannello li passa tutti per ``parseInt``).
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

import requests

_LOGGER = logging.getLogger(__name__)

OID = "wifi_others"
INDICE_24GHZ = 1
_TIMEOUT = 30

# Gli unici intervalli che il pannello del router offre.
INTERVALLI = ("0", "15", "30", "45", "60")

# I campi che la scrittura pretende, presi com'erano dalla lettura tranne quelli
# che stiamo cambiando.
_CAMPI = (
    "wlRtsThrshld",
    "wlFrgThrshld",
    "wlTxPwrPcnt",
    "wlBcnIntvl",
    "wlDtmIntvl",
    "wlMode",
    "wlProtect",
    "wlPreamble",
    "InActiveChan",
    "atf",
    "wlAutoOffEnable",
    "wlAutoOffIntvl",
    "wlPmf",
)


def oggetto(coordinator: Any) -> dict[str, Any]:
    """La configurazione 'Others' del Wi-Fi letta dal coordinator."""
    dati = (getattr(coordinator, "data", None) or {}).get("wifi_others")
    if isinstance(dati, list):
        return dati[0] if dati and isinstance(dati[0], dict) else {}
    return dati if isinstance(dati, dict) else {}


def leggi(router: Any) -> dict[str, Any] | None:
    """GET con ``Index``, come fa il pannello del router.

    Si ricalca ``nr7101.get_json_object``: stessi parametri (cookie di sessione
    compresi) e **chiave di sessione nell'URL**, piu' l'``Index`` che solo
    questo OID pretende.
    """
    url = f"{router.url}/cgi-bin/DAL?oid={OID}"
    if getattr(router, "sessionkey", None):
        url += f"&sessionkey={router.sessionkey}"
    # ``DalGetOneObject=y`` lo aggiunge il pannello a ogni GET con parametri:
    # senza, il router risponde ZCFG_INVALID_ARGUMENTS.
    url += f"&DalGetOneObject=y&Index={INDICE_24GHZ}"

    parametri = dict(getattr(router, "params", {}) or {})
    parametri.setdefault("timeout", _TIMEOUT)

    risposta = requests.get(url, **parametri)
    if risposta.status_code != 200:
        _LOGGER.debug("wifi_others: il router ha risposto %s", risposta.status_code)
        return None

    grezzo = risposta.json()
    if (
        getattr(router, "encryption_required", False)
        and isinstance(grezzo, dict)
        and "content" in grezzo
    ):
        grezzo = router.decrypt_response(grezzo)

    interno = grezzo.get("Object") if isinstance(grezzo, dict) else None
    if isinstance(interno, list) and interno and isinstance(interno[0], dict):
        _LOGGER.debug("wifi_others letto: %s", interno[0])
        return interno[0]
    if isinstance(interno, dict):
        return interno
    _LOGGER.debug(
        "wifi_others: risposta senza Object (result=%s)",
        grezzo.get("result") if isinstance(grezzo, dict) else type(grezzo).__name__,
    )
    return None


# Numeri che il router vuole interi, non stringhe.
_INTERI = (
    "wlRtsThrshld",
    "wlFrgThrshld",
    "wlTxPwrPcnt",
    "wlBcnIntvl",
    "wlDtmIntvl",
    "wlAutoOffIntvl",
    # Il router lo da' come 0/1, non come true/false: rimandarglielo booleano
    # fa fallire tutta la scrittura con ZCFG_INVALID_PARAM_VALUE.
    "wlAutoOffEnable",
)


def _in_scrittura(corrente: dict[str, Any]) -> dict[str, Any]:
    """Traduce l'oggetto letto in quello che la PUT accetta.

    Solo i campi che il router ha davvero dato: uno assente diventerebbe
    ``None``, e si riscriverebbe a zero una soglia RTS o la potenza radio.
    """
    fuori: dict[str, Any] = {}
    for campo in _CAMPI:
        if campo not in corrente:
            continue
        valore = corrente[campo]
        if campo in _INTERI:
            try:
                valore = int(valore)
            except (TypeError, ValueError):
                continue
        elif campo == "wlProtect":
            # In lettura e' true/false, in scrittura "auto" oppure "off".
            if valore not in ("auto", "off"):
                vero = valore is True or str(valore).lower() == "true"
                valore = "auto" if vero else "off"
        elif campo == "wlPreamble":
            # Il router puo' dire "auto", ma la scrittura accetta solo i due.
            valore = "short" if valore == "short" else "long"
        fuori[campo] = valore
    return fuori


class ZyxelAutoOffClient:
    """Scrive ``wlAutoOffEnable`` e ``wlAutoOffIntvl`` lasciando il resto com'e'."""

    def __init__(self, get_router: Callable[[], Any]) -> None:
        self._get_router = get_router
        self._lucchetto = threading.Lock()

    def write(self, modifiche: dict[str, Any], corrente: dict[str, Any]) -> tuple[bool, str]:
        if not corrente:
            return False, "Impostazioni Wi-Fi non ancora lette"

        payload = _in_scrittura(corrente)
        payload.update(modifiche)
        payload["Index"] = corrente.get("Index", INDICE_24GHZ)

        with self._lucchetto:
            for tentativo in range(2):
                router = self._get_router()
                try:
                    if not getattr(router, "sessionkey", None):
                        if not router.login():
                            return False, "Login al router fallito"
                except Exception as err:  # noqa: BLE001
                    return False, f"Login al router fallito: {err}"

                ok, messaggio, riprova = self._put(router, payload)
                if ok:
                    return True, messaggio
                if not riprova or tentativo == 1:
                    return False, messaggio
                router.sessionkey = None

        return False, "Scrittura non riuscita"

    def _put(self, router: Any, payload: dict[str, Any]) -> tuple[bool, str, bool]:
        url = f"{router.url}/cgi-bin/DAL?oid={OID}&sessionkey={router.sessionkey}"

        if getattr(router, "encryption_required", False):
            corpo = router.encrypt_request(payload)
        else:
            corpo = json.dumps(payload, separators=(",", ":"))

        parametri = dict(getattr(router, "params", {}) or {})
        parametri["timeout"] = _TIMEOUT
        parametri["headers"] = {
            **parametri.get("headers", {}),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "CSRFToken": str(router.sessionkey),
            "Origin": router.url,
            "Referer": f"{router.url}/",
        }

        _LOGGER.debug("wifi_others scrivo: %s", payload)
        try:
            risposta = requests.put(url, data=corpo.encode("utf-8"), **parametri)
        except requests.RequestException as err:
            return False, f"Richiesta fallita: {err}", False

        if risposta.status_code in (401, 403):
            return False, f"Sessione rifiutata ({risposta.status_code})", True

        try:
            grezzo = risposta.json()
        except Exception:  # noqa: BLE001
            grezzo = {}

        if (
            getattr(router, "encryption_required", False)
            and isinstance(grezzo, dict)
            and "content" in grezzo
        ):
            try:
                grezzo = router.decrypt_response(grezzo)
            except Exception:  # noqa: BLE001
                grezzo = {}

        esito = grezzo.get("result") if isinstance(grezzo, dict) else None
        if risposta.status_code == 200 and esito in (None, "ZCFG_SUCCESS"):
            return True, "ok", False
        return False, f"Il router ha risposto {risposta.status_code} {esito or ''}".strip(), False
