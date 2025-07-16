# TRADE_SUPERVISOR.PY

## Overview

The Trade Supervisor is a comprehensive monitoring and auto-stop system that has access to ALL data displayed in the trade monitor, including:

- **TTC (Time To Close)** - Current time remaining until market close
- **Live Symbol Price** - Real-time BTC price
- **Momentum Scores** - Weighted momentum calculations from multiple timeframes
- **Volatility Scores** - Composite volatility across multiple timeframes
- **Strike Table Data** - All strike information including:
  - Strike prices
  - Buffer values
  - B/M (Buy/Move) percentages
  - Probability calculations
  - Current YES/NO prices
  - DIFF calculations (PROB - YES_PRICE)
- **Open Trades** - Full access to TRADES.DB for currently open positions

## Core Functionality

### 1. Continuous Data Monitoring
The supervisor runs continuously and updates all data sources every second:
- Core market data (BTC price, TTC, momentum, volatility)
- Strike table data with probabilities and market prices
- Open trades from the database
- Volatility data across multiple timeframes

### 2. Auto-Stop Execution
When enabled, the supervisor can automatically close trades based on preset criteria:
- **Loss Threshold** - Close if loss exceeds specified percentage
- **Momentum Threshold** - Close if momentum exceeds threshold
- **Volatility Threshold** - Close if volatility exceeds threshold
- **Holding Time** - Close after specified time period
- **Profit Target** - Close when profit reaches target
- **Drawdown Protection** - Close to prevent excessive drawdown

### 3. Real-Time Data Synchronization
The supervisor maintains real-time access to all trading data and can make informed decisions based on current market conditions.

## Installation & Setup

### 1. Prerequisites
- Python 3.7+
- Required packages: `requests`, `sqlite3`, `logging`
- Running Flask server (main.py) on localhost:5000

### 2. Configuration
Edit `trade_supervisor_config.json` to configure:
- Update intervals
- Auto-stop criteria
- Logging preferences
- Monitoring settings

### 3. Testing
Run the test script to verify data access:
```bash
cd backend
python test_trade_supervisor.py
```

### 4. Running the Supervisor
```bash
cd backend
python trade_supervisor.py
```

## Data Access Verification

The supervisor accesses data through the following endpoints:

### Core Data (`/core`)
- BTC price
- TTC (Time To Close)
- Momentum deltas (1m, 2m, 3m, 4m, 15m, 30m)
- Volatility scores

### Strike Probabilities (`/api/strike_probabilities`)
- Strike-specific probability calculations
- Buffer and B/M values
- Momentum-aware calculations

### Kalshi Market Data (`/kalshi_market_snapshot`)
- Current YES/NO prices
- Market liquidity data

### Volatility Data (`/api/composite_volatility_score`)
- Composite volatility scores
- Multi-timeframe analysis

### Open Trades (Direct DB Access)
- Direct access to `trades.db`
- Real-time trade status monitoring

## Auto-Stop Criteria

### Basic Criteria
- **max_loss_percent**: Maximum loss percentage before auto-close
- **max_holding_time_minutes**: Maximum time to hold a position
- **momentum_threshold**: Momentum level that triggers auto-close
- **volatility_threshold**: Volatility level that triggers auto-close

### Advanced Criteria
- **momentum_reversal_threshold**: Momentum reversal detection
- **volatility_spike_threshold**: Volatility spike detection
- **price_gap_threshold**: Price gap detection
- **time_decay_threshold**: Time decay consideration

## Configuration Examples

### Conservative Auto-Stop
```json
{
  "auto_stop": {
    "enabled": true,
    "criteria": {
      "max_loss_percent": 30.0,
      "momentum_threshold": 10.0,
      "volatility_threshold": 0.7
    }
  }
}
```

### Aggressive Auto-Stop
```json
{
  "auto_stop": {
    "enabled": true,
    "criteria": {
      "max_loss_percent": 60.0,
      "momentum_threshold": 20.0,
      "volatility_threshold": 0.9
    }
  }
}
```

## Logging

The supervisor logs to:
- `backend/logs/trade_supervisor.log` - General supervisor logs
- `backend/logs/auto_stop_events.log` - Auto-stop execution events

### Log Levels
- **INFO**: General operation information
- **DEBUG**: Detailed data updates
- **ERROR**: Error conditions and failures

## Status Monitoring

The supervisor provides comprehensive status reports including:
- Running status
- Auto-stop configuration
- Data access status
- Trade monitoring status
- Volatility monitoring status

## Integration with Existing System

The supervisor is designed to work alongside the existing trading system:
- **Non-intrusive**: Only monitors and closes trades, doesn't interfere with opening
- **Configurable**: Can be enabled/disabled without system restart
- **Logging**: Comprehensive logging for audit trails
- **Real-time**: Updates every second for immediate response

## Safety Features

### Data Validation
- Validates all data before making decisions
- Handles missing or invalid data gracefully
- Logs data quality issues

### Error Handling
- Comprehensive exception handling
- Graceful degradation on API failures
- Automatic retry mechanisms

### Audit Trail
- All auto-stop events are logged with full context
- Includes market conditions at time of execution
- Maintains trade history integrity

## Future Enhancements

### Planned Features
1. **Machine Learning Integration** - ML-based stop criteria
2. **Advanced Risk Management** - Portfolio-level risk controls
3. **Performance Analytics** - Auto-stop effectiveness tracking
4. **Web Interface** - Real-time monitoring dashboard
5. **Alert System** - Email/SMS notifications for critical events

### Customization Options
1. **Strategy-Specific Stops** - Different criteria per trading strategy
2. **Market Condition Adaptation** - Dynamic criteria based on market state
3. **Time-Based Rules** - Different criteria for different market hours
4. **Correlation Analysis** - Multi-asset correlation considerations

## Troubleshooting

### Common Issues

1. **Data Access Failures**
   - Verify Flask server is running on localhost:5000
   - Check network connectivity
   - Verify database file permissions

2. **Auto-Stop Not Triggering**
   - Check auto-stop is enabled in config
   - Verify criteria thresholds are appropriate
   - Check log files for error messages

3. **Performance Issues**
   - Adjust update_interval in config
   - Reduce logging verbosity
   - Check system resources

### Debug Mode
Enable debug logging by setting log_level to "DEBUG" in config:
```json
{
  "supervisor": {
    "log_level": "DEBUG"
  }
}
```

## Support

For issues or questions:
1. Check the log files for error messages
2. Run the test script to verify data access
3. Review the configuration settings
4. Check system requirements and dependencies

The Trade Supervisor provides a robust foundation for automated trade management while maintaining full visibility into all trading data and market conditions. 