"""
检查下载的数据

查看小时线数据的时间范围
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.storage.models import BarModel, init_database
from strategy.resolution import Resolution

# 初始化数据库
init_database()

# 查询 AAPL 小时线数据
symbol = "AAPL"
bar_size = Resolution.Hour.bar_size

query = (
    BarModel.select()
    .where((BarModel.symbol == symbol) & (BarModel.bar_size == bar_size))
    .order_by(BarModel.timestamp.desc())
    .limit(20)
)

print(f"最新的 20 根 {symbol} 小时线：")
print("=" * 80)

for bar in query:
    print(f"{bar.timestamp} | O={bar.open:7.2f} H={bar.high:7.2f} L={bar.low:7.2f} C={bar.close:7.2f} V={bar.volume}")

print("=" * 80)
