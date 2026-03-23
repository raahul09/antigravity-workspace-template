//+------------------------------------------------------------------+
//|                                              xos_smc_ea.mq5       |
//|                                   XAUUSD SMC Liquidity Sweep EA   |
//|                                   Expert Advisor for MT5 Terminal |
//+------------------------------------------------------------------+
#property copyright "XOS SMC Bot"
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

//--- Account & Connection
input int      inpMagicNumber       = 777888;           // Magic number for trade identification
input string   inpSymbol            = "XAUUSD";         // Trading symbol
input bool     inpUseAutoLogin      = false;            // Use terminal's logged-in account
input int      inpMT5Login          = 0;                // MT5 Login ID (if manual login)
input string   inpMT5Password       = "";               // MT5 Password
input string   inpMT5Server         = "";               // MT5 Server name

//--- Risk Management
input double   inpRiskPercent       = 5.0;              // Risk per trade (%)
input int      inpMaxSlippage       = 10;               // Maximum slippage in points
input double   inpRewardToRisk      = 0.2;              // R:R target (hyper-scalping)

//--- Strategy Settings
input int      inpSwingLookback     = 5;                // Swing point lookback (candles)
input int      inpEmaPeriod         = 50;               // EMA period for trend filter
input int      inpRsiPeriod         = 14;               // RSI period
input double   inpRsiOverbought     = 55.0;             // RSI overbought threshold
input double   inpRsiOversold       = 45.0;             // RSI oversold threshold

//--- Trailing Stop
input bool     inpUseTrailingStop   = true;             // Enable trailing stop
input double   inpTrailingActivationRR = 1.0;           // R:R level to activate trailing

//--- Timeframe Settings
input ENUM_TIMEFRAMES inpTF15M      = PERIOD_M15;       // 15M timeframe for swing points
input ENUM_TIMEFRAMES inpTF1M       = PERIOD_M1;        // 1M timeframe for sweep detection

//--- Logging & Debug
input bool     inpEnableLogging     = true;             // Enable chart logging
input bool     inpShowChartComments = true;             // Show info on chart

//+------------------------------------------------------------------+
//| Global Variables                                                 |
//+------------------------------------------------------------------+

int      swingHighsCount = 0;
int      swingLowsCount = 0;
double   swingHighs[];
double   swingLows[];
datetime swingHighsTime[];
datetime swingLowsTime[];

bool     mt5Initialized = false;
bool     tradingEnabled = true;

int      handleEMA = INVALID_HANDLE;
int      handleRSI = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Expert Initialization Function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Validate inputs
   if(inpRiskPercent <= 0 || inpRiskPercent > 100)
   {
      Print("ERROR: Risk percent must be between 0 and 100");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(inpRewardToRisk <= 0)
   {
      Print("ERROR: Reward-to-risk ratio must be positive");
      return INIT_PARAMETERS_INCORRECT;
   }

   //--- Initialize symbol info
   if(!symbol.Name(inpSymbol))
   {
      Print("ERROR: Failed to initialize symbol ", inpSymbol);
      return INIT_FAILED;
   }
   symbol.Refresh();

   //--- Configure trade object
   trade.SetExpertMagicNumber(inpMagicNumber);
   trade.SetDeviationInPoints(inpMaxSlippage);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   trade.SetAsyncMode(false);

   //--- Initialize indicators
   handleEMA = iMA(inpSymbol, inpTF15M, inpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handleRSI = iRSI(inpSymbol, inpTF15M, inpRsiPeriod, PRICE_CLOSE);

   if(handleEMA == INVALID_HANDLE || handleRSI == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create indicator handles");
      return INIT_FAILED;
   }

   //--- Initialize arrays for swing points
   ArraySetAsSeries(swingHighs, true);
   ArraySetAsSeries(swingLows, true);
   ArraySetAsSeries(swingHighsTime, true);
   ArraySetAsSeries(swingLowsTime, true);

   //--- Attempt MT5 login if credentials provided
   if(!inpUseAutoLogin && inpMT5Login != 0 && inpMT5Password != "" && inpMT5Server != "")
   {
      if(!MT5Login(inpMT5Login, inpMT5Password, inpMT5Server))
      {
         Print("ERROR: MT5 login failed. Error: ", GetLastError());
         return INIT_FAILED;
      }
      mt5Initialized = true;
      Log("Successfully logged into MT5 account: " + IntegerToString(inpMT5Login));
   }
   else
   {
      // Use auto-login (terminal's current session)
      mt5Initialized = true;
      Log("Using auto-login from terminal session");
   }

   //--- Create timer for swing point updates (every 15 seconds)
   EventSetTimer(15);

   Log("=== XOS SMC EA Initialized ===");
   Log("Symbol: " + inpSymbol + ", Risk: " + DoubleToString(inpRiskPercent, 2) + "%");
   Log("R:R Target: " + DoubleToString(inpRewardToRisk, 2) + ", Swing Lookback: " + IntegerToString(inpSwingLookback));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert Deinitialization Function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   //--- Kill timer
   EventKillTimer();

   //--- Release indicator handles
   if(handleEMA != INVALID_HANDLE) IndicatorRelease(handleEMA);
   if(handleRSI != INVALID_HANDLE) IndicatorRelease(handleRSI);

   //--- Clear chart comments
   if(inpShowChartComments)
      Comment("");

   Log("=== XOS SMC EA Deinitialized ===");
   Log("Reason: " + EnumToString(reason));
}

//+------------------------------------------------------------------+
//| Expert Tick Handler                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!mt5Initialized || !tradingEnabled)
      return;

   //--- Check market hours (skip if market closed)
   if(!IsMarketOpen())
      return;

   //--- Update swing points from 15M
   UpdateSwingPoints();

   //--- Get current price data
   MqlTick tick;
   if(!SymbolInfoTick(inpSymbol, tick))
   {
      Log("ERROR: Failed to get tick data");
      return;
   }

   //--- Get 1M candle data for sweep detection
   MqlRates rates1M[];
   ArraySetAsSeries(rates1M, true);

   int copied1M = CopyRates(inpSymbol, inpTF1M, 0, 3, rates1M);
   if(copied1M < 3)
   {
      Log("ERROR: Failed to get 1M rates");
      return;
   }

   //--- Get 15M data for trend context
   MqlRates rates15M[];
   ArraySetAsSeries(rates15M, true);

   int copied15M = CopyRates(inpSymbol, inpTF15M, 0, 50, rates15M);
   if(copied15M < 50)
   {
      Log("ERROR: Failed to get 15M rates for trend context");
      return;
   }

   //--- Calculate trend filter
   int trendDirection = GetTrendDirection(rates15M);
   double rsiValue = GetRSIValue();

   //--- Check for liquidity sweep setups
   CheckSweepSetups(tick, rates1M, trendDirection, rsiValue);

   //--- Update trailing stops on open positions
   if(inpUseTrailingStop)
      UpdateTrailingStops();

   //--- Update chart display
   if(inpShowChartComments)
      UpdateChartDisplay(tick, trendDirection, rsiValue);
}

//+------------------------------------------------------------------+
//| Timer Handler - Periodic Tasks                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   //--- Refresh swing points periodically
   UpdateSwingPoints();

   //--- Refresh symbol info
   symbol.Refresh();
}

//+------------------------------------------------------------------+
//| Trade Event Handler                                              |
//+------------------------------------------------------------------+
void OnTrade()
{
   //--- Handle trade events (position updates, orders filled)
   position.SelectByMagic(inpMagicNumber);

   if(position.SelectByMagic(inpMagicNumber))
   {
      Log("Trade event detected. Positions updated.");
   }
}

//+------------------------------------------------------------------+
//| Update Swing Points on 15M                                       |
//+------------------------------------------------------------------+
void UpdateSwingPoints()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);

   int copied = CopyRates(inpSymbol, inpTF15M, 0, inpSwingLookback * 2 + 10, rates);
   if(copied < inpSwingLookback * 2 + 1)
      return;

   //--- Clear previous swing points
   swingHighsCount = 0;
   swingLowsCount = 0;
   ArrayResize(swingHighs, 100);
   ArrayResize(swingLows, 100);
   ArrayResize(swingHighsTime, 100);
   ArrayResize(swingLowsTime, 100);

   //--- Detect swing highs and lows
   for(int i = inpSwingLookback; i < copied - inpSwingLookback; i++)
   {
      double currentHigh = rates[i].high;
      double currentLow = rates[i].low;

      bool isSwingHigh = true;
      bool isSwingLow = true;

      //--- Check left side
      for(int j = 1; j <= inpSwingLookback; j++)
      {
         if(rates[i-j].high >= currentHigh)
         {
            isSwingHigh = false;
            break;
         }
         if(rates[i-j].low <= currentLow)
         {
            isSwingLow = false;
            break;
         }
      }

      //--- Check right side
      if(isSwingHigh)
      {
         for(int j = 1; j <= inpSwingLookback; j++)
         {
            if(rates[i+j].high >= currentHigh)
            {
               isSwingHigh = false;
               break;
            }
         }
      }

      if(isSwingLow)
      {
         for(int j = 1; j <= inpSwingLookback; j++)
         {
            if(rates[i+j].low <= currentLow)
            {
               isSwingLow = false;
               break;
            }
         }
      }

      //--- Store swing points
      if(isSwingHigh && swingHighsCount < 100)
      {
         swingHighs[swingHighsCount] = currentHigh;
         swingHighsTime[swingHighsCount] = rates[i].time;
         swingHighsCount++;
      }

      if(isSwingLow && swingLowsCount < 100)
      {
         swingLows[swingLowsCount] = currentLow;
         swingLowsTime[swingLowsCount] = rates[i].time;
         swingLowsCount++;
      }
   }

   Log("Swing points updated: Highs=" + IntegerToString(swingHighsCount) +
       ", Lows=" + IntegerToString(swingLowsCount));
}

//+------------------------------------------------------------------+
//| Get Trend Direction from 15M EMA                                 |
//+------------------------------------------------------------------+
int GetTrendDirection(MqlRates &rates15M[])
{
   double emaBuffer[];
   ArraySetAsSeries(emaBuffer, true);

   if(CopyBuffer(handleEMA, 0, 0, 2, emaBuffer) < 2)
      return 0; // Neutral

   double lastClose = rates15M[0].close;
   double lastEMA = emaBuffer[0];

   if(lastClose > lastEMA)
      return 1; // Uptrend
   else if(lastClose < lastEMA)
      return -1; // Downtrend
   else
      return 0; // Neutral
}

//+------------------------------------------------------------------+
//| Get RSI Value from 15M                                           |
//+------------------------------------------------------------------+
double GetRSIValue()
{
   double rsiBuffer[];
   ArraySetAsSeries(rsiBuffer, true);

   if(CopyBuffer(handleRSI, 0, 0, 1, rsiBuffer) < 1)
      return 50.0; // Default neutral

   return rsiBuffer[0];
}

//+------------------------------------------------------------------+
//| Check for Liquidity Sweep Setups                                 |
//+------------------------------------------------------------------+
void CheckSweepSetups(MqlTick &tick, MqlRates &rates1M, int trendDirection, double rsiValue)
{
   if(rates1M.Length() < 2)
      return;

   //--- Get last closed 1M candle (index 1)
   double candleHigh = rates1M[1].high;
   double candleLow = rates1M[1].low;
   double candleClose = rates1M[1].close;
   double candleOpen = rates1M[1].open;

   double currentPrice = tick.bid;
   double askPrice = tick.ask;

   //--- Check for bearish sweep (sell setup)
   if(trendDirection <= 0 && rsiValue > inpRsiOverbought)
   {
      for(int i = 0; i < swingHighsCount; i++)
      {
         double swingLevel = swingHighs[i];

         //--- Price swept above swing high
         if(candleHigh > swingLevel)
         {
            //--- Candle closed back below swing level (bearish rejection)
            if(candleClose < swingLevel)
            {
               Log("BEARISH SWEEP DETECTED!");
               Log("  Swing Level: " + DoubleToString(swingLevel, _Digits));
               Log("  Sweep High: " + DoubleToString(candleHigh, _Digits));
               Log("  Close: " + DoubleToString(candleClose, _Digits));

               double slDistance = candleHigh - swingLevel;
               double slPrice = candleHigh;
               double entryPrice = askPrice;

               ExecuteSellTrade(slPrice, entryPrice, slDistance);
               break; // Only one trade per sweep
            }
         }
      }
   }

   //--- Check for bullish sweep (buy setup)
   if(trendDirection >= 0 && rsiValue < inpRsiOversold)
   {
      for(int i = 0; i < swingLowsCount; i++)
      {
         double swingLevel = swingLows[i];

         //--- Price swept below swing low
         if(candleLow < swingLevel)
         {
            //--- Candle closed back above swing level (bullish rejection)
            if(candleClose > swingLevel)
            {
               Log("BULLISH SWEEP DETECTED!");
               Log("  Swing Level: " + DoubleToString(swingLevel, _Digits));
               Log("  Sweep Low: " + DoubleToString(candleLow, _Digits));
               Log("  Close: " + DoubleToString(candleClose, _Digits));

               double slDistance = swingLevel - candleLow;
               double slPrice = candleLow;
               double entryPrice = currentPrice;

               ExecuteBuyTrade(slPrice, entryPrice, slDistance);
               break; // Only one trade per sweep
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Execute Buy Trade                                                |
//+------------------------------------------------------------------+
void ExecuteBuyTrade(double slPrice, double entryPrice, double slDistancePoints)
{
   double lotSize = CalculateLotSize(slDistancePoints);

   if(lotSize <= 0 || lotSize < symbol.VolumeMin() || lotSize > symbol.VolumeMax())
   {
      Log("ERROR: Invalid lot size calculated: " + DoubleToString(lotSize, 2));
      return;
   }

   //--- Calculate Take Profit
   double tpDistance = slDistancePoints * inpRewardToRisk;
   double tpPrice = entryPrice + tpDistance;

   //--- Normalize prices
   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   Log("Executing BUY:");
   Log("  Lot: " + DoubleToString(lotSize, 2));
   Log("  Entry: " + DoubleToString(entryPrice, _Digits));
   Log("  SL: " + DoubleToString(slPrice, _Digits));
   Log("  TP: " + DoubleToString(tpPrice, _Digits));

   //--- Execute buy order
   if(trade.Buy(lotSize, inpSymbol, entryPrice, slPrice, tpPrice, "XOS SMC Buy"))
   {
      Log("BUY order successful. Ticket: " + IntegerToString(trade.ResultOrder()));
      Log("  Deal price: " + DoubleToString(trade.ResultDealPrice(), _Digits));
   }
   else
   {
      Log("ERROR: BUY order failed. Retcode: " + IntegerToString(trade.ResultRetcode()));
      Log("  Comment: " + trade.ResultComment());
   }
}

//+------------------------------------------------------------------+
//| Execute Sell Trade                                               |
//+------------------------------------------------------------------+
void ExecuteSellTrade(double slPrice, double entryPrice, double slDistancePoints)
{
   double lotSize = CalculateLotSize(slDistancePoints);

   if(lotSize <= 0 || lotSize < symbol.VolumeMin() || lotSize > symbol.VolumeMax())
   {
      Log("ERROR: Invalid lot size calculated: " + DoubleToString(lotSize, 2));
      return;
   }

   //--- Calculate Take Profit
   double tpDistance = slDistancePoints * inpRewardToRisk;
   double tpPrice = entryPrice - tpDistance;

   //--- Normalize prices
   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   Log("Executing SELL:");
   Log("  Lot: " + DoubleToString(lotSize, 2));
   Log("  Entry: " + DoubleToString(entryPrice, _Digits));
   Log("  SL: " + DoubleToString(slPrice, _Digits));
   Log("  TP: " + DoubleToString(tpPrice, _Digits));

   //--- Execute sell order
   if(trade.Sell(lotSize, inpSymbol, entryPrice, slPrice, tpPrice, "XOS SMC Sell"))
   {
      Log("SELL order successful. Ticket: " + IntegerToString(trade.ResultOrder()));
      Log("  Deal price: " + DoubleToString(trade.ResultDealPrice(), _Digits));
   }
   else
   {
      Log("ERROR: SELL order failed. Retcode: " + IntegerToString(trade.ResultRetcode()));
      Log("  Comment: " + trade.ResultComment());
   }
}

//+------------------------------------------------------------------+
//| Calculate Dynamic Lot Size                                       |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistancePoints)
{
   double equity = account.Equity();
   double riskAmount = equity * (inpRiskPercent / 100.0);

   double tickValue = symbol.TickValue();
   double tickSize = symbol.TickSize();

   if(slDistancePoints <= 0 || tickSize <= 0)
      return symbol.VolumeMin();

   //--- Calculate raw lot size
   // Risk Amount = Lot Size * (SL Distance / Tick Size) * Tick Value
   double rawLot = riskAmount / ((slDistancePoints / tickSize) * tickValue);

   //--- Floor to volume step
   double volumeStep = symbol.VolumeStep();
   double lotSize = MathFloor(rawLot / volumeStep) * volumeStep;

   //--- Clamp to min/max
   lotSize = MathMax(symbol.VolumeMin(), MathMin(lotSize, symbol.VolumeMax()));

   return NormalizeDouble(lotSize, 2);
}

//+------------------------------------------------------------------+
//| Update Trailing Stops                                            |
//+------------------------------------------------------------------+
void UpdateTrailingStops()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i))
         continue;

      if(position.Symbol() != inpSymbol)
         continue;

      if(position.Magic() != inpMagicNumber)
         continue;

      //--- Get position info
      double openPrice = position.PriceOpen();
      double currentSL = position.StopLoss();
      double volume = position.Volume();

      //--- Get current price
      double currentPrice;
      if(position.PositionType() == POSITION_TYPE_BUY)
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_BID);
      else
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_ASK);

      //--- Calculate profit in points
      double profitPoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         profitPoints = (currentPrice - openPrice) / symbol.TickSize();
      else
         profitPoints = (openPrice - currentPrice) / symbol.TickSize();

      //--- Calculate SL distance in points
      double slDistancePoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         slDistancePoints = (openPrice - currentSL) / symbol.TickSize();
      else
         slDistancePoints = (currentSL - openPrice) / symbol.TickSize();

      //--- Check if trailing should activate
      if(profitPoints >= slDistancePoints * inpTrailingActivationRR)
      {
         //--- Move SL to break-even or trail
         double newSL;
         if(position.PositionType() == POSITION_TYPE_BUY)
            newSL = currentPrice - (slDistancePoints * symbol.TickSize());
         else
            newSL = currentPrice + (slDistancePoints * symbol.TickSize());

         //--- Only update if new SL is better
         if(position.PositionType() == POSITION_TYPE_BUY)
         {
            if(newSL > currentSL)
            {
               trade.PositionModify(position.Ticket(), newSL, position.TakeProfit());
               Log("Trailing stop updated for BUY #" + IntegerToString(position.Ticket()) +
                   " -> SL: " + DoubleToString(newSL, _Digits));
            }
         }
         else
         {
            if(newSL < currentSL)
            {
               trade.PositionModify(position.Ticket(), newSL, position.TakeProfit());
               Log("Trailing stop updated for SELL #" + IntegerToString(position.Ticket()) +
                   " -> SL: " + DoubleToString(newSL, _Digits));
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check if Market is Open                                          |
//+------------------------------------------------------------------+
bool IsMarketOpen()
{
   //--- Check if trading is allowed on symbol
   if(!SymbolInfoInteger(inpSymbol, SYMBOL_TRADE_MODE))
      return false;

   //--- Check if session is active
   MqlTradingSession session[];
   if(!SymbolInfoSession(inpSymbol, 0, session))
      return true; // Assume open if no session info

   datetime now = TimeCurrent();

   //--- Simple check: avoid weekends
   int dayOfWeek = TimeDayOfWeek(now);
   if(dayOfWeek == 6 || dayOfWeek == 7) // Saturday or Sunday
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Update Chart Display                                             |
//+------------------------------------------------------------------+
void UpdateChartDisplay(MqlTick &tick, int trendDirection, double rsiValue)
{
   string trendText;
   if(trendDirection == 1)
      trendText = "UPTREND";
   else if(trendDirection == -1)
      trendText = "DOWNTREND";
   else
      trendText = "NEUTRAL";

   string comment = "=== XOS SMC Bot ===\n";
   comment += "Symbol: " + inpSymbol + "\n";
   comment += "Price: " + DoubleToString(tick.bid, _Digits) + "\n";
   comment += "Trend: " + trendText + "\n";
   comment += "RSI: " + DoubleToString(rsiValue, 2) + "\n";
   comment += "Swing Highs: " + IntegerToString(swingHighsCount) + "\n";
   comment += "Swing Lows: " + IntegerToString(swingLowsCount) + "\n";
   comment += "Equity: $" + DoubleToString(account.Equity(), 2) + "\n";
   comment += "Risk: " + DoubleToString(inpRiskPercent, 2) + "%\n";

   if(tradingEnabled)
      comment += "Status: ACTIVE\n";
   else
      comment += "Status: PAUSED\n";

   Comment(comment);
}

//+------------------------------------------------------------------+
//| Logging Helper                                                   |
//+------------------------------------------------------------------+
void Log(string message)
{
   if(inpEnableLogging)
   {
      Print("[XOS SMC] " + message);
   }
}

//+------------------------------------------------------------------+
//| MT5 Login Helper                                                 |
//+------------------------------------------------------------------+
bool MT5Login(int login, string password, string server)
{
   MqlAccountInfo accInfo;

   //--- Try to login
   if(!AccountLogin(login, password, server))
      return false;

   //--- Verify login succeeded
   if(AccountInfoInteger(ACCOUNT_LOGIN) == login)
      return true;

   return false;
}

//+------------------------------------------------------------------+
//| End of Expert Advisor                                            |
//+------------------------------------------------------------------+
