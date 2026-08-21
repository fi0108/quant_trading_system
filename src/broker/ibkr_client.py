"""IBKR客户端封装

提供切片1风格的IBKR连接管理接口。
"""

import time
from datetime import datetime
from ib_insync import IB
from common.config import config
from common.logger import log
from common.models import ConnectionStatus


class IBKRClient:
    """IBKR客户端"""

    def __init__(self):
        self.ib = IB()
        self.status = ConnectionStatus(connected=False)
        
        self.host = config.get('ibkr', 'ibkr.host', '127.0.0.1')
        self.port = config.get('ibkr', 'ibkr.port', 4002)
        self.client_id = config.get('ibkr', 'ibkr.client_id', 1)
        self.timeout = config.get('ibkr', 'ibkr.timeout', 15)
        
        self.max_retries = 3
        self.retry_delay = 5
        
        self.reconnect_enabled = True
        self.max_reconnect_attempts = 10
        self.backoff_factor = 2
        self.initial_delay = 5
        
        self.ib.disconnectedEvent += self._on_disconnected

    def connect(self) -> bool:
        for attempt in range(1, self.max_retries + 1):
            try:
                log.info(f"Connecting to IBKR {self.host}:{self.port} (attempt {attempt}/{self.max_retries})")
                
                self.ib.connect(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=self.timeout
                )
                
                self.status.connected = True
                self.status.last_connect_time = datetime.now()
                self.status.reconnect_attempts = 0
                
                log.info("Connected to IBKR successfully")
                return True
                
            except Exception as e:
                log.error(f"Connection attempt {attempt} failed: {e}")
                if attempt < self.max_retries:
                    log.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        log.error(f"Failed to connect after {self.max_retries} attempts")
        return False

    def disconnect(self):
        if self.ib.isConnected():
            log.info("Disconnecting from IBKR...")
            self.ib.disconnect()
            self.status.connected = False
            self.status.last_disconnect_time = datetime.now()
            log.info("Disconnected")

    def is_connected(self) -> bool:
        return self.ib.isConnected()

    def _on_disconnected(self):
        self.status.connected = False
        self.status.last_disconnect_time = datetime.now()
        log.warning("Disconnected from IBKR")
        
        if self.reconnect_enabled:
            self._auto_reconnect()

    def _auto_reconnect(self):
        delay = self.initial_delay
        
        for attempt in range(1, self.max_reconnect_attempts + 1):
            self.status.reconnect_attempts = attempt
            log.info(f"Auto-reconnecting (attempt {attempt}/{self.max_reconnect_attempts})")
            
            time.sleep(delay)
            
            if self.connect():
                log.info("Auto-reconnect successful")
                return True
            
            delay = min(delay * self.backoff_factor, 60)
        
        log.error(f"Auto-reconnect failed after {self.max_reconnect_attempts} attempts")
        return False
