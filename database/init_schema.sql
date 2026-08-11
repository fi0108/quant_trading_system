-- Market Data Schema Initialization
-- Encoding: UTF-8

-- 1-minute bar data table
CREATE TABLE IF NOT EXISTS market_data_1min (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(10, 2) NOT NULL,
    high DECIMAL(10, 2) NOT NULL,
    low DECIMAL(10, 2) NOT NULL,
    close DECIMAL(10, 2) NOT NULL,
    volume BIGINT NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_symbol_time UNIQUE (symbol, timestamp)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_symbol_timestamp
ON market_data_1min(symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_timestamp
ON market_data_1min(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_source
ON market_data_1min(source);

CREATE INDEX IF NOT EXISTS idx_created_at
ON market_data_1min(created_at DESC);

-- Trading calendar table
CREATE TABLE IF NOT EXISTS trading_calendar (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    is_trading_day BOOLEAN NOT NULL,
    is_half_day BOOLEAN DEFAULT FALSE,
    market VARCHAR(10) DEFAULT 'NYSE',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calendar_date
ON trading_calendar(date DESC);

-- Backfill tasks table
CREATE TABLE IF NOT EXISTS backfill_tasks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INT DEFAULT 0,
    bars_filled INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_backfill_symbol
ON backfill_tasks(symbol);

CREATE INDEX IF NOT EXISTS idx_backfill_status
ON backfill_tasks(status);

-- Data quality log table
CREATE TABLE IF NOT EXISTS data_quality_log (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    check_date DATE NOT NULL,
    realtime_bars INT DEFAULT 0,
    historical_bars INT DEFAULT 0,
    difference_count INT DEFAULT 0,
    max_difference DECIMAL(10, 6) DEFAULT 0,
    corrected BOOLEAN DEFAULT FALSE,
    check_time TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quality_symbol_date
ON data_quality_log(symbol, check_date DESC);

-- Verify tables created
SELECT 'Tables created successfully!' AS status;
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('market_data_1min', 'trading_calendar', 'backfill_tasks', 'data_quality_log');
