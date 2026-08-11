"""
IBKR Client - High-level wrapper for Interactive Brokers API.

Provides simplified interface for:
- Historical data requests
- Real-time data subscription
- Connection management
"""

from typing import List, Dict, Optional, Callable
from datetime import datetime, timedelta
from ib_insync import IB, Stock, Contract, util
import asyncio
import logging

logger = logging.getLogger(__name__)


class IBKRClient:
    """
    High-level IBKR API client.

    Wraps ib_insync for easier usage:
    - Automatic connection management
    - Simplified data request interface
    - Real-time bar subscription
    """

    def __init__(self, host: str = '127.0.0.1', port: int = 7497, client_id: int = 1):
        """
        Initialize IBKR client.

        Args:
            host: IB Gateway/TWS host
            port: Port (7497 for TWS, 4001 for IB Gateway)
            client_id: Client ID
        """
        self.host = host
        self.port = port
        self.client_id = client_id

        self.ib = IB()
        self._is_connected = False

    async def connect_async(self) -> bool:
        """
        Connect to IB Gateway/TWS (async version).

        Returns:
            True if connection successful
        """
        try:
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=15
            )
            self._is_connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True

        except Exception as e:
            self._is_connected = False
            logger.error(f"Connection failed: {e}")
            return False

    def connect(self) -> bool:
        """
        Connect to IB Gateway/TWS (sync version).

        Returns:
            True if connection successful
        """
        try:
            # Try to get running loop
            try:
                loop = asyncio.get_running_loop()
                # In async context, can't use sync connect
                logger.error("Cannot use sync connect in async context. Use connect_async() instead.")
                return False
            except RuntimeError:
                # No running loop, safe to use sync connect
                self.ib.connect(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=15
                )
                self._is_connected = True
                logger.info(f"Connected to IBKR at {self.host}:{self.port}")
                return True

        except Exception as e:
            self._is_connected = False
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IB Gateway/TWS."""
        if self.ib.isConnected():
            self.ib.disconnect()
            self._is_connected = False
            logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._is_connected and self.ib.isConnected()

    async def get_historical_bars(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        bar_size: str = '1 day'
    ) -> List[Dict]:
        """
        Get historical bar data (async version).

        Args:
            symbol: Stock symbol
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            bar_size: Bar size ('1 min', '1 hour', '1 day', '1 week', '1 month')

        Returns:
            List of bar dictionaries with keys: timestamp, open, high, low, close, volume
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return []

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Calculate duration based on bar size
            duration_days = (end_date - start_date).days + 2  # +2 buffer

            if bar_size in ['1 min', '5 mins', '15 mins', '30 mins']:
                # Minute bars - use smaller duration
                if duration_days <= 1:
                    duration_str = '1 D'
                elif duration_days <= 7:
                    duration_str = f'{duration_days} D'
                else:
                    duration_str = f'{min(duration_days, 30)} D'  # Max 30 days for minute data
            elif bar_size == '1 hour':
                # Hourly bars
                if duration_days <= 30:
                    duration_str = f'{duration_days} D'
                else:
                    duration_str = f'{min(duration_days // 7 + 1, 52)} W'
            else:
                # Daily, weekly, monthly
                if duration_days <= 30:
                    duration_str = f'{duration_days} D'
                elif duration_days <= 365:
                    duration_str = f'{duration_days // 7 + 2} W'
                else:
                    duration_str = f'{duration_days // 365 + 1} Y'

            # Request historical data (async)
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime=end_date,
                durationStr=duration_str,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )

            # Convert and filter based on bar size
            result = []

            for bar in bars:
                bar_timestamp = bar.date

                # Determine if we should include this bar based on granularity
                include = False

                if bar_size in ['1 day', '1 week', '1 month']:
                    # Daily or coarser: filter by date only
                    if hasattr(bar_timestamp, 'date'):
                        bar_date = bar_timestamp.date()
                    else:
                        bar_date = bar_timestamp

                    include = bar_date >= start_date.date() and bar_date <= end_date.date()

                else:
                    # Intraday (minute/hour): filter by full datetime
                    if not hasattr(bar_timestamp, 'hour'):
                        # It's a date, convert to datetime
                        from datetime import datetime as dt
                        bar_timestamp = dt.combine(bar_timestamp, dt.min.time())

                    # Handle timezone comparison
                    if start_date.tzinfo:
                        if not (hasattr(bar_timestamp, 'tzinfo') and bar_timestamp.tzinfo):
                            # Localize naive bar_timestamp to same timezone as start_date
                            bar_timestamp = start_date.tzinfo.localize(bar_timestamp)

                    include = bar_timestamp >= start_date and bar_timestamp <= end_date

                if include:
                    bar_dict = {
                        'symbol': symbol,
                        'timestamp': bar.date,
                        'open': float(bar.open),
                        'high': float(bar.high),
                        'low': float(bar.low),
                        'close': float(bar.close),
                        'volume': int(bar.volume)
                    }
                    result.append(bar_dict)

            logger.info(f"Retrieved {len(result)} bars for {symbol} (filtered from {len(bars)} total)")
            return result

        except Exception as e:
            logger.error(f"Failed to get historical bars for {symbol}: {e}")
            return []

    def subscribe_realtime_bars(
        self,
        symbol: str,
        bar_size: str = '1 min',
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Subscribe to real-time bar data.

        Args:
            symbol: Stock symbol
            bar_size: Bar size (currently only '5 secs' and '1 min' supported by IBKR)
            callback: Callback function(symbol, bar_data) called on new bar

        Returns:
            True if subscription successful
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return False

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Subscribe to real-time bars
            # Note: IBKR only supports 5-second bars via reqRealTimeBars
            # For 1-minute bars, we need to use reqMktData instead
            if bar_size == '5 secs':
                bars = self.ib.reqRealTimeBars(
                    contract,
                    barSize=5,
                    whatToShow='TRADES',
                    useRTH=False  # Include extended hours
                )

                # Register callback
                if callback:
                    def on_bar_update(bars, hasNewBar):
                        if hasNewBar:
                            bar = bars[-1]
                            bar_data = {
                                'symbol': symbol,
                                'timestamp': bar.time,
                                'open': float(bar.open_),
                                'high': float(bar.high),
                                'low': float(bar.low),
                                'close': float(bar.close),
                                'volume': int(bar.volume)
                            }
                            callback(symbol, bar_data)

                    bars.updateEvent += on_bar_update

                logger.info(f"Subscribed to real-time bars for {symbol}")
                return True
            else:
                logger.warning(f"Bar size {bar_size} not directly supported, use reqMktData for tick data")
                return False

        except Exception as e:
            logger.error(f"Failed to subscribe to real-time bars for {symbol}: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
