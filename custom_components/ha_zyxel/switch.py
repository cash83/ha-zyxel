"""Interruttori: selezione delle bande e radio Wi-Fi.

Nel router l'auto-selezione non e' un campo: corrisponde a ``INTF_Preferred_Bands``
vuoto. Spegnerla significa scrivere la lista esplicita delle bande scelte.
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .band_client import band_object, split_list
from .const import DOMAIN
from .wlan_client import wlan_object

_LOGGER = logging.getLogger(__name__)

_PREFERITE = "INTF_Preferred_Bands"
_SUPPORTATE = "INTF_Supported_Bands"

# Il modulo ne supporta 29, ma in Italia se ne usano dieci: le altre sarebbero
# solo interruttori da scorrere. Confronto in minuscolo perche' il router
# scrive "B1" e "n78".
_BANDE_ITALIA = frozenset(
    {"b1", "b3", "b7", "b20", "b28", "n1", "n3", "n28", "n38", "n78"}
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Crea l'interruttore dell'auto-selezione e uno per ogni banda supportata."""
    dati = hass.data[DOMAIN][entry.entry_id]
    coordinator = dati["coordinator"]
    entita: list[SwitchEntity] = []

    if wlan_object(coordinator):
        entita.append(ZyxelWifi(coordinator, entry, dati["wlan_client"]))
    else:
        _LOGGER.debug("Nessun dato Wi-Fi: interruttore non creato")

    oggetto = band_object(coordinator)
    if oggetto:
        client = dati["band_client"]
        entita.append(ZyxelBandAuto(coordinator, entry, client))
        for banda in split_list(oggetto.get(_SUPPORTATE)):
            if banda.lower() not in _BANDE_ITALIA:
                continue
            entita.append(ZyxelBand(coordinator, entry, client, banda))
    else:
        _LOGGER.debug("Nessun dato bande: interruttori non creati")

    if entita:
        async_add_entities(entita)


class _Base(CoordinatorEntity, SwitchEntity):
    """Parte comune: device, categoria, accesso ai dati bande."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry, client) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )

    @property
    def _oggetto(self) -> dict:
        return band_object(self.coordinator)

    @property
    def _preferite(self) -> list[str]:
        return split_list(self._oggetto.get(_PREFERITE))

    async def _scrivi(self, bande: list[str]) -> None:
        ok, messaggio = await self.hass.async_add_executor_job(
            self._client.write, {_PREFERITE: ",".join(bande)}, self._oggetto
        )
        if not ok:
            _LOGGER.error("Bande non impostate: %s", messaggio)
            return
        await self.coordinator.async_request_refresh()


class ZyxelBandAuto(_Base):
    """Acceso = lascia scegliere al modem (lista preferite vuota)."""

    _attr_name = "Selezione banda automatica"
    _attr_icon = "mdi:auto-fix"

    def __init__(self, coordinator, entry: ConfigEntry, client) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_unique_id = f"{entry.entry_id}_band_auto"

    @property
    def is_on(self) -> bool:
        return not self._preferite

    async def async_turn_on(self, **kwargs) -> None:
        """Svuota la lista: il modem torna a scegliere da solo."""
        await self._scrivi([])

    async def async_turn_off(self, **kwargs) -> None:
        """Fissa la lista sulla banda in uso, cosi' lo spegnimento ha un effetto."""
        if self._preferite:
            return
        attuale = self._oggetto.get("INTF_Current_Band") or ""
        # "LTE_BC3" -> "B3"; "NR5G_N78" -> "n78"
        banda = attuale.replace("LTE_BC", "B").replace("NR5G_N", "n")
        supportate = split_list(self._oggetto.get(_SUPPORTATE))
        if banda not in supportate:
            _LOGGER.error(
                "Non so quale banda fissare (attuale %s): spuntale dal pannello", attuale
            )
            return
        await self._scrivi([banda])


class ZyxelBand(_Base):
    """Una banda: acceso = presente nella lista delle preferite."""

    _attr_icon = "mdi:radio-tower"

    def __init__(self, coordinator, entry: ConfigEntry, client, banda: str) -> None:
        super().__init__(coordinator, entry, client)
        self._banda = banda
        self._attr_name = f"Banda {banda}"
        self._attr_unique_id = f"{entry.entry_id}_band_{banda}"

    @property
    def is_on(self) -> bool:
        return self._banda in self._preferite

    async def async_turn_on(self, **kwargs) -> None:
        bande = self._preferite
        if self._banda in bande:
            return
        bande.append(self._banda)
        await self._scrivi(bande)

    async def async_turn_off(self, **kwargs) -> None:
        bande = self._preferite
        if self._banda not in bande:
            return
        if len(bande) == 1:
            _LOGGER.error(
                "Non spengo %s: e' l'ultima banda rimasta, resteresti senza linea",
                self._banda,
            )
            return
        bande.remove(self._banda)
        await self._scrivi(bande)


class ZyxelWifi(CoordinatorEntity, SwitchEntity):
    """La radio Wi-Fi del router (campo ``wlEnable``).

    Nome rete, banda e tipo di sicurezza stanno negli attributi invece che in
    sensori a parte: servono per leggerli, non per automatizzarci sopra. La
    password non compare da nessuna parte, nemmeno come attributo: finirebbe
    nello storico di Home Assistant. Si cambia col servizio ``imposta_wifi``.
    """

    _attr_has_entity_name = True
    _attr_name = "Wi-Fi"
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator, entry: ConfigEntry, client) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_wifi"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )

    @property
    def _oggetto(self) -> dict:
        return wlan_object(self.coordinator)

    @property
    def is_on(self) -> bool:
        return bool(self._oggetto.get("wlEnable"))

    @property
    def extra_state_attributes(self) -> dict:
        o = self._oggetto
        if not o:
            return {}
        return {
            "nome_rete": o.get("SSID"),
            "banda": o.get("band"),
            "canale": o.get("channel"),
            "sicurezza": o.get("SecurityMode"),
            "nascosta": o.get("wlHide"),
            "dispositivi_max": o.get("MaxAssociatedDevices"),
        }

    async def _accendi(self, acceso: bool) -> None:
        ok, messaggio = await self.hass.async_add_executor_job(
            self._client.write, {"wlEnable": acceso}, self._oggetto
        )
        if not ok:
            _LOGGER.error("Wi-Fi non cambiato: %s", messaggio)
            return
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._accendi(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._accendi(False)
