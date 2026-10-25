"""Lettura della casella SMS (OID ``cellwan_sms``).

Il router consegna mittente e testo **impacchettati in GSM 7 bit** e spezza i
messaggi lunghi in piu' parti, ognuna con la sua intestazione UDH. Qui si
decodifica e si ricuce, cosi' in Home Assistant arrivano messaggi leggibili.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_ALFABETO = (
    "@£$¥èéùìòÇ\nØø\rÅå"
    "Δ_ΦΓΛΩΠΨΣΘΞ\x1b"
    "ÆæßÉ"
    " !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_ESTESO = {
    10: "\f", 20: "^", 40: "{", 41: "}", 47: "\\",
    60: "[", 61: "~", 62: "]", 64: "|", 101: "€",
}

# Quante voci tenere negli attributi: oltre a questo il database di HA si gonfia.
_MAX_MESSAGGI = 20


def _septetti(dati: bytes, salta: int = 0) -> str:
    """Spacchetta i septetti GSM, scartandone ``salta`` all'inizio."""
    bit = 0
    accumulatore = 0
    valori: list[int] = []
    for byte in dati:
        accumulatore |= byte << bit
        bit += 8
        while bit >= 7:
            valori.append(accumulatore & 0x7F)
            accumulatore >>= 7
            bit -= 7

    testo: list[str] = []
    escape = False
    for valore in valori[salta:]:
        if escape:
            testo.append(_ESTESO.get(valore, _ALFABETO[valore]))
            escape = False
        elif valore == 0x1B:
            escape = True
        else:
            testo.append(_ALFABETO[valore])
    return "".join(testo)


def _decodifica(esadecimale: str, udhi: bool) -> str:
    """Decodifica un campo, saltando l'intestazione UDH quando c'e'."""
    try:
        dati = bytes.fromhex(esadecimale or "")
    except ValueError:
        return esadecimale or ""
    if not dati:
        return ""
    if not udhi:
        return _septetti(dati)
    lunghezza_udh = dati[0] + 1           # il primo byte non conta se stesso
    salta = -(-lunghezza_udh * 8 // 7)    # septetti occupati dall'UDH
    return _septetti(dati, salta)


def _quando(grezzo: str) -> str:
    """"26/10/25,15:33:26+04" -> "2026-10-25 15:33:26" (il fuso e' in quarti d'ora)."""
    try:
        # Alcuni messaggi usano la virgola, altri lo spazio fra data e ora.
        testo = (grezzo or "").strip().replace(",", " ")
        data, ora = testo.split(None, 1)
        anno, mese, giorno = data.split("/")
        ora = ora.split("+")[0].split("-")[0].strip()
        return f"20{anno}-{mese}-{giorno} {ora}"
    except Exception:  # noqa: BLE001
        return grezzo


def _casella(coordinator: Any) -> dict[str, Any]:
    """Estrae l'oggetto SMS dai dati del coordinator, qualunque forma abbia."""
    dati = (getattr(coordinator, "data", None) or {}).get("sms")
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


def messaggi(coordinator: Any) -> list[dict[str, str]]:
    """Messaggi ricevuti, decodificati e ricuciti, dal piu' recente."""
    inbox = _casella(coordinator).get("SMS_Inbox") or []
    if not isinstance(inbox, list):
        return []

    pezzi: dict[Any, list[dict[str, Any]]] = {}
    for voce in inbox:
        if not isinstance(voce, dict):
            continue
        # I messaggi lunghi condividono MsgID; quelli singoli stanno per conto loro.
        chiave = voce.get("MsgID") if voce.get("UDHI") else ("solo", voce.get("MsgIndex"))
        pezzi.setdefault(chiave, []).append(voce)

    fuori: list[dict[str, str]] = []
    for gruppo in pezzi.values():
        gruppo.sort(key=lambda v: v.get("MsgSegmentSequence") or 0)
        primo = gruppo[0]
        testo = "".join(
            _decodifica(v.get("Content", ""), bool(v.get("UDHI"))) for v in gruppo
        )
        fuori.append(
            {
                "da": _decodifica(primo.get("From", ""), False),
                "quando": _quando(primo.get("TimeStamp", "")),
                "testo": testo.strip(),
                "parti": str(len(gruppo)),
                # Nelle caselle SMS lo stato codifica anche il verso:
                # 0/1 = ricevuto (non letto / letto), 2/3 = salvato / inviato.
                "stato": primo.get("State"),
                "inviato": primo.get("State") in (2, 3),
                # Servono per cancellarlo: un messaggio lungo occupa piu' voci.
                "indici": [
                    v.get("ObjIndex") for v in gruppo if v.get("ObjIndex") is not None
                ],
            }
        )

    fuori.sort(key=lambda m: m["quando"], reverse=True)
    return fuori[:_MAX_MESSAGGI]


class _Base(CoordinatorEntity, SensorEntity):
    """Parte comune delle entita' SMS."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Zyxel ({entry.data['host']})",
            manufacturer="Zyxel",
        )


class ZyxelSmsRicevuti(_Base):
    """Quanti messaggi ci sono, con l'elenco completo negli attributi."""

    _attr_name = "SMS ricevuti"
    _attr_icon = "mdi:message-text"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_sms_ricevuti"

    @property
    def native_value(self) -> int:
        return len(messaggi(self.coordinator))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        casella = _casella(self.coordinator)
        return {
            "messaggi": messaggi(self.coordinator),
            "spazio_usato": casella.get("SMS_UsedSpace"),
            "spazio_totale": casella.get("SMS_TotalSpace"),
        }


class ZyxelUltimoSms(_Base):
    """Il messaggio piu' recente: mittente nello stato, testo negli attributi."""

    _attr_name = "Ultimo SMS"
    _attr_icon = "mdi:message-arrow-left"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ultimo_sms"

    @property
    def native_value(self) -> str | None:
        elenco = messaggi(self.coordinator)
        # Lo stato di HA si ferma a 255 caratteri: qui ci sta il mittente.
        return elenco[0]["da"] if elenco else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        elenco = messaggi(self.coordinator)
        if not elenco:
            return {}
        return {
            "testo": elenco[0]["testo"],
            "quando": elenco[0]["quando"],
            "parti": elenco[0]["parti"],
        }
