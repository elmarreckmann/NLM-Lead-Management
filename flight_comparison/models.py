"""Data model for a single flight offer."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FlightOffer:
    abflughafen: str
    abflugdatum: str          # YYYY-MM-DD
    abflugzeit: str           # HH:MM  (leer wenn unbekannt)
    rueckflugdatum: str       # YYYY-MM-DD
    rueckflugzeit: str        # HH:MM  (leer wenn unbekannt)
    airline: str
    direktflug: str           # "ja" / "nein"
    zwischenstopps: int
    preis_eur: float
    quelle: str
    buchungs_url: str
    abgerufen_am: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def dedup_key(self) -> str:
        """Unique key to identify the same flight from different sources."""
        return (
            f"{self.abflughafen}|{self.abflugdatum}|{self.abflugzeit}|"
            f"{self.rueckflugdatum}|{self.rueckflugzeit}|"
            f"{self.airline}|{self.zwischenstopps}"
        )
