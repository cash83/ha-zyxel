"""Lettura e scrittura del Wi-Fi (OID ``wlan``).

Il router NON accetta indietro l'oggetto che ha appena dato (risponde
``ZCFG_INVALID_PARAM_VALUE``): vuole una **lista** con dieci campi precisi, e
tre di quelli — ``securityLevel``, ``wpaMode``, ``encryp`` — non esistono in
lettura, il pannello li ricava da ``SecurityMode``. La password si chiama
``psk_value`` in scrittura e ``PskDisplay`` in lettura, dove arriva in chiaro:
rimandarla indietro invariata e' quindi il modo di NON cambiarla.

La password non diventa mai un'entita' ne' un attributo: resterebbe nello stato
di Home Assistant e nel suo storico, leggibile da chiunque guardi le entita'.
Si cambia con ``ha_zyxel.imposta_wifi`` e si rilegge con
``ha_zyxel.leggi_password_wifi``, che la restituisce solo a chi la chiede, nel
momento in cui la chiede, senza lasciarla da nessuna parte.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

import requests
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVIZIO = "imposta_wifi"
SERVIZIO_LETTURA = "leggi_password_wifi"
_TIMEOUT = 45
# Il pannello del router concede un minuto all'applicazione delle modifiche Wi-Fi.
_ATTESA_RADIO = 60

SCHEMA = vol.Schema(
    {
        vol.Optional("nome"): cv.string,
        vol.Optional("password"): cv.string,
        vol.Optional("acceso"): cv.boolean,
    }
)


def wlan_object(coordinator: Any) -> dict[str, Any]:
    """Estrae la configurazione Wi-Fi dai dati del coordinator."""
    dati = (getattr(coordinator, "data", None) or {}).get("wlan")
    if not dati:
        return {}
    if isinstance(dati, list):
        return dati[0] if dati and isinstance(dati[0], dict) else {}
    if not isinstance(dati, dict):
        return {}
    interno = dati.get("Object")
    if isinstance(interno, list) and interno and isinstance(interno[0], dict):
        return interno[0]
    if isinstance(interno, dict):
        return interno
    return dati


# SecurityMode (lettura) -> i tre campi che la scrittura pretende.
_SICUREZZA = {
    "WPA2-Personal": ("MoreSecure", "wpa2psk", "aes"),
    "WPA-WPA2-Personal": ("MoreSecure", "wpawpa2psk", "tkipaes"),
    "WPA3-Personal": ("MoreSecure", "wpa3psk", "aes"),
}


def _in_scrittura(corrente: dict[str, Any]) -> dict[str, Any]:
    """Traduce l'oggetto letto nei dieci campi che il router accetta in PUT."""
    livello, modo, cifratura = _SICUREZZA.get(
        corrente.get("SecurityMode") or "",
        ("NoSecurity", corrente.get("wpaMode") or "", corrente.get("encryp") or "aes"),
    )
    return {
        "Index": corrente.get("Index", 1),
        "wlEnable": bool(corrente.get("wlEnable")),
        "SSID": corrente.get("SSID") or "",
        "wlHide": bool(corrente.get("wlHide")),
        "securityLevel": livello,
        "wpaMode": modo,
        "encryp": cifratura,
        "AutoGenPSK": bool(corrente.get("AutoGenPSK")),
        "psk_value": corrente.get("PskDisplay") or "",
        "RekeyingInterval": corrente.get("RekeyingInterval", 3600),
    }


class ZyxelWlanClient:
    """Scrive la configurazione Wi-Fi riusando la sessione viva di nr7101."""

    def __init__(self, get_router: Callable[[], Any]) -> None:
        self._get_router = get_router
        self._lucchetto = threading.Lock()

    def write(self, modifiche: dict[str, Any], corrente: dict[str, Any]) -> tuple[bool, str]:
        if not corrente:
            return False, "Configurazione Wi-Fi non ancora letta"

        payload = [{**_in_scrittura(corrente), **modifiche}]

        # Traccia di chi tocca il Wi-Fi, senza segreti: serve a distinguere un
        # cambiamento deciso qui da uno deciso dal router.
        _LOGGER.info(
            "Scrittura Wi-Fi: campi=%s wlEnable=%s (prima era %s)",
            sorted(modifiche),
            payload[0].get("wlEnable"),
            corrente.get("wlEnable"),
        )

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

    def _put(self, router: Any, payload: list[dict[str, Any]]) -> tuple[bool, str, bool]:
        url = f"{router.url}/cgi-bin/DAL?oid=wlan&sessionkey={router.sessionkey}"

        if getattr(router, "encryption_required", False):
            body = router.encrypt_request(payload)
        else:
            body = json.dumps(payload, separators=(",", ":"))

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

        try:
            risposta = requests.put(url, data=body.encode("utf-8"), **parametri)
        except requests.RequestException as err:
            return False, f"Richiesta fallita: {err}", False

        if risposta.status_code in (401, 403):
            return False, f"Sessione rifiutata ({risposta.status_code})", True

        try:
            raw = risposta.json()
        except Exception:  # noqa: BLE001
            raw = {}

        if (
            getattr(router, "encryption_required", False)
            and isinstance(raw, dict)
            and "content" in raw
        ):
            try:
                raw = router.decrypt_response(raw)
            except Exception:  # noqa: BLE001
                raw = {}

        esito = raw.get("result") if isinstance(raw, dict) else None
        if risposta.status_code == 200 and esito in (None, "ZCFG_SUCCESS"):
            self._attendi_radio(router, parametri)
            return True, "ok", False
        return False, f"Il router ha risposto {risposta.status_code} {esito or ''}".strip(), False


    @staticmethod
    def _attendi_radio(router: Any, parametri: dict[str, Any]) -> None:
        """Aspetta che la radio si sia riassestata, come fa il pannello.

        Applicare una modifica al Wi-Fi richiede qualche secondo; una seconda
        scrittura arrivata nel frattempo viene accettata e poi persa. Il pannello
        del router, dopo ogni PUT, chiama ``WlCheck`` con un minuto di tempo:
        qui si fa lo stesso. Se non risponde non importa — serve solo ad
        aspettare, non a decidere l'esito.
        """
        attesa = dict(parametri)
        attesa["timeout"] = _ATTESA_RADIO
        try:
            requests.get(f"{router.url}/cgi-bin/Wireless?action=WlCheck", **attesa)
        except requests.RequestException as err:
            _LOGGER.debug("WlCheck non risponde (ininfluente): %s", err)


async def async_registra_servizio(hass: HomeAssistant) -> None:
    """Registra i due servizi del Wi-Fi: scrittura e rilettura della chiave."""
    if hass.services.has_service(DOMAIN, SERVIZIO):
        return

    async def _gestisci(call: ServiceCall) -> None:
        voci = list(hass.data.get(DOMAIN, {}).values())
        if not voci:
            raise HomeAssistantError("Nessun router Zyxel configurato")
        dati = voci[0]

        modifiche: dict[str, Any] = {}
        if "nome" in call.data:
            modifiche["SSID"] = call.data["nome"]
        if "password" in call.data:
            modifiche["psk_value"] = call.data["password"]
        if "acceso" in call.data:
            modifiche["wlEnable"] = call.data["acceso"]
        if not modifiche:
            raise HomeAssistantError("Niente da cambiare")

        ok, messaggio = await hass.async_add_executor_job(
            dati["wlan_client"].write, modifiche, wlan_object(dati["coordinator"])
        )
        if not ok:
            raise HomeAssistantError(f"Wi-Fi non impostato: {messaggio}")
        await dati["coordinator"].async_request_refresh()

    hass.services.async_register(DOMAIN, SERVIZIO, _gestisci, schema=SCHEMA)

    async def _leggi(call: ServiceCall) -> dict[str, Any]:
        """Restituisce la chiave del Wi-Fi a chi chiama, e basta.

        Serve all'occhio del pannello. Il router la da' in chiaro in
        ``PskDisplay``; qui non viene salvata, solo passata indietro.
        """
        voci = list(hass.data.get(DOMAIN, {}).values())
        if not voci:
            raise HomeAssistantError("Nessun router Zyxel configurato")
        oggetto = wlan_object(voci[0]["coordinator"])
        if not oggetto:
            raise HomeAssistantError("Configurazione Wi-Fi non ancora letta")
        return {"password": oggetto.get("PskDisplay") or ""}

    hass.services.async_register(
        DOMAIN,
        SERVIZIO_LETTURA,
        _leggi,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
