from .ryanair import RyanairClient
from .easyjet import EasyJetClient
from .condor  import CondorClient
# EurowingsClient entfernt – api.eurowings.com erfordert Bearer-Token

ALL_AIRLINE_CLIENTS = [RyanairClient, EasyJetClient, CondorClient]
