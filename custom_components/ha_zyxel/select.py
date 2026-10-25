"""Selettore della tecnologia di accesso (4G / 5G NSA / 5G SA / Auto)."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    if not band_object(coordinator):
        _LOGGER.debug("Nessun dato bande: selettore non creato")
        return
    async_add_entities([ZyxelAccessTechnology(coordinator, entry, dati["band_client"])])


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
