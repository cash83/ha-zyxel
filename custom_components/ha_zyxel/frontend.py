"""Registra il pannello Zyxel nella barra laterale.

Il pannello e' solo interfaccia: legge e comanda le entita' gia' esistenti
attraverso ``hass``, quindi non serve nessuna API aggiuntiva.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend as ha_frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FILE_PANNELLO = "panel.js"
URL_STATICO = "/ha_zyxel_panel/panel.js"
URL_PANNELLO = "zyxel"
NOME_COMPONENTE = "zyxel-panel"

_CHIAVE = f"{DOMAIN}_frontend"


def _stato(hass: HomeAssistant) -> dict[str, bool]:
    return hass.data.setdefault(_CHIAVE, {"statico": False, "pannello": False})


async def async_registra_pannello(hass: HomeAssistant) -> None:
    """Serve il file e mette la voce nella barra laterale (una volta sola)."""
    stato = _stato(hass)
    percorso = Path(__file__).parent / FILE_PANNELLO

    if not stato["statico"]:
        try:
            await hass.http.async_register_static_paths(
                [StaticPathConfig(URL_STATICO, str(percorso), False)]
            )
            stato["statico"] = True
        except RuntimeError as err:
            # Gia' registrato da un avvio precedente dell'entry: non e' un errore.
            _LOGGER.debug("Percorso statico gia' presente: %s", err)
            stato["statico"] = True

    if stato["pannello"]:
        return

    # La data del file nell'URL evita che il browser serva una copia vecchia.
    versione = percorso.stat().st_mtime_ns
    ha_frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Zyxel",
        sidebar_icon="mdi:router-wireless",
        frontend_url_path=URL_PANNELLO,
        config={
            "_panel_custom": {
                "name": NOME_COMPONENTE,
                "embed_iframe": False,
                "trust_external": False,
                "module_url": f"{URL_STATICO}?v={versione}",
            }
        },
        require_admin=True,
    )
    stato["pannello"] = True


def rimuovi_pannello(hass: HomeAssistant) -> None:
    """Toglie la voce dalla barra quando l'integrazione viene rimossa."""
    stato = _stato(hass)
    if not stato["pannello"]:
        return
    try:
        ha_frontend.async_remove_panel(hass, URL_PANNELLO)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Pannello gia' rimosso: %s", err)
    stato["pannello"] = False
