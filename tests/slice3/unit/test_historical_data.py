"""
历史数据单元测试
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest

from data.historical.downloader import HistoricalDataDownloader
from data.historical.provider import HistoricalDataProvider
from data.ibkr_client import IBKRClient
from strategy.resolution import Resolution
from tests.slice2.conftest import requires_database


@pytest.fixture
def mock_ibkr_client():
    """Mock IBKR 客户端"""
    client = Mock(spec=IBKRClient)
    client.is_connected = Mock(return_value=True)
    client.ib = Mock()
    client.ib.reqHistoricalData = Mock(return_value=[])
    return client


@pytest.fixture
def downloader(mock_ibkr_client):
    """创建下载器"""
    return HistoricalDataDownloader(mock_ibkr_client)


def test_downloader_initialization(downloader):
    """测试下载器初始化"""
    assert downloader.ibkr_client is not None
    assert downloader.MAX_BARS_PER_REQUEST == 2000


def test_get_duration_string(downloader):
    """测试获取下载时长"""
    assert downloader._get_duration_string(Resolution.Daily) == "1 Y"
    assert downloader._get_duration_string(Resolution.Hour) == "1 M"
    assert downloader._get_duration_string(Resolution.Minute) == "1 W"


def test_download_not_connected(mock_ibkr_client):
    """测试未连接时下载"""
    mock_ibkr_client.is_connected.return_value = False

    downloader = HistoricalDataDownloader(mock_ibkr_client)
    result = downloader.download("AAPL", "2024-01-01", "2024-01-31")

    assert result == 0


def test_download_chunk(downloader, mock_ibkr_client):
    """测试下载数据块"""
    # Mock 返回数据
    mock_bar = Mock()
    mock_bar.date = datetime(2024, 1, 1)
    mock_bar.open = 150.0
    mock_bar.high = 155.0
    mock_bar.low = 149.0
    mock_bar.close = 154.0
    mock_bar.volume = 1000000

    mock_ibkr_client.ib.reqHistoricalData.return_value = [mock_bar]

    # 下载
    from ib_insync import Stock

    contract = Stock("AAPL", "SMART", "USD")

    bars = downloader._download_chunk(
        contract=contract, end_datetime=datetime(2024, 1, 31), duration="1 M", bar_size="1 day", what_to_show="TRADES"
    )

    assert len(bars) == 1
    assert bars[0].close == 154.0


@requires_database
def test_provider_get_bar_count():
    """测试获取数据条数（需要数据库）"""
    provider = HistoricalDataProvider()

    # 这个需要数据库，可能返回0
    count = provider.get_bar_count("AAPL", Resolution.Daily)

    assert count >= 0


def test_provider_clear_cache():
    """测试清空缓存"""
    provider = HistoricalDataProvider()
    provider._cache["test"] = "data"

    provider.clear_cache()

    assert len(provider._cache) == 0


def test_provider_initialization():
    """测试 Provider 初始化"""
    provider = HistoricalDataProvider()

    assert provider._cache == {}


@requires_database
def test_provider_get_available_symbols():
    """测试获取可用股票列表（需要数据库）"""
    provider = HistoricalDataProvider()

    symbols = provider.get_available_symbols(Resolution.Daily)

    assert isinstance(symbols, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
