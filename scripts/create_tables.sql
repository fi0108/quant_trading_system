-- Market Data Tables Creation Script
-- Creates tables for storing historical and real-time market data at multiple granularities

-- ============================================
-- 1-Minute Bar Data Table
-- ============================================
CREATE TABLE IF NOT EXISTS market_data_1min (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    session VARCHAR(20),  -- 'pre_market', 'regular', 'after_hours'
    source VARCHAR(20) DEFAULT 'unknown',  -- 'realtime', 'historical', 'backfill'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_1min_symbol_timestamp ON market_data_1min(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_1min_session ON market_data_1min(session) WHERE session IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_1min_created_at ON market_data_1min(created_at DESC);

COMMENT ON TABLE market_data_1min IS '1-minute bar data for intraday strategies';
COMMENT ON COLUMN market_data_1min.session IS 'Trading session: pre_market, regular, after_hours';
COMMENT ON COLUMN market_data_1min.source IS 'Data source: realtime, historical, backfill';

-- ============================================
-- 1-Hour Bar Data Table
-- ============================================
CREATE TABLE IF NOT EXISTS market_data_1hour (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    session VARCHAR(20),
    source VARCHAR(20) DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_1hour_symbol_timestamp ON market_data_1hour(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_1hour_created_at ON market_data_1hour(created_at DESC);

COMMENT ON TABLE market_data_1hour IS '1-hour bar data for intraday swing strategies';

-- ============================================
-- Daily Bar Data Table
-- ============================================
CREATE TABLE IF NOT EXISTS market_data_daily (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    source VARCHAR(20) DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_daily_symbol_timestamp ON market_data_daily(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_daily_created_at ON market_data_daily(created_at DESC);

COMMENT ON TABLE market_data_daily IS 'Daily bar data for short-to-medium term strategies';

-- ============================================
-- Weekly Bar Data Table
-- ============================================
CREATE TABLE IF NOT EXISTS market_data_weekly (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    source VARCHAR(20) DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_weekly_symbol_timestamp ON market_data_weekly(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_weekly_created_at ON market_data_weekly(created_at DESC);

COMMENT ON TABLE market_data_weekly IS 'Weekly bar data for medium-term trend strategies';

-- ============================================
-- Monthly Bar Data Table
-- ============================================
CREATE TABLE IF NOT EXISTS market_data_monthly (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    open DECIMAL(12, 4) NOT NULL,
    high DECIMAL(12, 4) NOT NULL,
    low DECIMAL(12, 4) NOT NULL,
    close DECIMAL(12, 4) NOT NULL,
    volume BIGINT NOT NULL,
    source VARCHAR(20) DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_monthly_symbol_timestamp ON market_data_monthly(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_monthly_created_at ON market_data_monthly(created_at DESC);

COMMENT ON TABLE market_data_monthly IS 'Monthly bar data for long-term trend strategies';

-- ============================================
-- Verification Queries
-- ============================================

-- Check table existence
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name LIKE 'market_data_%'
ORDER BY table_name;

-- Show indexes
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename LIKE 'market_data_%'
ORDER BY tablename, indexname;
