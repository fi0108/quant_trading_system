"""
Core Integration Tests for Market Data Module

Tests the two most critical scenarios:
1. Real-time data write to PostgreSQL
2. Real-time data write to Redis

These tests require:
- IBKR Gateway/TWS running and logged in
- PostgreSQL database available
- Redis server running
- Currently in trading hours (pre-market, regular, or after-hours)
"""

import pytest
import psycopg2
import redis
from datetime import datetime, timedelta


@pytest.fixture
def db_connection():
    """PostgreSQL connection fixture."""
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='quant_trading',
        user='postgres',
        password='postgres'
    )
    yield conn
    conn.close()


@pytest.fixture
def redis_client():
    """Redis connection fixture."""
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    yield r
    r.close()


@pytest.mark.core
@pytest.mark.integration
@pytest.mark.realtime
def test_realtime_data_write_to_pg(db_connection):
    """
    Core Test 1: Verify real-time data writes to PostgreSQL

    Prerequisites:
    - Real-time data service is running
    - Currently in trading hours (pre-market/regular/after-hours)
    - Service has been running for at least 5 minutes

    Test Steps:
    1. Query PostgreSQL for recent data (last 5 minutes)
    2. Verify data exists
    3. Verify data fields are complete
    4. Verify session field is correctly set
    5. Verify timestamp is in UTC format
    """
    cursor = db_connection.cursor()

    # Query recent data (last 10 minutes to be safe)
    query = """
        SELECT COUNT(*) as count,
               MIN(timestamp) as earliest,
               MAX(timestamp) as latest
        FROM market_data_1min
        WHERE symbol = 'AAPL'
          AND timestamp > NOW() - INTERVAL '10 minutes'
    """

    cursor.execute(query)
    result = cursor.fetchone()
    count, earliest, latest = result

    # Assertion 1: Data exists
    assert count > 0, (
        f"No recent data found in PostgreSQL. "
        f"Make sure real-time service is running and has been running for at least 5 minutes. "
        f"Current query window: last 10 minutes"
    )

    print(f"✓ Found {count} bars in last 10 minutes")
    print(f"  Earliest: {earliest}")
    print(f"  Latest: {latest}")

    # Query detailed data to verify fields
    query_detail = """
        SELECT symbol, timestamp, open, high, low, close, volume, session, source
        FROM market_data_1min
        WHERE symbol = 'AAPL'
          AND timestamp > NOW() - INTERVAL '10 minutes'
        ORDER BY timestamp DESC
        LIMIT 5
    """

    cursor.execute(query_detail)
    rows = cursor.fetchall()

    # Assertion 2: Fields are complete
    for row in rows:
        symbol, timestamp, open_price, high, low, close, volume, session, source = row

        assert symbol is not None, "symbol field is NULL"
        assert timestamp is not None, "timestamp field is NULL"
        assert open_price is not None and open_price > 0, f"open price invalid: {open_price}"
        assert high is not None and high > 0, f"high price invalid: {high}"
        assert low is not None and low > 0, f"low price invalid: {low}"
        assert close is not None and close > 0, f"close price invalid: {close}"
        assert volume is not None and volume >= 0, f"volume invalid: {volume}"

        # Assertion 3: Data quality (OHLC logic)
        assert high >= low, f"high ({high}) < low ({low})"
        assert high >= max(open_price, close), f"high ({high}) < max(open, close)"
        assert low <= min(open_price, close), f"low ({low}) > min(open, close)"

        print(f"✓ Bar validated: {timestamp} close={close:.2f} volume={volume} session={session}")

    # Assertion 4: Session field is set correctly
    query_session = """
        SELECT DISTINCT session
        FROM market_data_1min
        WHERE symbol = 'AAPL'
          AND timestamp > NOW() - INTERVAL '10 minutes'
    """

    cursor.execute(query_session)
    sessions = [row[0] for row in cursor.fetchall()]

    assert len(sessions) > 0, "No session data found"
    assert sessions[0] in ['pre_market', 'regular', 'after_hours'], (
        f"Invalid session value: {sessions[0]}. Expected one of: pre_market, regular, after_hours"
    )

    print(f"✓ Session field verified: {sessions[0]}")

    # Assertion 5: Timestamp is in UTC
    # PostgreSQL stores in UTC, verify it's recent (within last 10 minutes)
    now_utc = datetime.utcnow()
    age_seconds = (now_utc - latest).total_seconds()

    assert age_seconds < 600, (
        f"Latest timestamp is too old: {age_seconds:.0f} seconds ago. "
        f"Expected less than 600 seconds (10 minutes)"
    )

    print(f"✓ Timestamp is recent: {age_seconds:.0f} seconds ago")

    cursor.close()
    print("\n✅ PostgreSQL real-time write test PASSED")


@pytest.mark.core
@pytest.mark.integration
@pytest.mark.realtime
def test_realtime_data_write_to_redis(redis_client):
    """
    Core Test 2: Verify real-time data writes to Redis

    Prerequisites:
    - Real-time data service is running
    - Currently in trading hours
    - Service has been running for at least 5 minutes

    Test Steps:
    1. Check Redis key exists
    2. Verify data structure (list)
    3. Verify data count (should be <= 100)
    4. Verify data format (JSON)
    5. Verify latest data is recent
    """
    import json

    key = 'AAPL:latest_bars'

    # Assertion 1: Key exists
    assert redis_client.exists(key), (
        f"Redis key '{key}' does not exist. "
        f"Make sure real-time service is running and writing to Redis."
    )

    print(f"✓ Redis key exists: {key}")

    # Assertion 2: Data structure is list
    key_type = redis_client.type(key)
    assert key_type == 'list', f"Expected list type, got: {key_type}"

    print(f"✓ Data structure verified: {key_type}")

    # Assertion 3: Data count
    length = redis_client.llen(key)
    assert length > 0, "Redis list is empty"
    assert length <= 100, f"Redis list too long: {length} (expected <= 100)"

    print(f"✓ Data count: {length} bars (max 100)")

    # Assertion 4: Data format (JSON)
    latest_bar_json = redis_client.lindex(key, 0)
    assert latest_bar_json is not None, "No data at index 0"

    try:
        bar_data = json.loads(latest_bar_json)
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse JSON: {e}")

    # Verify required fields
    required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    for field in required_fields:
        assert field in bar_data, f"Missing required field: {field}"

    print(f"✓ JSON format verified with fields: {list(bar_data.keys())}")

    # Assertion 5: Latest data is recent
    timestamp_str = bar_data['timestamp']

    # Parse timestamp (ISO format)
    try:
        if 'T' in timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        pytest.fail(f"Failed to parse timestamp '{timestamp_str}': {e}")

    # Calculate age
    now = datetime.utcnow()
    if timestamp.tzinfo is not None:
        import pytz
        now = pytz.UTC.localize(now)

    age_seconds = (now - timestamp).total_seconds()

    assert age_seconds < 600, (
        f"Latest bar is too old: {age_seconds:.0f} seconds ago. "
        f"Expected less than 600 seconds (10 minutes)"
    )

    print(f"✓ Latest bar timestamp: {timestamp_str} ({age_seconds:.0f} seconds ago)")
    print(f"✓ Latest bar data: open={bar_data['open']} close={bar_data['close']} volume={bar_data['volume']}")

    print("\n✅ Redis real-time write test PASSED")


@pytest.mark.core
@pytest.mark.integration
def test_historical_data_sync():
    """
    Core Test 3: Verify historical data sync functionality

    This is a placeholder test that would verify:
    - Historical sync script can be executed
    - Data is written to correct table
    - Data count matches expected trading days

    Note: This test should be run separately after executing sync script manually
    """
    pytest.skip("This test requires manual execution of sync_historical_data.py script first")


# Helper functions for manual testing
def print_recent_pg_data(symbol='AAPL', minutes=5):
    """Helper function to print recent PostgreSQL data."""
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='quant_trading',
        user='postgres',
        password='postgres'
    )
    cursor = conn.cursor()

    query = f"""
        SELECT timestamp, open, high, low, close, volume, session
        FROM market_data_1min
        WHERE symbol = '{symbol}'
          AND timestamp > NOW() - INTERVAL '{minutes} minutes'
        ORDER BY timestamp DESC
        LIMIT 10
    """

    cursor.execute(query)
    rows = cursor.fetchall()

    print(f"\n=== Recent {symbol} data (last {minutes} minutes) ===")
    for row in rows:
        print(f"{row[0]} | O:{row[1]:.2f} H:{row[2]:.2f} L:{row[3]:.2f} C:{row[4]:.2f} V:{row[5]} | {row[6]}")

    cursor.close()
    conn.close()


def print_redis_data(symbol='AAPL', count=5):
    """Helper function to print Redis data."""
    import json
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

    key = f'{symbol}:latest_bars'
    length = r.llen(key)

    print(f"\n=== Redis {symbol} data (showing {count}/{length} bars) ===")

    for i in range(min(count, length)):
        bar_json = r.lindex(key, i)
        bar_data = json.loads(bar_json)
        print(f"{bar_data['timestamp']} | O:{bar_data['open']:.2f} C:{bar_data['close']:.2f} V:{bar_data['volume']}")

    r.close()


if __name__ == '__main__':
    """
    Run tests manually for debugging:

    python tests/integration/test_market_data_core.py
    """
    print("Running manual data checks...\n")

    try:
        print_recent_pg_data('AAPL', minutes=10)
    except Exception as e:
        print(f"PostgreSQL check failed: {e}")

    try:
        print_redis_data('AAPL', count=5)
    except Exception as e:
        print(f"Redis check failed: {e}")
