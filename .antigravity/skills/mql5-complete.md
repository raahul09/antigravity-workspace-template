# MQL5 Complete Development Skill - Error-Free Bot Building

## Overview

Comprehensive MQL5 Expert Advisor development skill based on official MQL5 documentation. Follow these patterns to build bots without compilation or runtime errors.

---

## Part 1: MQL5 Language Fundamentals

### Data Types

```mq5
//--- Integer types
int      x = 10;           // 32-bit integer
long     y = 1000000L;     // 64-bit integer
short    z = 100;          // 16-bit integer

//--- Floating point
double   price = 1.2345;   // 64-bit float
float    ratio = 0.5f;     // 32-bit float

//--- Boolean
bool     isActive = true;

//--- String
string   symbol = "EURUSD";
string   comment = "Trade opened";

//--- Character
char     byte = 0x41;      // ASCII 'A'

//--- Color (for chart drawing)
color    bullColor = clrGreen;
color    bearColor = clrRed;

//--- Datetime
datetime barTime = TimeCurrent();
datetime specific = StringToTime("2024.01.15 10:30");
```

### Arrays

```mq5
//--- Static arrays
double prices[100];
int    levels[50];

//--- Dynamic arrays
double buffer[];
ArrayResize(buffer, 200);

//--- Series arrays (reverse indexing - most recent = index 0)
double maBuffer[];
ArraySetAsSeries(maBuffer, true);

//--- Array operations
ArrayFree(array);           // Free memory
ArrayResize(array, size);   // Resize
ArrayCopy(dest, src);       // Copy
ArraySize(array);           // Get size
```

---

## Part 2: Preprocessor Directives

### Properties

```mq5
#property copyright "Author Name"
#property version   "1.00"
#property strict

//--- Indicator properties
#property indicator_chart_window
#property indicator_buffers 3
#property indicator_plots   2
#property indicator_minimum 0
#property indicator_maximum 100

//--- Library export
#property library
#property script
```

### Includes

```mq5
//--- Standard library includes
#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Trade\TradeDialog.mqh>

//--- Custom includes
#include <MyIndicators\CustomMA.mqh>
#include "MyFunctions.mqh"  // Local file
```

### Conditional Compilation

```mq5
#ifdef DEBUG_MODE
   Print("Debug info");
#endif

#ifndef __MQL5__
   #error "This code requires MQL5"
#endif
```

---

## Part 3: Event Handlers (Complete Reference)

### OnInit() - Expert Advisor

```mq5
int OnInit()
{
   // 1. Validate input parameters
   if(inpRiskPercent <= 0 || inpRiskPercent > 100)
   {
      Print("ERROR: Risk must be 0-100%");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(inpSymbol == "")
   {
      Print("ERROR: Symbol cannot be empty");
      return INIT_PARAMETERS_INCORRECT;
   }

   // 2. Initialize symbol info
   if(!symbol.Name(inpSymbol))
   {
      Print("ERROR: Cannot initialize symbol: ", inpSymbol);
      return INIT_FAILED;
   }
   symbol.Refresh();

   // 3. Check symbol trade mode
   if(!SymbolInfoInteger(inpSymbol, SYMBOL_TRADE_MODE))
   {
      Print("ERROR: Trading not allowed for ", inpSymbol);
      return INIT_FAILED;
   }

   // 4. Configure trade object
   trade.SetExpertMagicNumber(inpMagicNumber);
   trade.SetDeviationInPoints(inpMaxSlippage);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   trade.SetAsyncMode(false);
   trade.SetMarginMode();

   // 5. Create indicator handles
   handleMA = iMA(inpSymbol, inpTF, inpPeriod, 0, MODE_SMA, PRICE_CLOSE);
   handleRSI = iRSI(inpSymbol, inpTF, inpRsiPeriod, PRICE_CLOSE);
   handleATR = iATR(inpSymbol, inpTF, inpAtrPeriod);

   if(handleMA == INVALID_HANDLE || handleRSI == INVALID_HANDLE)
   {
      Print("ERROR: Indicator creation failed. Error: ", GetLastError());
      return INIT_FAILED;
   }

   // 6. Initialize arrays
   ArraySetAsSeries(maBuffer, true);
   ArraySetAsSeries(rsiBuffer, true);

   // 7. Setup timer (optional)
   EventSetTimer(60); // 60 seconds

   // 8. Log success
   Print("=== ", MQLInfoInteger(MQL_PROGRAM_NAME), " Initialized ===");
   Print("Symbol: ", inpSymbol, " | TF: ", EnumToString(inpTF));
   Print("Risk: ", inpRiskPercent, "% | Magic: ", inpMagicNumber);

   return INIT_SUCCEEDED;
}
```

### OnDeinit() - All Types

```mq5
void OnDeinit(const int reason)
{
   // Kill timer
   EventKillTimer();

   // Release indicator handles
   if(handleMA != INVALID_HANDLE) IndicatorRelease(handleMA);
   if(handleRSI != INVALID_HANDLE) IndicatorRelease(handleRSI);
   if(handleATR != INVALID_HANDLE) IndicatorRelease(handleATR);

   // Delete graphical objects
   ObjectDelete(0, "Label_Status");
   ObjectDelete(0, "Line_Entry");
   ObjectDelete(0, "Line_SL");
   ObjectDelete(0, "Line_TP");

   // Clear chart comments
   Comment("");

   // Log reason
   string reasonText;
   switch(reason)
   {
      case REASON_REMOVE:      reasonText = "Removed by user"; break;
      case REASON_RECOMPILE:   reasonText = "Recompiled"; break;
      case REASON_CHARTCHANGE: reasonText = "Chart changed"; break;
      case REASON_TEMPLATE:    reasonText = "Template changed"; break;
      case REASON_PARAMETERS:  reasonText = "Parameters changed"; break;
      case REASON_CLOSE:       reasonText = "Chart closed"; break;
      default:                 reasonText = EnumToString(reason);
   }
   Print("EA Deinitialized. Reason: ", reasonText);
}
```

### OnTick() - Expert Advisor Only

```mq5
void OnTick()
{
   //--- Guard: Check if trading allowed
   if(!IsTradeAllowed()) return;
   if(!IsMarketOpen()) return;
   if(IsStopped()) return;

   //--- Guard: Check terminal connection
   if(!TerminalInfoInteger(TERMINEEQUITY)) return;

   //--- Get tick data
   MqlTick tick;
   if(!SymbolInfoTick(inpSymbol, tick))
   {
      Print("ERROR: Failed to get tick");
      return;
   }

   //--- Get candle data
   MqlRates rates[];
   ArraySetAsSeries(rates, true);

   int copied = CopyRates(inpSymbol, inpTF, 0, 100, rates);
   if(copied < 100)
   {
      Print("ERROR: Failed to get rates. Count: ", copied);
      return;
   }

   //--- Get indicator values
   double maBuffer[], rsiBuffer[], atrBuffer[];
   ArraySetAsSeries(maBuffer, true);
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(atrBuffer, true);

   if(CopyBuffer(handleMA, 0, 0, 2, maBuffer) < 2) return;
   if(CopyBuffer(handleRSI, 0, 0, 1, rsiBuffer) < 1) return;
   if(CopyBuffer(handleATR, 0, 0, 1, atrBuffer) < 1) return;

   //--- Strategy logic
   double ma = maBuffer[0];
   double rsi = rsiBuffer[0];
   double atr = atrBuffer[0];

   //--- Check for entry signals
   CheckEntrySignals(tick, rates, ma, rsi, atr);

   //--- Manage positions
   if(inpUseTrailingStop)
      UpdateTrailingStops();

   //--- Update display
   UpdateChartDisplay(tick, ma, rsi);
}
```

### OnTimer() - All Types

```mq5
void OnTimer()
{
   //--- Periodic tasks (called every N seconds as set in OnInit)

   // Refresh swing points
   UpdateSwingPoints();

   // Refresh symbol info
   symbol.Refresh();

   // Check news events (if implemented)
   CheckNewsFilter();

   // Log status
   if(TimeCurrent() % 300 < 15) // Every 5 minutes
      Print("Status: Equity=$", account.Equity(), " | Positions: ", PositionsTotal());
}
```

### OnTrade() - Expert Advisor Only

```mq5
void OnTrade()
{
   //--- Called when trade state changes (order/position modified)

   // Refresh position info
   position.SelectByMagic(inpMagicNumber);

   // Log trade event
   Print("Trade event detected. Positions updated.");

   // Update trailing stops if needed
   if(inpUseTrailingStop)
      UpdateTrailingStops();
}
```

### OnTradeTransaction() - Expert Advisor Only

```mq5
void OnTradeTransaction(const MqlTradeTransaction& transaction,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
   //--- Detailed trade transaction logging

   Print("=== Trade Transaction ===");
   Print("Type: ", EnumToString(transaction.type));
   Print("Order: ", transaction.order);
   Print("Deal: ", transaction.deal);
   Print("Symbol: ", transaction.symbol);

   if(transaction.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      Print("New deal added. Deal #: ", transaction.deal);
   }

   if(transaction.type == TRADE_TRANSACTION_POSITION_ADD)
   {
      Print("New position opened. Position #: ", transaction.position);
   }

   if(transaction.type == TRADE_TRANSACTION_POSITION_REMOVE)
   {
      Print("Position closed. Deal #: ", transaction.deal);
   }
}
```

### OnChartEvent() - All Types

```mq5
void OnChartEvent(const int id, const long lparam, const double dparam, const string sparam)
{
   //--- Handle chart events

   if(id == CHARTEVENT_KEYDOWN)
   {
      Print("Key pressed: ", lparam);
      if(lparam == 'T') ToggleTrading();
      if(lparam == 'P') PrintPositionSummary();
   }

   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam == "Button_Start")
      {
         ObjectSetInteger(0, "Button_Start", OBJPROP_STATE, false);
         StartTrading();
      }
      if(sparam == "Button_Stop")
      {
         ObjectSetInteger(0, "Button_Stop", OBJPROP_STATE, false);
         StopTrading();
      }
   }

   if(id == CHARTEVENT_MOUSE_MOVE)
   {
      // Handle mouse movement for custom UI
   }
}
```

### OnCalculate() - Custom Indicator

```mq5
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   //--- Calculate indicator values

   int start = (prev_calculated > 0) ? prev_calculated - 1 : 0;

   for(int i = start; i < rates_total; i++)
   {
      // Example: Simple MA calculation
      double sum = 0;
      for(int j = 0; j < period; j++)
      {
         sum += close[i - j];
      }
      Buffer[i] = sum / period;
   }

   return rates_total;
}
```

### OnStart() - Script Only

```mq5
int OnStart()
{
   //--- Script execution (runs once)

   Print("Script started");

   // Execute single action
   double lotSize = 0.1;
   double sl = SymbolInfoDouble(_Symbol, SYMBOL_BID) - 100 * _Point;
   double tp = SymbolInfoDouble(_Symbol, SYMBOL_BID) + 200 * _Point;

   if(trade.Buy(lotSize, _Symbol, 0, sl, tp, "Script trade"))
      Print("Trade executed successfully");
   else
      Print("Trade failed: ", trade.ResultRetcode());

   return 0;
}
```

---

## Part 4: Trade Operations (Error-Free Patterns)

### Order Execution Pattern

```mq5
bool ExecuteBuyOrder(double lotSize, double slPrice, double tpPrice, string comment)
{
   //--- Validate lot size
   double minLot = symbol.VolumeMin();
   double maxLot = symbol.VolumeMax();
   double lotStep = symbol.VolumeStep();

   if(lotSize < minLot)
   {
      Print("ERROR: Lot size below minimum: ", lotSize, " < ", minLot);
      return false;
   }
   if(lotSize > maxLot)
   {
      Print("ERROR: Lot size above maximum: ", lotSize, " > ", maxLot);
      return false;
   }

   //--- Normalize prices
   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   //--- Check if SL/TP are valid
   if(slPrice != 0)
   {
      double minSL = SymbolInfoDouble(inpSymbol, SYMBOL_ASK) - SymbolInfoInteger(inpSymbol, SYMBOL_TRADE_STOPS_LEVEL);
      if(slPrice >= SymbolInfoDouble(inpSymbol, SYMBOL_ASK))
      {
         Print("ERROR: SL must be below entry for BUY");
         return false;
      }
   }

   //--- Execute order
   bool result = trade.Buy(lotSize, inpSymbol, 0, slPrice, tpPrice, comment);

   if(!result)
   {
      int retcode = trade.ResultRetcode();
      string retMessage = trade.ResultComment();

      Print("BUY order failed. Retcode: ", retcode, " Message: ", retMessage);

      // Handle specific errors
      HandleTradeError(retcode);
      return false;
   }

   Print("BUY successful. Ticket: ", trade.ResultOrder(), " Price: ", trade.ResultDealPrice());
   return true;
}

bool ExecuteSellOrder(double lotSize, double slPrice, double tpPrice, string comment)
{
   //--- Same validation as ExecuteBuyOrder

   double minLot = symbol.VolumeMin();
   double maxLot = symbol.VolumeMax();

   if(lotSize < minLot || lotSize > maxLot)
   {
      Print("ERROR: Invalid lot size");
      return false;
   }

   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   bool result = trade.Sell(lotSize, inpSymbol, 0, slPrice, tpPrice, comment);

   if(!result)
   {
      Print("SELL order failed. Retcode: ", trade.ResultRetcode());
      HandleTradeError(trade.ResultRetcode());
      return false;
   }

   Print("SELL successful. Ticket: ", trade.ResultOrder());
   return true;
}
```

### Error Handler

```mq5
void HandleTradeError(int retcode)
{
   switch(retcode)
   {
      case TRADE_RETCODE_DONE:
         // No error - success
         break;

      case TRADE_RETCODE_INVALID_VOLUME:
         Print("Fix: Check VolumeMin/VolumeMax/VolumeStep");
         break;

      case TRADE_RETCODE_INVALID_PRICE:
         Print("Fix: Normalize price with NormalizeDouble(price, _Digits)");
         break;

      case TRADE_RETCODE_INVALID_STOPS:
         Print("Fix: SL must be away from current price by StopsLevel");
         break;

      case TRADE_RETCODE_TRADE_DISABLED:
         Print("Fix: Enable AutoTrading in terminal");
         break;

      case TRADE_RETCODE_MARKET_CLOSED:
         Print("Fix: Market is closed - wait for open");
         break;

      case TRADE_RETCODE_NO_MONEY:
         Print("Fix: Insufficient margin - reduce lot size");
         break;

      case TRADE_RETCODE_INVALID_FILL:
         Print("Fix: Use correct filling type (FILLING_IOC or FILLING_GTC)");
         break;

      case TRADE_RETCODE_INVALID:
         Print("Fix: Check all order parameters");
         break;

      case TRADE_RETCODE_TIMEOUT:
         Print("Fix: Network timeout - retry");
         break;

      default:
         Print("Unknown error: ", retcode);
   }
}
```

### Position Modification

```mq5
bool ModifyPosition(ulong ticket, double newSL, double newTP)
{
   //--- Validate new levels
   double currentPrice;
   int posType = (int)PositionGetInteger(POSITION_TYPE);

   if(posType == POSITION_TYPE_BUY)
   {
      currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_BID);
      if(newSL != 0 && newSL >= currentPrice)
      {
         Print("ERROR: SL cannot be above current price for BUY");
         return false;
      }
   }
   else
   {
      currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_ASK);
      if(newSL != 0 && newSL <= currentPrice)
      {
         Print("ERROR: SL cannot be below current price for SELL");
         return false;
      }
   }

   //--- Normalize
   newSL = NormalizeDouble(newSL, _Digits);
   newTP = NormalizeDouble(newTP, _Digits);

   //--- Modify
   if(!trade.PositionModify(ticket, newSL, newTP))
   {
      Print("Modify failed: ", trade.ResultRetcode());
      return false;
   }

   Print("Position modified. New SL: ", newSL, " TP: ", newTP);
   return true;
}
```

### Close Position

```mq5
bool ClosePosition(ulong ticket)
{
   //--- Get position info
   if(!position.Select(ticket))
   {
      Print("ERROR: Position not found");
      return false;
   }

   //--- Close by opposite order
   if(position.PositionType() == POSITION_TYPE_BUY)
   {
      if(!trade.Sell(position.Volume(), inpSymbol, 0, 0, 0, "Close BUY"))
      {
         Print("Close BUY failed: ", trade.ResultRetcode());
         return false;
      }
   }
   else
   {
      if(!trade.Buy(position.Volume(), inpSymbol, 0, 0, 0, "Close SELL"))
      {
         Print("Close SELL failed: ", trade.ResultRetcode());
         return false;
      }
   }

   Print("Position closed. Ticket: ", ticket);
   return true;
}
```

---

## Part 5: Risk Management (Complete Patterns)

### Dynamic Lot Size Calculation

```mq5
double CalculateLotSize(double slDistancePoints)
{
   //--- Get account equity
   double equity = account.Equity();

   //--- Calculate risk amount
   double riskAmount = equity * (inpRiskPercent / 100.0);

   //--- Get symbol properties
   double tickValue = symbol.TickValue();
   double tickSize = symbol.TickSize();
   double volumeMin = symbol.VolumeMin();
   double volumeMax = symbol.VolumeMax();
   double volumeStep = symbol.VolumeStep();

   //--- Validate inputs
   if(slDistancePoints <= 0 || tickSize <= 0)
   {
      Print("WARNING: Invalid SL distance or tick size");
      return volumeMin;
   }

   if(tickValue == 0)
   {
      Print("ERROR: Tick value is zero");
      return volumeMin;
   }

   //--- Calculate raw lot size
   // Formula: Risk = LotSize * (SL_distance / tickSize) * tickValue
   double rawLot = riskAmount / ((slDistancePoints / tickSize) * tickValue);

   //--- Floor to volume step
   double lotSize = MathFloor(rawLot / volumeStep) * volumeStep;

   //--- Clamp to min/max
   lotSize = MathMax(volumeMin, MathMin(lotSize, volumeMax));

   //--- Normalize to 2 decimal places
   lotSize = NormalizeDouble(lotSize, 2);

   Print("Lot calculated: Equity=$", equity, " Risk=", inpRiskPercent,
         "% SL=", slDistancePoints, "pts -> Lot=", lotSize);

   return lotSize;
}
```

### Position Size by ATR

```mq5
double CalculateLotSizeByATR(double atrValue)
{
   double equity = account.Equity();
   double riskAmount = equity * (inpRiskPercent / 100.0);

   // ATR-based SL distance
   double slDistance = atrValue * 2.0; // 2x ATR

   double tickValue = symbol.TickValue();
   double tickSize = symbol.TickSize();

   double rawLot = riskAmount / ((slDistance / tickSize) * tickValue);

   double volumeStep = symbol.VolumeStep();
   double lotSize = MathFloor(rawLot / volumeStep) * volumeStep;

   lotSize = MathMax(symbol.VolumeMin(), MathMin(lotSize, symbol.VolumeMax()));

   return NormalizeDouble(lotSize, 2);
}
```

### Maximum Drawdown Protection

```mq5
bool CheckDrawdownLimit()
{
   //--- Get account balance and equity
   double balance = account.Balance();
   double equity = account.Equity();

   //--- Calculate current drawdown
   double drawdownPercent = ((balance - equity) / balance) * 100.0;

   //--- Check against limit
   if(drawdownPercent > inpMaxDrawdownPercent)
   {
      Print("DRAWDOWN LIMIT REACHED: ", DoubleToString(drawdownPercent, 2), "%");
      Print("Trading paused until drawdown reduces");
      return false; // Stop trading
   }

   return true; // Continue trading
}
```

### Daily Loss Limit

```mq5
bool CheckDailyLossLimit()
{
   //--- Get today's profit/loss
   datetime todayStart = StringToTime(TimeToString(TimeCurrent(), TIME_DATE));
   double dailyPL = 0;

   // Loop through today's deals
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(!DealSelect(ticket)) continue;

      datetime dealTime = (datetime)HistoryDealGetInteger(ticket, DEAL_ENTRY_TIME);
      if(dealTime < todayStart) continue;

      if(HistoryDealGetString(ticket, DEAL_SYMBOL) == inpSymbol)
      {
         dailyPL += HistoryDealGetDouble(ticket, DEAL_PROFIT);
      }
   }

   //--- Check limit
   if(dailyPL < -inpDailyLossLimit)
   {
      Print("DAILY LOSS LIMIT REACHED: $", DoubleToString(dailyPL, 2));
      return false;
   }

   return true;
}
```

---

## Part 6: Trailing Stop Patterns

### Break-Even Trailing

```mq5
void UpdateTrailingStops()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() != inpSymbol) continue;
      if(position.Magic() != inpMagicNumber) continue;

      ulong ticket = position.Ticket();
      double openPrice = position.PriceOpen();
      double currentSL = position.StopLoss();
      double currentTP = position.TakeProfit();

      // Get current price
      double currentPrice;
      if(position.PositionType() == POSITION_TYPE_BUY)
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_BID);
      else
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_ASK);

      // Calculate profit in points
      double profitPoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         profitPoints = (currentPrice - openPrice) / _Point;
      else
         profitPoints = (openPrice - currentPrice) / _Point;

      // Calculate SL distance in points
      double slPoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         slPoints = (openPrice - currentSL) / _Point;
      else
         slPoints = (currentSL - openPrice) / _Point;

      // Check if trailing should activate (profit >= activation R:R)
      if(profitPoints >= slPoints * inpTrailingActivationRR)
      {
         // Move to break-even
         double newSL;
         if(position.PositionType() == POSITION_TYPE_BUY)
         {
            newSL = openPrice + (inpBreakEvenPoints * _Point);
            if(newSL > currentSL)
            {
               if(trade.PositionModify(ticket, newSL, currentTP))
                  Print("BE trailing updated for BUY #", ticket);
            }
         }
         else
         {
            newSL = openPrice - (inpBreakEvenPoints * _Point);
            if(newSL < currentSL)
            {
               if(trade.PositionModify(ticket, newSL, currentTP))
                  Print("BE trailing updated for SELL #", ticket);
            }
         }
      }
   }
}
```

### ATR Trailing Stop

```mq5
void UpdateATRTrailingStop()
{
   double atrBuffer[];
   ArraySetAsSeries(atrBuffer, true);
   CopyBuffer(handleATR, 0, 0, 1, atrBuffer);
   double atr = atrBuffer[0];

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() != inpSymbol) continue;
      if(position.Magic() != inpMagicNumber) continue;

      ulong ticket = position.Ticket();
      double currentPrice;
      if(position.PositionType() == POSITION_TYPE_BUY)
      {
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_BID);
         double newSL = currentPrice - (atr * inpTrailingMultiplier);
         if(newSL > position.StopLoss())
            trade.PositionModify(ticket, newSL, position.TakeProfit());
      }
      else
      {
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_ASK);
         double newSL = currentPrice + (atr * inpTrailingMultiplier);
         if(newSL < position.StopLoss())
            trade.PositionModify(ticket, newSL, position.TakeProfit());
      }
   }
}
```

---

## Part 7: Indicator Patterns

### Creating Indicators

```mq5
// In OnInit()
handleEMA = iMA(_Symbol, _Period, 50, 0, MODE_EMA, PRICE_CLOSE);
handleRSI = iRSI(_Symbol, _Period, 14, PRICE_CLOSE);
handleATR = iATR(_Symbol, _Period, 14);
handleBB = iBands(_Symbol, _Period, 20, 0, 2, PRICE_CLOSE);
handleMACD = iMACD(_Symbol, _Period, 12, 26, 9, PRICE_CLOSE);
handleStoch = iStochastic(_Symbol, _Period, 14, 3, 3, MODE_SMA, STO_LOWHIGH);
handleADX = iADX(_Symbol, _Period, 14);

// Validate handles
if(handleEMA == INVALID_HANDLE) { Print("EMA handle failed"); return INIT_FAILED; }
if(handleRSI == INVALID_HANDLE) { Print("RSI handle failed"); return INIT_FAILED; }
```

### Reading Indicator Buffers

```mq5
double GetIndicatorValue(int handle, int buffer, int index)
{
   double bufferArray[];
   ArraySetAsSeries(bufferArray, true);

   if(CopyBuffer(handle, buffer, index, 1, bufferArray) < 1)
   {
      Print("ERROR: CopyBuffer failed");
      return EMPTY_VALUE;
   }

   return bufferArray[0];
}

// Usage
double ema = GetIndicatorValue(handleEMA, 0, 0);
double rsi = GetIndicatorValue(handleRSI, 0, 0);
double atr = GetIndicatorValue(handleATR, 0, 0);
```

### Multi-Timeframe Analysis

```mq5
double GetMTF Indicator(string symbol, ENUM_TIMEFRAMES tf, int handle, int buffer)
{
   double bufferArray[];
   ArraySetAsSeries(bufferArray, true);

   if(CopyBuffer(handle, buffer, 0, 1, bufferArray) < 1)
      return EMPTY_VALUE;

   return bufferArray[0];
}

// Usage in OnTick()
double ema15M = GetMTF Indicator(inpSymbol, PERIOD_M15, handleEMA15, 0);
double ema1H  = GetMTF Indicator(inpSymbol, PERIOD_H1, handleEMA1H, 0);
double ema4H  = GetMTF Indicator(inpSymbol, PERIOD_H4, handleEMA4H, 0);

// Multi-timeframe trend filter
int trend = 0;
if(ema15M > ema1H && ema1H > ema4H) trend = 1;  // Bullish
if(ema15M < ema1H && ema1H < ema4H) trend = -1; // Bearish
```

---

## Part 8: Common Error Solutions

### Compilation Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 'variable' undefined | Missing declaration | Add type: `double`, `int`, `string` |
| Array index out of range | Accessing beyond array size | Check array size before access |
| Invalid type conversion | Mixing incompatible types | Use explicit casting |
| Function not found | Missing include or typo | Check `#include` paths |
| Duplicate variable name | Same name in scope | Rename one variable |
| ';' expected | Missing semicolon | Add `;` at end of statement |
| '{' expected | Missing brace | Add opening `{` |
| Unexpected end of file | Unclosed brace/function | Check all braces match |

### Runtime Errors

| Error | Cause | Solution |
|-------|-------|----------|
| INIT_FAILED | Initialization error | Check return values in OnInit |
| TRADE_RETCODE_INVALID_VOLUME | Lot size invalid | Use VolumeMin/VolumeMax |
| TRADE_RETCODE_INVALID_STOPS | SL/TP too close | Check SYMBOL_TRADE_STOPS_LEVEL |
| TRADE_RETCODE_NO_MONEY | Insufficient margin | Reduce lot size |
| TRADE_RETCODE_MARKET_CLOSED | Market closed | Check IsMarketOpen() |
| TRADE_RETCODE_TRADE_DISABLED | AutoTrading off | Enable AutoTrading button |
| CopyBuffer failed | Invalid handle | Check handle != INVALID_HANDLE |
| CopyRates failed | Data unavailable | Check symbol and timeframe |

---

## Part 9: Debugging Techniques

### Print Debugging

```mq5
void DebugPrint(string message, double value = EMPTY_VALUE)
{
   if(inpEnableLogging)
   {
      if(value == EMPTY_VALUE)
         Print("[DEBUG] ", message);
      else
         Print("[DEBUG] ", message, " = ", DoubleToString(value, 5));
   }
}

// Usage
DebugPrint("Current price", tick.bid);
DebugPrint("RSI value", rsi);
DebugPrint("Lot size", lotSize);
```

### Chart Visual Debug

```mq5
void DrawDebugLabel(string text, int x, int y)
{
   string name = "DebugLabel_" + IntegerToString(x);

   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   }

   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

// Usage in OnTick()
DrawDebugLabel("Price: " + DoubleToString(tick.bid, _Digits), 10, 30);
DrawDebugLabel("RSI: " + DoubleToString(rsi, 2), 10, 50);
DrawDebugLabel("Signal: " + signalText, 10, 70);
```

### Error Logging

```mq5
void LogError(string function, string error, int errorCode)
{
   string logEntry = TimeToString(TimeCurrent()) + " | ERROR | " +
                     function + " | " + error + " | Code: " + IntegerToString(errorCode);

   // Print to journal
   Print(logEntry);

   // Could also write to file
   // FileWrite(handle, logEntry);
}
```

---

## Part 10: Best Practices Checklist

### Before Compilation

- [ ] All variables declared with types
- [ ] All functions have return statements
- [ ] All braces matched (open/close)
- [ ] All semicolons in place
- [ ] Include paths correct
- [ ] Input parameters validated
- [ ] Indicator handles checked for INVALID_HANDLE

### Before Deployment

- [ ] Test on demo account first
- [ ] Verify lot size calculation
- [ ] Check SL/TP levels are valid
- [ ] Enable AutoTrading in terminal
- [ ] Set correct magic number
- [ ] Verify symbol name matches broker
- [ ] Check max slippage setting

### During Operation

- [ ] Monitor Experts log for errors
- [ ] Check Journal tab for trade results
- [ ] Verify positions match expected behavior
- [ ] Watch for drawdown limits
- [ ] Review trailing stop updates

---

## Part 11: Quick Reference

### MQL5 Constants

```mq5
// Order types
ORDER_TYPE_BUY
ORDER_TYPE_SELL
ORDER_TYPE_BUY_LIMIT
ORDER_TYPE_SELL_LIMIT
ORDER_TYPE_BUY_STOP
ORDER_TYPE_SELL_STOP

// Filling types
ORDER_FILLING_IOC
ORDER_FILLING_GTC
ORDER_FILLING_FOK

// Time types
ORDER_TIME_GTC
ORDER_TIME_DAY
ORDER_TIME_SPECIFIED

// Position types
POSITION_TYPE_BUY
POSITION_TYPE_SELL

// Timeframes
PERIOD_M1, PERIOD_M5, PERIOD_M15, PERIOD_M30
PERIOD_H1, PERIOD_H4, PERIOD_D1, PERIOD_W1, PERIOD_MN1

// Prices
SYMBOL_BID, SYMBOL_ASK, SYMBOL_LAST
SYMBOL_OPEN, SYMBOL_HIGH, SYMBOL_LOW, SYMBOL_CLOSE

// Colors
clrBlack, clrWhite, clrRed, clrGreen, clrBlue
clrYellow, clrMagenta, clrCyan, clrOrange
```

### Common Functions

```mq5
// Math
MathAbs(), MathMax(), MathMin(), MathFloor(), MathCeil()
MathRound(), MathSqrt(), MathPow(), MathLog(), MathExp()

// String
StringToTime(), TimeToString(), DoubleToString(), IntegerToString()
StringFormat(), StringSubstr(), StringReplace()

// Array
ArraySize(), ArrayResize(), ArrayFree(), ArrayCopy()
ArraySetAsSeries(), ArraySort(), ArrayBSearch()

// Symbol info
SymbolInfoDouble(), SymbolInfoInteger(), SymbolInfoString()
SymbolInfoTick(), SymbolInfoSession()

// Account info
AccountInfoDouble(), AccountInfoInteger(), AccountInfoString()

// Trade functions
OrderSend(), OrderGetTicket(), PositionGetTicket()
PositionGetSymbol(), PositionGetVolume()

// Indicator functions
iMA(), iRSI(), iMACD(), iBands(), iATR(), iStochastic(), iADX()
CopyBuffer(), CopyRates(), CopyTick()
```

---

## Trigger

Use this skill when:
- Creating new MQL5 Expert Advisors, indicators, or scripts
- Debugging compilation errors in MetaEditor
- Fixing runtime trade execution errors
- Implementing risk management logic
- Working with indicator handles and buffers
- Building multi-timeframe analysis systems
- Converting strategies from other platforms to MQL5

---

## Error Prevention Rules

1. **Always check return values** from CopyBuffer, CopyRates, trade functions
2. **Always normalize prices** with NormalizeDouble(price, _Digits)
3. **Always validate lot size** against VolumeMin/VolumeMax/VolumeStep
4. **Always check handle != INVALID_HANDLE** before using indicators
5. **Always use ArraySetAsSeries(true)** for time-series buffers
6. **Always guard OnTick()** with IsTradeAllowed() check
7. **Always release handles** in OnDeinit()
8. **Always check market hours** before trading
9. **Always validate SL/TP** levels relative to current price
10. **Always test on demo** before live deployment
