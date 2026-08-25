"""
QCAlgorithm 基类

提供 QuantConnect 风格的策略开发接口
"""

from datetime import datetime
from typing import Dict, Optional

from common.logger import log
from common.models import Order
from data.ibkr_client import IBKRClient
from strategy.portfolio import SecurityPortfolioManager
from strategy.resolution import Resolution
from trading.order.manager import OrderManager
from trading.position.manager import PositionManager


class QCAlgorithm:
    """
    策略基类

    提供 QuantConnect 风格的 API：
    - Initialize() / OnData() / OnOrderEvent() 生命周期
    - AddEquity() / MarketOrder() / LimitOrder() 交易 API
    - Portfolio / Securities 持仓 API

    使用方式：
    ```python
    class MyStrategy(QCAlgorithm):
        def Initialize(self):
            self.AddEquity("AAPL", Resolution.Minute)

        def OnData(self, data):
            self.MarketOrder("AAPL", 100)
    ```
    """

    def __init__(self, ibkr_client: IBKRClient, order_manager: OrderManager, position_manager: PositionManager):
        """
        初始化策略

        Args:
            ibkr_client: IBKR 客户端
            order_manager: 订单管理器
            position_manager: 持仓管理器
        """
        self._ibkr_client = ibkr_client
        self._order_manager = order_manager
        self._position_manager = position_manager

        # 投资组合
        self.Portfolio = SecurityPortfolioManager(position_manager)

        # 订阅的股票
        self._securities: Dict[str, Resolution] = {}

        # 指标管理
        self._indicators: Dict[str, list] = {}  # {symbol: [indicators]}

        # 策略状态
        self._initialized = False

        # 注册订单成交回调
        self._order_manager.register_filled_callback(self._on_order_filled_internal)

    # ==================== 生命周期方法 ====================

    def Initialize(self):
        """
        策略初始化

        在此方法中：
        - 添加股票：self.AddEquity("AAPL")
        - 创建指标：self.SMA("AAPL", 20)
        - 设置参数

        子类必须重写此方法
        """
        raise NotImplementedError("Subclass must implement Initialize()")

    def OnData(self, data: Dict):
        """
        行情数据事件

        当新的行情数据到达时调用

        Args:
            data: 行情数据字典 {symbol: bar}

        子类可以重写此方法
        """
        pass

    def OnOrderEvent(self, order_event: Order):
        """
        订单事件

        当订单状态变化时调用（提交、成交、取消等）

        Args:
            order_event: 订单对象

        子类可以重写此方法
        """
        pass

    # ==================== 股票管理 API ====================

    def AddEquity(self, symbol: str, resolution: Resolution = Resolution.Minute):
        """
        添加股票

        Args:
            symbol: 股票代码
            resolution: 数据分辨率

        Returns:
            Security 对象（未实现）
        """
        self._securities[symbol] = resolution
        log.info(f"Added equity: {symbol} ({resolution})")

        # TODO: 订阅实时数据
        # self._data_manager.subscribe(symbol, resolution)

    # ==================== 交易 API ====================

    def MarketOrder(self, symbol: str, quantity: int) -> Optional[Order]:
        """
        市价单

        Args:
            symbol: 股票代码
            quantity: 数量（正数买入，负数卖出）

        Returns:
            订单对象
        """
        action = "BUY" if quantity > 0 else "SELL"
        quantity = abs(quantity)

        log.info(f"Market order: {action} {quantity} {symbol}")

        order = self._order_manager.create_market_order(symbol=symbol, quantity=quantity, action=action)

        return order

    def LimitOrder(self, symbol: str, quantity: int, limit_price: float) -> Optional[Order]:
        """
        限价单

        Args:
            symbol: 股票代码
            quantity: 数量（正数买入，负数卖出）
            limit_price: 限价

        Returns:
            订单对象
        """
        action = "BUY" if quantity > 0 else "SELL"
        quantity = abs(quantity)

        log.info(f"Limit order: {action} {quantity} {symbol} @ ${limit_price}")

        order = self._order_manager.create_limit_order(
            symbol=symbol, quantity=quantity, limit_price=limit_price, action=action
        )

        return order

    def Liquidate(self, symbol: str) -> Optional[Order]:
        """
        平仓

        Args:
            symbol: 股票代码

        Returns:
            订单对象
        """
        holding = self.Portfolio[symbol]

        if not holding.Invested:
            log.warning(f"No position to liquidate: {symbol}")
            return None

        quantity = int(abs(holding.Quantity))
        action = "SELL" if holding.Quantity > 0 else "BUY"

        log.info(f"Liquidating {symbol}: {action} {quantity}")

        order = self._order_manager.create_market_order(symbol=symbol, quantity=quantity, action=action)

        return order

    # ==================== 历史数据 API ====================

    def History(self, symbol: str, periods: int, resolution: Resolution = Resolution.Daily) -> Optional["pd.DataFrame"]:
        """
        获取历史数据

        Args:
            symbol: 股票代码
            periods: 周期数
            resolution: 数据分辨率

        Returns:
            历史数据 DataFrame
        """
        try:
            from data.historical.provider import HistoricalDataProvider

            provider = HistoricalDataProvider()
            df = provider.get_latest_bars(symbol, periods, resolution)

            if df.empty:
                log.warning(f"No history data for {symbol}")

            return df

        except Exception as e:
            log.error(f"Error getting history: {e}")
            return None

    # ==================== 技术指标 API ====================

    def SMA(self, symbol: str, period: int, resolution: Resolution = Resolution.Daily):
        """
        创建简单移动平均指标

        Args:
            symbol: 股票代码
            period: 周期
            resolution: 数据分辨率

        Returns:
            SMA 指标对象
        """
        from strategy.indicators import SimpleMovingAverage

        indicator = SimpleMovingAverage(f"SMA({symbol},{period})", period)

        # 预热指标
        self._warmup_indicator(symbol, indicator, resolution)

        # 注册到自动更新列表
        if symbol not in self._indicators:
            self._indicators[symbol] = []
        self._indicators[symbol].append(indicator)

        log.info(f"Created indicator: {indicator.Name}")

        return indicator

    def EMA(self, symbol: str, period: int, resolution: Resolution = Resolution.Daily):
        """
        创建指数移动平均指标

        Args:
            symbol: 股票代码
            period: 周期
            resolution: 数据分辨率

        Returns:
            EMA 指标对象
        """
        from strategy.indicators import ExponentialMovingAverage

        indicator = ExponentialMovingAverage(f"EMA({symbol},{period})", period)

        # 预热指标
        self._warmup_indicator(symbol, indicator, resolution)

        # 注册到自动更新列表
        if symbol not in self._indicators:
            self._indicators[symbol] = []
        self._indicators[symbol].append(indicator)

        log.info(f"Created indicator: {indicator.Name}")

        return indicator

    def _warmup_indicator(self, symbol: str, indicator, resolution: Resolution):
        """
        预热指标

        从数据库加载历史数据，填充指标

        Args:
            symbol: 股票代码
            indicator: 指标对象
            resolution: 数据分辨率
        """
        try:
            from data.historical.provider import HistoricalDataProvider

            provider = HistoricalDataProvider()

            # 获取足够的历史数据（周期 + 10 buffer）
            required_bars = indicator.Period + 10
            history = provider.get_latest_bars(symbol, required_bars, resolution)

            if history.empty:
                log.warning(f"No history data for warming up {indicator.Name}")
                return

            # 用历史数据预热
            for timestamp, row in history.iterrows():
                indicator.Update(timestamp, float(row["close"]))

            if indicator.IsReady:
                log.info(
                    f"Warmed up {indicator.Name} with {len(history)} bars, current value: {indicator.Current.Value:.2f}"
                )
            else:
                log.warning(f"{indicator.Name} not ready after warmup ({indicator.Samples}/{indicator.Period})")

        except Exception as e:
            log.error(f"Error warming up indicator: {e}", exc_info=True)

    # ==================== 内部方法 ====================

    def _on_order_filled_internal(self, order: Order):
        """
        订单成交内部回调

        转发到用户的 OnOrderEvent()

        Args:
            order: 成交的订单
        """
        try:
            self.OnOrderEvent(order)
        except Exception as e:
            log.error(f"Error in OnOrderEvent: {e}", exc_info=True)

    def _run_initialize(self):
        """运行初始化"""
        if self._initialized:
            log.warning("Algorithm already initialized")
            return

        try:
            log.info(f"Initializing strategy: {self.__class__.__name__}")
            self.Initialize()
            self._initialized = True
            log.info("Strategy initialized successfully")
        except Exception as e:
            log.error(f"Error initializing strategy: {e}", exc_info=True)
            raise

    def _process_data(self, data: Dict):
        """
        处理行情数据

        Args:
            data: 行情数据
        """
        if not self._initialized:
            log.warning("Strategy not initialized")
            return

        try:
            # 自动更新所有指标
            for symbol, bar in data.items():
                if symbol in self._indicators:
                    for indicator in self._indicators[symbol]:
                        # 假设 bar 有 timestamp 和 close 属性
                        indicator.Update(bar.get("timestamp", datetime.now()), float(bar.get("close", 0)))

            # 调用用户的 OnData
            self.OnData(data)

        except Exception as e:
            log.error(f"Error in OnData: {e}", exc_info=True)

    # ==================== 属性 ====================

    @property
    def Time(self) -> datetime:
        """当前时间"""
        return datetime.now()

    @property
    def IsWarmingUp(self) -> bool:
        """是否在预热期"""
        # TODO: 实现预热逻辑
        return False
