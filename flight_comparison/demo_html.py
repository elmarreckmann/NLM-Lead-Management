"""Generate a demo HTML with fake data to preview the layout without running the full search."""

import pandas as pd
from exporter import export_html

DEMO_DATA = [
    ("DUS","2026-05-22","06:15","2026-05-29","14:30","Eurowings","ja",0,189.99,"Amadeus API","https://amadeus.com"),
    ("DUS","2026-05-22","11:05","2026-05-29","19:20","Ryanair","ja",0,204.50,"Skyscanner","https://skyscanner.de"),
    ("HAJ","2026-05-25","07:40","2026-06-01","16:55","TUIfly","ja",0,212.00,"Check24","https://flug.check24.de"),
    ("PAD","2026-05-18","09:00","2026-05-25","17:10","Ryanair","ja",0,219.90,"Kayak","https://kayak.de"),
    ("DUS","2026-06-03","14:20","2026-06-10","22:40","Lufthansa","nein",1,245.00,"Google Flights","https://google.com/flights"),
    ("HAJ","2026-06-01","06:55","2026-06-08","15:20","Eurowings","ja",0,251.50,"Amadeus API","https://amadeus.com"),
    ("DUS","2026-05-29","08:30","2026-06-05","17:00","Condor","ja",0,265.00,"Fluege.de","https://fluege.de"),
    ("PAD","2026-06-07","10:15","2026-06-14","19:45","Ryanair","ja",0,278.00,"Idealo","https://idealo.de"),
    ("HAJ","2026-06-12","07:30","2026-06-19","16:50","TUIfly","ja",0,289.99,"Duffel API","https://duffel.com"),
    ("DUS","2026-05-30","13:45","2026-06-06","22:10","Eurowings","nein",1,295.00,"Skyscanner","https://skyscanner.de"),
    ("PAD","2026-05-25","08:00","2026-06-01","17:30","Ryanair","ja",0,299.00,"Kayak","https://kayak.de"),
    ("DUS","2026-06-15","07:00","2026-06-22","16:20","Lufthansa","nein",2,312.50,"Google Flights","https://google.com/flights"),
]

cols = ["abflughafen","abflugdatum","abflugzeit","rueckflugdatum","rueckflugzeit",
        "airline","direktflug","zwischenstopps","preis_eur","quelle","buchungs_url"]

df = pd.DataFrame(DEMO_DATA, columns=cols)
df["abgerufen_am"] = "2026-05-08 12:00:00"

export_html(df, "flights_mallorca_DEMO.html")
print("Demo-HTML generiert: flights_mallorca_DEMO.html")
