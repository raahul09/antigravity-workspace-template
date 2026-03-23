# MQL5 Expert Advisor Development Skill

## Overview

This skill provides patterns, conventions, and templates for developing MetaTrader 5 Expert Advisors (EAs) in MQL5.

---

## EA Structure Template

```mq5
//+------------------------------------------------------------------+
//|                                              <name>.mq5           |
//|                                   <description>                   |
//+------------------------------------------------------------------+
#property copyright "<author>"
#property version   "1.00"
#property strict

//--- Include standard libraries
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Trade objects
CTrade         trade;
CPositionInfo  position;
CAccountInfo   account;
CSymbolInfo    symbol;

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+

//--- Group: Category
input type   inpVariable      = default_value;     // Description

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+

//--- Declare globals

//+------------------------------------------------------------------+
//| Expert Initialization Function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Validate inputs
   //--- Initialize objects
   //--- Create indicators
   //--- Setup timer
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert Deinitialization Function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   //--- Cleanup: kill timer, release handles, clear comments
}

//+------------------------------------------------------------------+
//| Expert Tick Handler                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- Main strategy logic (called on every tick)
}

//+------------------------------------------------------------------+
//| Timer Handler                                                    |
//+------------------------------------------------------------------+
void OnTimer()
{
   //--- Periodic tasks
}

//+------------------------------------------------------------------+
//| Trade Event Handler                                              |
//+------------------------------------------------------------------+
void OnTrade()
{
   //--- Position/order updates
}
//+------------------------------------------------------------------+
```

---

## Input Parameter Conventions

### Naming Convention
- Prefix all inputs with `inp` (e.g., `inpRiskPercent`, `inpSymbol`)
- Use descriptive names with clear units in comments
- Group related parameters with comment headers

### Standard Parameter Groups

```mq5
//--- Account & Connection
input int      inpMagicNumber       = 123456;           // Magic number for trade ID
input string   inpSymbol            = "XAUUSD";         // Trading symbol
input bool     inpUseAutoLogin      = true;             // Use terminal session

//--- Risk Management
input double   inpRiskPercent       = 1.0;              // Risk per trade (%)
input int      inpMaxSlippage       = 10;               // Max slippage in points
input double   inpRewardToRisk      = 2.0;              // R:R target

//--- Strategy Settings
input int      inpIndicatorPeriod   = 14;               // Indicator lookback
input double   inpThreshold         = 50.0;             // Signal threshold

//--- Trailing Stop
input bool     inpUseTrailing       = true;             // Enable trailing
input double   inpTrailingStart     = 1.0;              // Activation R:R

//--- Timeframes
input ENUM_TIMEFRAMES inpTFSignal   = PERIOD_M15;       // Signal timeframe
input ENUM_TIMEFRAMES inpTFTrend    = PERIOD_H1;        // Trend filter TF

//--- Logging & Debug
input bool     inpEnableLogging     = true;             // Enable Print() logs
input bool     inpShowChartComments = true;             // Show chart info
```

---

## Standard Libraries

### Trade Module Classes
```mq5
#include <Trade\Trade.mqh>           // CTrade - order execution
#include <Trade\PositionInfo.mqh>    // CPositionInfo - position queries
#include <Trade\AccountInfo.mqh>     // CAccountInfo - account data
#include <Trade\SymbolInfo.mqh>      // CSymbolInfo - symbol properties
```

### Usage Pattern
```mq5
// Initialize in OnInit()
if(!symbol.Name(inpSymbol)) return INIT_FAILED;
symbol.Refresh();

trade.SetExpertMagicNumber(inpMagicNumber);
trade.SetDeviationInPoints(inpMaxSlippage);
trade.SetTypeFilling(ORDER_FILLING_IOC);
```

---

## Core Function Patterns

### Initialization (OnInit)
```mq5
int OnInit()
{
   // 1. Validate critical inputs
   if(inpRiskPercent <= 0 || inpRiskPercent > 100)
      return INIT_PARAMETERS_INCORRECT;

   // 2. Initialize symbol info
   if(!symbol.Name(inpSymbol))
      return INIT_FAILED;
   symbol.Refresh();

   // 3. Configure trade object
   trade.SetExpertMagicNumber(inpMagicNumber);
   trade.SetDeviationInPoints(inpMaxSlippage);

   // 4. Create indicator handles
   handleMA = iMA(inpSymbol, inpTF, inpPeriod, 0, MODE_SMA, PRICE_CLOSE);
   if(handleMA == INVALID_HANDLE)
      return INIT_FAILED;

   // 5. Setup arrays
   ArraySetAsSeries(buffer, true);

   // 6. Create timer (optional)
   EventSetTimer(60); // 60 second interval

   Log("EA initialized successfully");
   return INIT_SUCCEEDED;
}
```

### Deinitialization (OnDeinit)
```mq5
void OnDeinit(const int reason)
{
   EventKillTimer();

   // Release indicator handles
   if(handleMA != INVALID_HANDLE) IndicatorRelease(handleMA);

   // Clear chart
   if(inpShowChartComments) Comment("");

   Log("EA deinitialized. Reason: " + EnumToString(reason));
}
```

### Tick Handler (OnTick)
```mq5
void OnTick()
{
   // 1. Guard clauses
   if(!IsTradingAllowed()) return;
   if(!IsMarketOpen()) return;

   // 2. Get current data
   MqlTick tick;
   if(!SymbolInfoTick(inpSymbol, tick)) return;

   // 3. Get indicator values
   double maBuffer[];
   ArraySetAsSeries(maBuffer, true);
   CopyBuffer(handleMA, 0, 0, 2, maBuffer);

   // 4. Get candle data
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   CopyRates(inpSymbol, inpTF, 0, 100, rates);

   // 5. Run strategy logic
   CheckEntrySignals(tick, rates, maBuffer);

   // 6. Manage open positions
   if(inpUseTrailing) UpdateTrailingStops();

   // 7. Update display
   UpdateChartInfo(tick);
}
```

---

## Risk Management Patterns

### Dynamic Lot Size Calculation
```mq5
double CalculateLotSize(double slDistancePoints)
{
   double equity = account.Equity();
   double riskAmount = equity * (inpRiskPercent / 100.0);

   double tickValue = symbol.TickValue();
   double tickSize = symbol.TickSize();

   if(slDistancePoints <= 0 || tickSize <= 0)
      return symbol.VolumeMin();

   // Risk Amount = Lot * (SL_distance / tickSize) * tickValue
   double rawLot = riskAmount / ((slDistancePoints / tickSize) * tickValue);

   // Floor to volume step
   double volumeStep = symbol.VolumeStep();
   double lotSize = MathFloor(rawLot / volumeStep) * volumeStep;

   // Clamp to broker limits
   lotSize = MathMax(symbol.VolumeMin(), MathMin(lotSize, symbol.VolumeMax()));

   return NormalizeDouble(lotSize, 2);
}
```

### Order Execution with Validation
```mq5
void ExecuteTrade(int direction, double entryPrice, double slPrice, double tpPrice)
{
   double lotSize = CalculateLotSize(entryPrice - slPrice);

   // Validate lot size
   if(lotSize < symbol.VolumeMin() || lotSize > symbol.VolumeMax())
   {
      Log("ERROR: Invalid lot size");
      return;
   }

   // Normalize prices
   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   // Execute
   bool result;
   if(direction == 1)
      result = trade.Buy(lotSize, inpSymbol, entryPrice, slPrice, tpPrice, "Buy comment");
   else
      result = trade.Sell(lotSize, inpSymbol, entryPrice, slPrice, tpPrice, "Sell comment");

   if(result)
      Log("Order successful. Ticket: " + IntegerToString(trade.ResultOrder()));
   else
      Log("ERROR: Order failed. Retcode: " + IntegerToString(trade.ResultRetcode()));
}
```

---

## Trailing Stop Pattern

```mq5
void UpdateTrailingStops()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() != inpSymbol) continue;
      if(position.Magic() != inpMagicNumber) continue;

      double openPrice = position.PriceOpen();
      double currentSL = position.StopLoss();

      // Get current price
      double currentPrice;
      if(position.PositionType() == POSITION_TYPE_BUY)
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_BID);
      else
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_ASK);

      // Calculate profit in points
      double profitPoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         profitPoints = (currentPrice - openPrice) / symbol.TickSize();
      else
         profitPoints = (openPrice - currentPrice) / symbol.TickSize();

      // Check activation threshold
      if(profitPoints >= (inpTrailingStart * symbol.TicksStop()))
      {
         double newSL;
         if(position.PositionType() == POSITION_TYPE_BUY)
         {
            newSL = currentPrice - (inpTrailingStart * symbol.TickSize());
            if(newSL > currentSL)
               trade.PositionModify(position.Ticket(), newSL, position.TakeProfit());
         }
         else
         {
            newSL = currentPrice + (inpTrailingStart * symbol.TickSize());
            if(newSL < currentSL)
               trade.PositionModify(position.Ticket(), newSL, position.TakeProfit());
         }
      }
   }
}
```

---

## Indicator Handling Pattern

### Creating and Using Indicators
```mq5
// In OnInit()
handleEMA = iMA(inpSymbol, inpTF, inpPeriod, 0, MODE_EMA, PRICE_CLOSE);
handleRSI = iRSI(inpSymbol, inpTF, inpRsiPeriod, PRICE_CLOSE);

if(handleEMA == INVALID_HANDLE || handleRSI == INVALID_HANDLE)
   return INIT_FAILED;

// In OnTick()
double emaBuffer[], rsiBuffer[];
ArraySetAsSeries(emaBuffer, true);
ArraySetAsSeries(rsiBuffer, true);

CopyBuffer(handleEMA, 0, 0, 2, emaBuffer);
CopyBuffer(handleRSI, 0, 0, 1, rsiBuffer);

double currentEMA = emaBuffer[0];
double currentRSI = rsiBuffer[0];
```

### Cleanup in OnDeinit()
```mq5
void OnDeinit(const int reason)
{
   if(handleEMA != INVALID_HANDLE) IndicatorRelease(handleEMA);
   if(handleRSI != INVALID_HANDLE) IndicatorRelease(handleRSI);
}
```

---

## Data Retrieval Patterns

### CopyRates for Candle Data
```mq5
MqlRates rates[];
ArraySetAsSeries(rates, true); // Most recent first

int copied = CopyRates(inpSymbol, inpTF, 0, 100, rates);
if(copied < 100)
{
   Log("ERROR: Failed to get rates");
   return;
}

// Access OHLCV
double open = rates[0].open;
double high = rates[0].high;
double low = rates[0].low;
double close = rates[0].close;
long volume = rates[0].tick_volume;
datetime time = rates[0].time;
```

### CopyRates for Range
```mq5
datetime from = StringToTime("2024.01.01");
datetime to = StringToTime("2024.12.31");

MqlRates rates[];
ArraySetAsSeries(rates, true);

int copied = CopyRates(inpSymbol, inpTF, from, to, rates);
```

---

## Logging and Debugging

### Log Helper Function
```mq5
void Log(string message)
{
   if(inpEnableLogging)
   {
      Print("[EA_NAME] " + message);
   }
}
```

### Chart Comments
```mq5
void UpdateChartDisplay(MqlTick &tick)
{
   string comment = "=== EA Status ===\n";
   comment += "Symbol: " + inpSymbol + "\n";
   comment += "Price: " + DoubleToString(tick.bid, _Digits) + "\n";
   comment += "Equity: $" + DoubleToString(account.Equity(), 2) + "\n";
   comment += "Open Positions: " + IntegerToString(PositionsTotal()) + "\n";
   comment += "Status: " + (tradingEnabled ? "ACTIVE" : "PAUSED");

   Comment(comment);
}
```

---

## Common Utility Functions

### Market Hours Check
```mq5
bool IsMarketOpen()
{
   datetime now = TimeCurrent();
   int dayOfWeek = TimeDayOfWeek(now);

   // Skip weekends
   if(dayOfWeek == 6 || dayOfWeek == 7)
      return false;

   // Check symbol trade mode
   if(!SymbolInfoInteger(inpSymbol, SYMBOL_TRADE_MODE))
      return false;

   return true;
}
```

### Price Normalization
```mq5
double NormalizePrice(double price)
{
   return NormalizeDouble(price, _Digits);
}
```

### Point/Distance Calculations
```mq5
double PointsToPrice(double points)
{
   return points * symbol.TickSize();
}

double PriceToPoints(double priceDistance)
{
   return priceDistance / symbol.TickSize();
}
```

---

## Error Handling Patterns

### Input Validation
```mq5
if(inpRiskPercent <= 0 || inpRiskPercent > 100)
{
   Print("ERROR: Risk percent must be 0-100");
   return INIT_PARAMETERS_INCORRECT;
}
```

### Order Result Checking
```mq5
if(!trade.Buy(lotSize, inpSymbol, price, sl, tp, "comment"))
{
   int retcode = trade.ResultRetcode();
   string comment = trade.ResultComment();

   Log("Order failed: " + IntegerToString(retcode) + " - " + comment);

   // Handle specific errors
   if(retcode == TRADE_RETCODE_INVALID_VOLUME)
      Log("ERROR: Invalid lot size");
   else if(retcode == TRADE_RETCODE_INVALID_STOPS)
      Log("ERROR: Invalid SL/TP levels");
   else if(retcode == TRADE_RETCODE_NO_MONEY)
      Log("ERROR: Insufficient margin");
}
```

---

## Compilation & Deployment

### Compile in MetaEditor
1. Open `.mq5` file in MetaEditor (F4 from MT5)
2. Press F7 to compile
3. Verify: 0 errors, 0 warnings
4. Output: `<MT5_folder>\MQL5\Experts\<name>.ex5`

### Deploy to MT5
1. Copy `.ex5` to: `<MT5>\MQL5\Experts\`
2. Restart MT5 or refresh Navigator
3. Drag EA onto chart
4. Configure inputs in dialog
5. Enable AutoTrading (green button)

### Verify Operation
- Check Experts tab for initialization logs
- Verify EA icon appears on chart
- Monitor Journal for trade execution
- Check Trade tab for open positions

---

## Common Retcode Reference

| Code | Constant | Meaning |
|------|----------|---------|
| 10000 | TRADE_RETCODE_DONE | Request processed |
| 10001 | TRADE_RETCODE_ERROR | Generic error |
| 10003 | TRADE_RETCODE_INVALID | Invalid request |
| 10004 | TRADE_RETCODE_INVALID_VOLUME | Invalid lot size |
| 10005 | TRADE_RETCODE_INVALID_PRICE | Invalid price |
| 10006 | TRADE_RETCODE_INVALID_STOPS | Invalid SL/TP |
| 10007 | TRADE_RETCODE_TRADE_DISABLED | Trading disabled |
| 10008 | TRADE_RETCODE_MARKET_CLOSED | Market closed |
| 10016 | TRADE_RETCODE_NO_MONEY | Insufficient funds |
| 10019 | TRADE_RETCODE_INVALID_FILL | Invalid filling type |

---

## Best Practices

1. **Always validate inputs** in OnInit()
2. **Check return values** from all MT5 API calls
3. **Use ArraySetAsSeries(true)** for time-series arrays
4. **Normalize prices** with NormalizeDouble(price, _Digits)
5. **Release indicator handles** in OnDeinit()
6. **Filter positions by magic** for multi-EA charts
7. **Guard against reentrancy** in OnTick()
8. **Log selectively** - enable/disable via input flag
9. **Test on demo** before live deployment
10. **Never commit** broker credentials to code

---

## Trigger

Use this skill when:
- User requests MQL5 EA creation/modification
- Working with `.mq5` or `.mq4` files
- Debugging MT5 compilation errors
- Implementing trading strategies for MT5
- Converting Python MT5 scripts to native MQL5
