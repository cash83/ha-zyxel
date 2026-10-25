"""Due sensori per il traffico consumato sulla SIM.

L'OID ``Traffic_Status`` porta 15 contatori per ognuna delle nove interfacce del
router: 135 numeri per sapere quanti giga sono passati. Qui se ne tengono due,
presi dall'interfaccia del modem che ha davvero traffico (``rmnet_data0`` su
questo apparecchio, ma la si sceglie guardando i byte invece di darla per
scontata: dopo un riaggancio il portante puo' spostarsi su un'altra).

I contatori del router **ripartono da zero a ogni riavvio**: ``TOTAL_INCREASING``
dice a Home Assistant di trattare un calo come un azzeramento, cosi' le
statistiche a lungo termine restano giuste.

Sopra ci stanno altri due sensori che tengono il conto del **mese**: sommano le
differenze fra una lettura e l'altra, riconoscono l'azzeramento del router
(lettura piu' bassa della precedente = e' ripartito, il nuovo valore e' tutto
traffico nuovo) e si ricordano il totale anche se Home Assistant si riavvia.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Le interfacce del modem si chiamano tutte cosi'; bridge* e br0 sono la LAN.
_PREFISSO_WAN = "rmnet_data"


def _interfaccia_wan(coordinator: Any) -> tuple[str | None, dict[str, Any]]:
    """Interfaccia del modem con piu' byte ricevuti, e i suoi contatori."""
    dati = (getattr(coordinator, "data", None) or {}).get("traffic") or {}
    if not isinstance(dati, dict):
        return None, {}

    scelta: str | None = None
    massimo = -1
    contatori: dict[str, Any] = {}
    for nome, stato in dati.items():
        if not nome or not nome.startswith(_PREFISSO_WAN) or not isinstance(stato, dict):
            continue
        try:
            ricevuti = int(stato.get("BytesReceived") or 0)
        except (TypeError, ValueError):
            continue
        if ricevuti > massimo:
            scelta, massimo, contatori = nome, ricevuti, stato
    return scelta, contatori


def sensori_traffico(coordinator: Any, entry: ConfigEntry) -> list[SensorEntity]:
    """I due sensori, se il router sta dando i dati del traffico."""
    interfaccia, _ = _interfaccia_wan(coordinator)
    if interfaccia is None:
        return []
    return [
        ZyxelDati(coordinator, entry, "BytesReceived", "Dati scaricati", "scaricati"),
        ZyxelDati(coordinator, entry, "BytesSent", "Dati inviati", "inviati"),
        ZyxelDatiMese(
            coordinator, entry, "BytesReceived", "Dati scaricati nel mese", "scaricati"
        ),
        ZyxelDatiMese(
            coordinator, entry, "BytesSent", "Dati inviati nel mese", "inviati"
        ),
    ]


class ZyxelDati(CoordinatorEntity, SensorEntity):
    """Byte passati sull'interfaccia del modem da quando il router e' acceso."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    # Megabyte come punto di partenza: in gigabyte un consumo di pochi MB si
    # legge '0.01'. Home Assistant tiene un'unita' fissa per sensore, ma la si
    # cambia dalle impostazioni dell'entita' (B, kB, MB, GB, TB).
    _attr_suggested_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        campo: str,
        nome: str,
        suffisso: str,
    ) -> None:
        super().__init__(coordinator)
        self._campo = campo
        self._attr_name = nome
        self._attr_icon = (
            "mdi:download-network" if campo == "BytesReceived" else "mdi:upload-network"
        )
        self._attr_unique_id = f"{entry.entry_id}_dati_{suffisso}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )

    @property
    def native_value(self) -> int | None:
        _, contatori = _interfaccia_wan(self.coordinator)
        try:
            return int(contatori.get(self._campo))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        interfaccia, contatori = _interfaccia_wan(self.coordinator)
        if interfaccia is None:
            return {}
        pacchetti = (
            "PacketsReceived" if self._campo == "BytesReceived" else "PacketsSent"
        )
        errori = "ErrorsReceived" if self._campo == "BytesReceived" else "ErrorsSent"
        return {
            "interfaccia": interfaccia,
            "pacchetti": contatori.get(pacchetti),
            "errori": contatori.get(errori),
        }


class ZyxelDatiMese(CoordinatorEntity, RestoreSensor):
    """Byte passati dall'inizio del mese, a prova di riavvio.

    Il contatore del router non ricorda niente oltre l'accensione, quindi la
    somma la si tiene qui: a ogni lettura si aggiunge la differenza con la
    precedente, e se la lettura e' **calata** vuol dire che il router e'
    ripartito, percio' il nuovo valore conta tutto come traffico nuovo.
    """

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.BYTES
    # Megabyte come punto di partenza: in gigabyte un consumo di pochi MB si
    # legge '0.01'. Home Assistant tiene un'unita' fissa per sensore, ma la si
    # cambia dalle impostazioni dell'entita' (B, kB, MB, GB, TB).
    _attr_suggested_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        campo: str,
        nome: str,
        suffisso: str,
    ) -> None:
        super().__init__(coordinator)
        self._campo = campo
        self._attr_name = nome
        self._attr_icon = (
            "mdi:download-network-outline"
            if campo == "BytesReceived"
            else "mdi:upload-network-outline"
        )
        self._attr_unique_id = f"{entry.entry_id}_dati_mese_{suffisso}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )
        self._totale: int = 0
        self._ultimo: int | None = None
        self._mese: str | None = None
        self._azzeramenti: int = 0

    async def async_added_to_hass(self) -> None:
        """Riprende il conto da dove l'aveva lasciato prima del riavvio di HA.

        Il totale si rilegge con ``async_get_last_sensor_data`` e NON dallo
        stato: lo stato e' gia' convertito nell'unita' mostrata (gigabyte), e
        riprenderlo da li' come se fossero byte azzererebbe il conto a ogni
        riavvio di Home Assistant.
        """
        await super().async_added_to_hass()
        salvati = await self.async_get_last_sensor_data()
        if salvati is not None and salvati.native_value is not None:
            try:
                self._totale = int(float(salvati.native_value))
            except (TypeError, ValueError):
                self._totale = 0

        vecchio = await self.async_get_last_state()
        if vecchio is not None:
            attributi = vecchio.attributes or {}
            self._mese = attributi.get("mese")
            self._azzeramenti = int(attributi.get("azzeramenti") or 0)
            ultimo = attributi.get("ultima_lettura")
            try:
                self._ultimo = int(ultimo) if ultimo is not None else None
            except (TypeError, ValueError):
                self._ultimo = None
        self._aggiorna()

    def _aggiorna(self) -> None:
        """Somma il pezzo di traffico nuovo e gestisce il cambio di mese."""
        _, contatori = _interfaccia_wan(self.coordinator)
        try:
            grezzo = int(contatori.get(self._campo))
        except (TypeError, ValueError):
            return

        mese = dt_util.now().strftime("%Y-%m")
        if self._mese != mese:
            self._mese = mese
            self._totale = 0
            self._azzeramenti = 0
            self._ultimo = grezzo
            return

        if self._ultimo is None:
            self._ultimo = grezzo
            return

        if grezzo < self._ultimo:
            # Il router e' ripartito: quel che c'e' adesso e' tutto nuovo.
            self._totale += grezzo
            self._azzeramenti += 1
        else:
            self._totale += grezzo - self._ultimo
        self._ultimo = grezzo

    def _handle_coordinator_update(self) -> None:
        self._aggiorna()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> int:
        return self._totale

    @property
    def last_reset(self):
        """Inizio del mese: serve alle statistiche a lungo termine."""
        if not self._mese:
            return None
        anno, mese = self._mese.split("-")
        return dt_util.start_of_local_day(
            dt_util.now().replace(year=int(anno), month=int(mese), day=1)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        interfaccia, _ = _interfaccia_wan(self.coordinator)
        return {
            "mese": self._mese,
            "ultima_lettura": self._ultimo,
            "azzeramenti": self._azzeramenti,
            "interfaccia": interfaccia,
        }

