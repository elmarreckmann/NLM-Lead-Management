from .ryanair import RyanairClient
from .condor  import CondorClient
# EurowingsClient entfernt – api.eurowings.com erfordert Bearer-Token
# EasyJetClient entfernt – alle bekannten Endpoints liefern 404

ALL_AIRLINE_CLIENTS = [RyanairClient, CondorClient]
