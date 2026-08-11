"""
Connection module for IBKR Gateway management.
"""

from .state_machine import ConnectionState, ConnectionStateMachine
from .reconnect import ReconnectStrategy

__all__ = [
    'ConnectionState',
    'ConnectionStateMachine',
    'ReconnectStrategy'
]

# ConnectionManager requires ib_insync, imported separately to avoid dependency issues in tests
try:
    from .manager import ConnectionManager
    __all__.append('ConnectionManager')
except ImportError:
    pass
