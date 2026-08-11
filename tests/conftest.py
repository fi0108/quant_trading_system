"""
Pytest configuration and shared fixtures
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


# ============================================
# Markers
# ============================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (multiple components)"
    )
    config.addinivalue_line(
        "markers", "system: System tests (end-to-end with real services)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow running tests"
    )
    config.addinivalue_line(
        "markers", "requires_ibkr: Requires IBKR connection"
    )
    config.addinivalue_line(
        "markers", "requires_db: Requires database connection"
    )
    config.addinivalue_line(
        "markers", "requires_redis: Requires Redis connection"
    )


# ============================================
# Shared Fixtures
# ============================================

@pytest.fixture
def mock_ib_client():
    """Mock IB client for testing"""
    from unittest.mock import Mock
    return Mock()


@pytest.fixture
def sample_bar_data():
    """Sample bar data for testing"""
    from datetime import datetime
    return {
        'symbol': 'AAPL',
        'timestamp': datetime(2026, 8, 9, 9, 30, 0),
        'open': 150.0,
        'high': 151.0,
        'low': 149.5,
        'close': 150.5,
        'volume': 100000,
        'source': 'realtime'
    }


@pytest.fixture
def timezone_manager():
    """Timezone manager instance"""
    from src.core.timezone_manager import TimezoneManager
    return TimezoneManager()


@pytest.fixture
def trading_calendar():
    """Trading calendar instance"""
    from src.calendar.trading_calendar import TradingCalendar
    return TradingCalendar()
