from .ryanair        import RyanairClient
from .google_flights import GoogleFlightsClient
# Eurowings: Bearer-Token erforderlich
# easyJet:   alle Endpoints 404
# Condor:    Endpoint 404

ALL_AIRLINE_CLIENTS = [RyanairClient, GoogleFlightsClient]
