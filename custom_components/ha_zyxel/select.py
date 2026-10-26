"""Selettori: tecnologia di accesso e intervallo di autospegnimento Wi-Fi."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .autospegnimento import INTERVALLI, oggetto as oggetto_autooff
from .band_client import band_object, split_list
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_CAMPO = "INTF_Preferred_Access_Technology"
_SUPPORTATE = "INTF_Supported_Access_Technologies"
_RIPIEGO = ["Auto", "NR5G-SA", "NR5G-NSA", "LTE"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Crea il selettore della tecnologia."""
    dati = hass.data[DOMAIN][entry.entry_id]
    coordinator = dati["coordinator"]
    entita: list[SelectEntity] = []

    if band_object(coordinator):
        entita.append(ZyxelAccessTechnology(coordinator, entry, dati["band_client"]))
    else:
        _LOGGER.debug("Nessun dato bande: selettore non creato")

    if oggetto_autooff(coordinator):
        entita.append(
            ZyxelIntervalloAutoOff(coordinator, entry, dati["autooff_client"])
        )

    if entita:
        async_add_entities(entita)


class ZyxelAccessTechnology(CoordinatorEntity, SelectEntity):
    """Tecnologia di accesso preferita, letta e scritta su cellwan_band."""

    _attr_has_entity_name = True
    _attr_name = "Tecnologia preferita"
    _attr_icon = "mdi:signal-cellular-3"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, entry: ConfigEntry, client) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_access_technology"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )

    @property
    def options(self) -> list[str]:
        supportate = split_list(band_object(self.coordinator).get(_SUPPORTATE))
        return supportate or _RIPIEGO

    @property
    def current_option(self) -> str | None:
        valore = band_object(self.coordinator).get(_CAMPO)
        return valore if valore in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Scrive la nuova tecnologia e rilegge."""
        corrente = band_object(self.coordinator)
        ok, messaggio = await self.hass.async_add_executor_job(
            self._client.write, {_CAMPO: option}, corrente
        )
        if not ok:
            _LOGGER.error("Tecnologia non impostata: %s", messaggio)
            return
        await self.coordinator.async_request_refresh()


class ZyxelIntervalloAutoOff(CoordinatorEntity, SelectEntity):
    """Dopo quanti minuti il router spegne da solo il suo Wi-Fi.

    Zero vuol dire mai. Il valore vive in ``wifi_others.wlAutoOffIntvl`` e lo
    spegnimento vero e proprio avviene solo se ``wlAutoOffEnable`` e' acceso.
    """

    _attr_has_entity_name = True
    _attr_name = "Minuti prima di spegnere il Wi-Fi"
    _attr_icon = "mdi:timer-off-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(INTERVALLI)

    def __init__(self, coordinator, entry: ConfigEntry, client) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry.entry_id}_autooff_intervallo"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )

    @property
    def current_option(self) -> str | None:
        valore = oggetto_autooff(self.coordinator).get("wlAutoOffIntvl")
        if valore is None:
            return None
        testo = str(int(valore)) if str(valore).lstrip("-").isdigit() else str(valore)
        return testo if testo in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        corrente = oggetto_autooff(self.coordinator)
        ok, messaggio = await self.hass.async_add_executor_job(
            self._client.write, {"wlAutoOffIntvl": int(option)}, corrente
        )
        if not ok:
            _LOGGER.error("Intervallo non impostato: %s", messaggio)
            return
        await self.coordinator.async_request_refresh()

