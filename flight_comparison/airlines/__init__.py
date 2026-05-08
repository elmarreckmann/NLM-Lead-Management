from .ryanair   import RyanairClient
from .eurowings import EurowingsClient
from .easyjet   import EasyJetClient
from .condor    import CondorClient

ALL_AIRLINE_CLIENTS = [RyanairClient, EurowingsClient, EasyJetClient, CondorClient]
