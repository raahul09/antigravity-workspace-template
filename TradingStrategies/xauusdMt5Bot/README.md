# XOS SMC EA - MQL5 Expert Advisor for XAUUSD

## Overview

**XOS SMC EA** is a production-ready MetaTrader 5 Expert Advisor implementing a Smart Money Concepts (SMC) liquidity sweep strategy for XAUUSD trading.

### Strategy Logic

1. **15M Timeframe**: Identifies swing highs and lows (liquidity pools) using a rolling window algorithm
2. **1M Timeframe**: Monitors price action for liquidity sweeps with CHoCH (Change of Character) confirmation
3. **Trend Filter**: 15M EMA(50) + RSI(14) confluence for directional bias
4. **Entry**: Triggered when price sweeps a swing level and closes back through it
5. **Risk Management**: Dynamic lot sizing based on account equity and configured risk %
6. **Exit**: Fixed R:R take profit + trailing stop activation

---

## Compilation Instructions

### Requirements
- MetaTrader 5 terminal installed
- MetaEditor (bundled with MT5)

### Steps

1. **Open MetaEditor**
   - Launch MT5 terminal
   - Press `F4` or click `Tools → MetaQuotes Language Editor`

2. **Open the EA Source**
   - In MetaEditor: `File → Open`
   - Navigate to: `TradingStrategies/xauusdMt5Bot/xos_smc_ea.mq5`

3. **Compile**
   - Press `F7` or click `Compile` button
   - Verify compilation succeeds with **0 errors**
   - Output file created: `xos_smc_ea.ex5`

4. **Locate Compiled EA**
   - Compiled `.ex5` file is automatically placed in:
     ```
     <MT5 Installation>/MQL5/Experts/xos_smc_ea.ex5
     ```
   - Or find via MetaEditor: `File → Open Data Folder → MQL5 → Experts`

---

## Deployment Instructions

### Step 1: Copy EA to MT5

If the compiled `.ex5` is not auto-deployed:

1. Copy `xos_smc_ea.ex5` from the build folder
2. Paste into your MT5 Experts directory:
   ```
   C:\Program Files\MetaTrader 5\MQL5\Experts\
   ```
   (Path may vary by installation)

3. Restart MT5 terminal or click `Navigator → Expert Advisors → Refresh`

### Step 2: Attach EA to Chart

1. Open MT5 terminal
2. Load **XAUUSD** chart (any timeframe, M15 recommended for visibility)
3. In Navigator panel, expand `Expert Advisors`
4. Drag `xos_smc_ea` onto the XAUUSD chart

### Step 3: Configure Parameters

In the EA settings dialog:

| Parameter | Default | Description |
|-----------|---------|-------------|
| **Magic Number** | 777888 | Unique ID to identify EA trades |
| **Symbol** | XAUUSD | Trading symbol |
| **Use Auto Login** | false | Use terminal's current session (recommended: true) |
| **Risk Per Trade (%)** | 5.0 | Account risk per trade |
| **R:R Target** | 0.2 | Take profit as multiple of SL (hyper-scalping) |
| **Swing Lookback** | 5 | Candles for swing point detection |
| **EMA Period** | 50 | Trend filter period |
| **RSI Overbought** | 55.0 | RSI threshold for bearish setups |
| **RSI Oversold** | 45.0 | RSI threshold for bullish setups |
| **Trailing Stop** | true | Enable trailing stops |
| **Trailing Activation R:R** | 1.0 | Profit level to activate trailing |

### Step 4: Enable AutoTrading

1. Click the **AutoTrading** button in MT5 toolbar (green/Red toggle)
2. Ensure it shows **Green** (enabled)
3. Verify EA icon appears in top-right of chart
4. Check `Experts` tab in Terminal window for logs

---

## Broker Requirements

### Symbol Naming
- Ensure your broker uses **XAUUSD** as the symbol name
- Some brokers use `GOLD`, `XAUUSDm`, or other variants
- Update `inpSymbol` parameter if needed

### Contract Specifications
- XAUUSD contract size: typically 100 oz per lot
- Tick size: 0.01 (varies by broker)
- Tick value: ~$1 per lot per tick (broker-dependent)

The EA auto-detects these via `SymbolInfo` functions.

---

## Testing & Validation

### Backtest Mode

1. Open MT5 **Strategy Tester** (`Ctrl+R`)
2. Select `xos_smc_ea` from EA dropdown
3. Symbol: `XAUUSD`
4. Timeframe: `M1` or `M15`
5. Date range: Select historical period
6. Mode: `Every tick based on real ticks` (most accurate)
7. Click **Start**

### Paper Trading (Demo)

1. Ensure demo account is selected in MT5
2. Attach EA with `inpRiskPercent` reduced (e.g., 1-2%)
3. Monitor `Experts` and `Journal` tabs for execution logs
4. Verify trades appear in `Toolbox → Trade` tab

### Live Trading

**WARNING**: Only deploy on live account after thorough backtesting + demo validation.

1. Fund account with appropriate capital
2. Start with reduced risk (`inpRiskPercent` = 1-2%)
3. Monitor first 20-50 trades before scaling risk
4. Review `Experts` log for any execution errors

---

## Troubleshooting

### EA Not Appearing in Navigator
- Verify `.ex5` file is in correct `Experts` folder
- Restart MT5 terminal
- Check file permissions

### Compilation Errors
- Open `.mq5` in MetaEditor
- Ensure all `#include` paths are valid (standard MQL5 libraries)
- Check for syntax errors in code

### No Trades Executing
- Verify `AutoTrading` is enabled (green)
- Check `Experts` log for setup detection messages
- Confirm market is open (not weekend/holiday)
- Validate RSI + trend conditions are met

### Order Rejected
- Check account margin requirements
- Verify lot size within broker limits
- Review slippage settings vs. broker execution

### Login Failed
- If using manual login, verify credentials in parameters
- Recommended: set `inpUseAutoLogin = true` and log into MT5 manually first

---

## Risk Warning

**Trading forex and commodities (XAUUSD) carries substantial risk of loss.**

- This EA implements an **aggressive** strategy (5% risk per trade)
- Past performance does not guarantee future results
- Always test on demo before live deployment
- Never risk capital you cannot afford to lose
- Monitor EA execution regularly
- Use appropriate position sizing and risk controls

---

## Support & Logs

### Log Location
- EA logs to MT5 `Experts` tab
- Detailed trade execution in `Journal` tab
- Chart comments displayed when `inpShowChartComments = true`

### Key Log Messages
- `[XOS SMC] SWEEP DETECTED!` - Setup identified
- `[XOS SMC] BUY/SELL order successful` - Trade executed
- `[XOS SMC] Order failed` - Execution error (check retcode)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.00 | 2026-03-23 | Initial release |

---

**Built with MQL5 for MetaTrader 5**
