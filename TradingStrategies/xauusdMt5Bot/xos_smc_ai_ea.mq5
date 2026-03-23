//+------------------------------------------------------------------+
//|                                           xos_smc_ai_ea.mq5      |
//|                      XAUUSD SMC EA with AI Confirmation          |
//+------------------------------------------------------------------+
#property copyright "XOS SMC AI Bot"
#property version   "2.03"  // Migrated from Anthropic Claude to Ollama local LLM
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
CSymbolInfo    sym;

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+

//--- Account & Connection
input ulong    inpMagicNumber       = 777888;           // Magic number
input string   inpSymbol            = "XAUUSD";         // Trading symbol
input bool     inpUseAutoLogin      = true;             // Use terminal session

//--- Risk Management
input double   inpRiskPercent       = 2.0;              // Risk per trade (%)
input int      inpMaxSlippage       = 10;               // Max slippage (points)
input double   inpRewardToRisk      = 1.0;              // R:R target

//--- Strategy Settings
input int      inpSwingLookback     = 5;                // Swing lookback
input int      inpEmaPeriod         = 50;               // EMA period
input int      inpRsiPeriod         = 14;               // RSI period
input double   inpRsiOverbought     = 60.0;             // RSI overbought (raise to get more signals)
input double   inpRsiOversold       = 40.0;             // RSI oversold  (lower to get more signals)

//--- AI Integration
input bool     inpEnableAI          = true;             // Enable AI confirmation
input int      inpAIConfidenceMin   = 60;               // Min AI confidence (%)
input int      inpAITimeoutSec      = 30;               // AI response timeout (sec)

//--- Trailing Stop
input bool     inpUseTrailingStop   = true;             // Enable trailing
input double   inpTrailingActivationRR = 1.0;           // Activation R:R
input double   inpBreakEvenPoints   = 50;               // Break-even points

//--- Logging
input bool     inpEnableLogging     = true;             // Enable logging
input bool     inpShowChartComments = true;             // Show chart info

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
bool     aiServiceRunning = false;

int      handleEMA = INVALID_HANDLE;
int      handleRSI = INVALID_HANDLE;
int      handleATR = INVALID_HANDLE;

// AI state
string   aiSignal = "";
int      aiConfidence = 0;
double   aiSL = 0;
double   aiTP = 0;
string   aiReasoning = "";
datetime aiResponseTime = 0;
bool     aiResponseReceived = false;

// File paths
string   requestFilePath = "";
string   responseFilePath = "";
string   errorFilePath = "";

//+------------------------------------------------------------------+
//| Expert Initialization                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- Validate inputs
   if(inpRiskPercent <= 0 || inpRiskPercent > 100)
   {
      Print("ERROR: Risk percent must be 0-100");
      return INIT_PARAMETERS_INCORRECT;
   }

   //--- Initialize symbol info
   if(!sym.Name(inpSymbol))
   {
      Print("ERROR: Failed to initialize symbol: ", inpSymbol);
      return INIT_FAILED;
   }
   sym.Refresh();

   //--- Configure trade object
   trade.SetExpertMagicNumber(inpMagicNumber);
   trade.SetDeviationInPoints(inpMaxSlippage);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   trade.SetAsyncMode(false);

   //--- Create indicator handles
   handleEMA = iMA(inpSymbol, PERIOD_M15, inpEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handleRSI = iRSI(inpSymbol, PERIOD_M15, inpRsiPeriod, PRICE_CLOSE);
   handleATR = iATR(inpSymbol, PERIOD_M15, 14);

   if(handleEMA == INVALID_HANDLE || handleRSI == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create indicator handles");
      return INIT_FAILED;
   }

   //--- Initialize arrays
   ArraySetAsSeries(swingHighs, true);
   ArraySetAsSeries(swingLows, true);
   ArraySetAsSeries(swingHighsTime, true);
   ArraySetAsSeries(swingLowsTime, true);

   //--- Setup file paths (must match where MQL5 FileOpen() writes)
   //    FileOpen() uses TERMINAL_DATA_PATH\MQL5\Files by default
   string dataPath = TerminalInfoString(TERMINAL_DATA_PATH);
   requestFilePath  = dataPath + "\\MQL5\\Files\\ai_request.txt";
   responseFilePath = dataPath + "\\MQL5\\Files\\ai_response.txt";
   errorFilePath    = dataPath + "\\MQL5\\Files\\ai_error.txt";

   Log("File paths initialized (DATA PATH)");
   Log("  Request: " + requestFilePath);
   Log("  Response: " + responseFilePath);

   //--- Create timer (1 second interval)
   EventSetTimer(1);

   //--- Mark as initialized (MUST be set for OnTick to proceed)
   mt5Initialized = true;

   Log("=== XOS SMC AI EA Initialized ===");
   Log("Symbol: " + inpSymbol + " | Risk: " + DoubleToString(inpRiskPercent, 2) + "%");
   Log("AI Enabled: " + (inpEnableAI ? "YES" : "NO"));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert Deinitialization                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();

   if(handleEMA != INVALID_HANDLE) IndicatorRelease(handleEMA);
   if(handleRSI != INVALID_HANDLE) IndicatorRelease(handleRSI);
   if(handleATR != INVALID_HANDLE) IndicatorRelease(handleATR);

   if(inpShowChartComments) Comment("");

   Log("=== XOS SMC AI EA Deinitialized ===");
   Log("Reason: " + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//| Expert Tick Handler                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!mt5Initialized || !tradingEnabled)
      return;

   if(!IsMarketOpen())
      return;

   //--- Update swing points
   UpdateSwingPoints();

   //--- Get tick data
   MqlTick tick;
   if(!SymbolInfoTick(inpSymbol, tick))
   {
      Log("ERROR: Failed to get tick");
      return;
   }

   //--- Get 1M candle data
   MqlRates rates1M[];
   ArraySetAsSeries(rates1M, true);

   if(CopyRates(inpSymbol, PERIOD_M1, 0, 3, rates1M) < 3)
   {
      Log("ERROR: Failed to get 1M rates");
      return;
   }

   //--- Get 15M data for indicators
   MqlRates rates15M[];
   ArraySetAsSeries(rates15M, true);

   if(CopyRates(inpSymbol, PERIOD_M15, 0, 50, rates15M) < 50)
   {
      Log("ERROR: Failed to get 15M rates");
      return;
   }

   //--- Get indicator values
   double emaBuffer[], rsiBuffer[], atrBuffer[];
   ArraySetAsSeries(emaBuffer, true);
   ArraySetAsSeries(rsiBuffer, true);
   ArraySetAsSeries(atrBuffer, true);

   if(CopyBuffer(handleEMA, 0, 0, 2, emaBuffer) < 2) return;
   if(CopyBuffer(handleRSI, 0, 0, 1, rsiBuffer) < 1) return;
   if(CopyBuffer(handleATR, 0, 0, 1, atrBuffer) < 1) return;

   double ema = emaBuffer[0];
   double rsi = rsiBuffer[0];
   double atr = atrBuffer[0];

   //--- Get trend direction
   int trendDirection = GetTrendDirection(rates15M, ema);

   //--- Check for SMC sweep setups (1=buy, -1=sell, 0=none)
   int smcSignal = CheckSweepSetups(tick, rates1M, trendDirection, rsi);

   //--- AI Integration: Request analysis if SMC signal detected
   if(inpEnableAI && smcSignal != 0)
   {
      string marketData = BuildMarketData(tick, rates15M, ema, rsi, atr, trendDirection);
      WriteAIRequest(marketData);

      Log("AI request sent, waiting for response...");

      // Wait for AI response with timeout
      datetime startTime = TimeCurrent();
      aiResponseReceived = false;

      while(!aiResponseReceived && (TimeCurrent() - startTime) < inpAITimeoutSec)
      {
         Sleep(500);
         CheckAIResponse();
      }

      if(aiResponseReceived)
      {
         Log("AI Response: " + aiSignal + " (Confidence: " + IntegerToString(aiConfidence) + "%)");
         Log("Reasoning: " + aiReasoning);

         // Only trade if AI agrees and confidence is high enough
         bool aiAgrees = ValidateAISignal(smcSignal);

         if(aiAgrees)
         {
            Log("AI confirmation received - executing trade");
         }
         else
         {
            Log("AI did not confirm - skipping trade");
            return;
         }
      }
      else
      {
         Log("WARNING: AI response timeout - proceeding with SMC signal only");
      }
   }

   //--- Execute trade if SMC signal confirmed
   if(smcSignal != 0)
   {
      ExecuteSMCTrade(tick, rates1M, smcSignal);
   }

   //--- Update trailing stops
   if(inpUseTrailingStop)
      UpdateTrailingStops();

   //--- Update chart display
   if(inpShowChartComments)
      UpdateChartDisplay(tick, trendDirection, rsi, atr);
}

//+------------------------------------------------------------------+
//| Timer Handler                                                    |
//+------------------------------------------------------------------+
void OnTimer()
{
   sym.Refresh();

   // Check if AI bridge is running
   if(inpEnableAI)
   {
      CheckAIServiceStatus();
   }
}

//+------------------------------------------------------------------+
//| Build Market Data String for AI                                  |
//+------------------------------------------------------------------+
string BuildMarketData(MqlTick &tick, MqlRates &rates15M[],
                       double ema, double rsi, double atr, int trend)
{
   string data = "";

   data += "Symbol: " + inpSymbol + "\n";
   data += "Time: " + TimeToString(TimeCurrent()) + "\n";
   data += "Price: " + DoubleToString(tick.bid, _Digits) + "\n";
   data += "Timeframe: M15\n";
   data += "EMA50: " + DoubleToString(ema, _Digits) + "\n";
   data += "RSI14: " + DoubleToString(rsi, 2) + "\n";
   data += "ATR14: " + DoubleToString(atr, _Digits) + "\n";

   string trendText;
   if(trend == 1) trendText = "UPTREND";
   else if(trend == -1) trendText = "DOWNTREND";
   else trendText = "NEUTRAL";
   data += "Trend: " + trendText + "\n";

   data += "SwingHighs: " + IntegerToString(swingHighsCount) + " levels\n";
   data += "SwingLows: " + IntegerToString(swingLowsCount) + " levels\n";

   data += "Equity: $" + DoubleToString(account.Equity(), 2) + "\n";
   data += "Balance: $" + DoubleToString(account.Balance(), 2) + "\n";
   data += "OpenPositions: " + IntegerToString(PositionsTotal()) + "\n";

   return data;
}

//+------------------------------------------------------------------+
//| Write AI Request to File                                         |
//+------------------------------------------------------------------+
void WriteAIRequest(string marketData)
{
   // FILE_COMMON writes to the shared Common\Files folder that ai_bridge.py watches
   int handle = FileOpen("ai_request.txt", FILE_WRITE | FILE_TXT | FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      Log("ERROR: Failed to open request file. Error: " + IntegerToString(GetLastError()));
      return;
   }

   FileWriteString(handle, marketData);
   FileClose(handle);

   Log("AI request written to Common\\Files\\ai_request.txt");
}

//+------------------------------------------------------------------+
//| Check for AI Response File                                       |
//+------------------------------------------------------------------+
void CheckAIResponse()
{
   if(!MyFileExists("ai_response.txt"))
      return;

   int handle = FileOpen("ai_response.txt", FILE_READ | FILE_TXT | FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return;

   string signal = "", reasoning = "", risk = "";
   int confidence = 0;
   double sl = 0, tp = 0;

   while(!FileIsEnding(handle))
   {
      string line = FileReadString(handle);
      int colonPos = StringFind(line, ":");

      if(StringFind(line, "SIGNAL:") >= 0)
         signal = StringTrimRight(StringSubstr(line, colonPos + 1, -1));
      else if(StringFind(line, "CONFIDENCE:") >= 0)
         confidence = (int)StringToDouble(StringTrimRight(StringSubstr(line, colonPos + 1, -1)));
      else if(StringFind(line, "REASONING:") >= 0)
         reasoning = StringTrimRight(StringSubstr(line, colonPos + 1, -1));
      else if(StringFind(line, "SL:") >= 0)
         sl = StringToDouble(StringTrimRight(StringSubstr(line, colonPos + 1, -1)));
      else if(StringFind(line, "TP:") >= 0)
         tp = StringToDouble(StringTrimRight(StringSubstr(line, colonPos + 1, -1)));
      else if(StringFind(line, "RISK:") >= 0)
         risk = StringTrimRight(StringSubstr(line, colonPos + 1, -1));
   }

   FileClose(handle);

   // Store AI response
   aiSignal = signal;
   aiConfidence = confidence;
   aiSL = sl;
   aiTP = tp;
   aiReasoning = reasoning;
   aiResponseTime = TimeCurrent();
   aiResponseReceived = true;

   // Cleanup response file from Common folder
   FileDelete("ai_response.txt", FILE_COMMON);

   Log("AI response parsed: " + signal + " (" + IntegerToString(confidence) + "%)");
}

//+------------------------------------------------------------------+
//| Validate AI Signal Against SMC                                   |
//+------------------------------------------------------------------+
bool ValidateAISignal(int smcSignal)
{
   if(aiSignal == "")
      return false;

   if(aiConfidence < inpAIConfidenceMin)
   {
      Log("AI confidence too low: " + IntegerToString(aiConfidence) + "%");
      return false;
   }

   if(aiSignal == "HOLD")
   {
      Log("AI recommends HOLD");
      return false;
   }

   // Check if AI agrees with SMC direction (1=buy, -1=sell)
   if(smcSignal == 1 && aiSignal == "BUY")
      return true;
   if(smcSignal == -1 && aiSignal == "SELL")
      return true;

   Log("AI signal disagrees with SMC: AI=" + aiSignal);
   return false;
}

//+------------------------------------------------------------------+
//| Check AI Bridge Service Status                                   |
//+------------------------------------------------------------------+
void CheckAIServiceStatus()
{
   if(MyFileExists("ai_error.txt"))
   {
      int handle = FileOpen("ai_error.txt", FILE_READ | FILE_TXT | FILE_COMMON);
      if(handle != INVALID_HANDLE)
      {
         string errorLine = FileReadString(handle);
         Log("AI Bridge Error: " + errorLine);
         FileClose(handle);
         FileDelete("ai_error.txt", FILE_COMMON);
      }
      aiServiceRunning = false;
   }
}

//+------------------------------------------------------------------+
//| Check if File Exists (custom name to avoid conflict)             |
//+------------------------------------------------------------------+
bool MyFileExists(string filename)
{
   // Always check in the Common folder (shared with ai_bridge.py)
   int handle = FileOpen(filename, FILE_READ | FILE_TXT | FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return false;
   FileClose(handle);
   return true;
}

//+------------------------------------------------------------------+
//| Update Swing Points                                              |
//+------------------------------------------------------------------+
void UpdateSwingPoints()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);

   int copied = CopyRates(inpSymbol, PERIOD_M15, 0, inpSwingLookback * 2 + 10, rates);
   if(copied < inpSwingLookback * 2 + 1)
      return;

   swingHighsCount = 0;
   swingLowsCount = 0;
   ArrayResize(swingHighs, 100);
   ArrayResize(swingLows, 100);

   for(int i = inpSwingLookback; i < copied - inpSwingLookback; i++)
   {
      double currentHigh = rates[i].high;
      double currentLow = rates[i].low;

      bool isSwingHigh = true;
      bool isSwingLow = true;

      for(int j = 1; j <= inpSwingLookback; j++)
      {
         if(rates[i-j].high >= currentHigh) isSwingHigh = false;
         if(rates[i-j].low <= currentLow) isSwingLow = false;
      }

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

      if(isSwingHigh && swingHighsCount < 100)
      {
         swingHighs[swingHighsCount] = currentHigh;
         swingHighsCount++;
      }

      if(isSwingLow && swingLowsCount < 100)
      {
         swingLows[swingLowsCount] = currentLow;
         swingLowsCount++;
      }
   }
}

//+------------------------------------------------------------------+
//| Get Trend Direction                                              |
//+------------------------------------------------------------------+
int GetTrendDirection(MqlRates &rates[], double ema)
{
   double lastClose = rates[0].close;

   if(lastClose > ema)
      return 1;   // Uptrend
   else if(lastClose < ema)
      return -1;  // Downtrend
   else
      return 0;   // Neutral
}

// Returns: 1=buy signal, -1=sell signal, 0=no signal
int CheckSweepSetups(MqlTick &tick, MqlRates &rates1M[], int trend, double rsi)
{
   int ratesCount = ArraySize(rates1M);
   if(ratesCount < 2)
      return 0;

   double candleHigh  = rates1M[1].high;
   double candleLow   = rates1M[1].low;
   double candleClose = rates1M[1].close;

   // Check bearish sweep (sell)
   if(trend <= 0 && rsi > inpRsiOverbought)
   {
      for(int i = 0; i < swingHighsCount; i++)
      {
         if(candleHigh > swingHighs[i] && candleClose < swingHighs[i])
         {
            Log("BEARISH SWEEP DETECTED at " + DoubleToString(swingHighs[i], _Digits));
            return -1; // sell signal
         }
      }
   }

   // Check bullish sweep (buy)
   if(trend >= 0 && rsi < inpRsiOversold)
   {
      for(int i = 0; i < swingLowsCount; i++)
      {
         if(candleLow < swingLows[i] && candleClose > swingLows[i])
         {
            Log("BULLISH SWEEP DETECTED at " + DoubleToString(swingLows[i], _Digits));
            return 1; // buy signal
         }
      }
   }

   return 0; // no signal
}

void ExecuteSMCTrade(MqlTick &tick, MqlRates &rates1M[], int signalDirection)
{
   double candleHigh  = rates1M[1].high;
   double candleLow   = rates1M[1].low;
   double entryPrice  = 0;
   double slPrice     = 0;
   double tpPrice     = 0;
   bool   isBuy       = (signalDirection == 1);

   if(isBuy)
   {
      entryPrice = tick.ask;
      slPrice    = candleLow;
   }
   else
   {
      entryPrice = tick.bid;
      slPrice    = candleHigh;
   }

   if(slPrice == 0)
      return;

   // Calculate lot size
   double slDistance = MathAbs(entryPrice - slPrice);
   double lotSize = CalculateLotSize(slDistance);

   if(lotSize <= 0)
   {
      Log("ERROR: Invalid lot size");
      return;
   }

   // Calculate TP
   double tpDistance = slDistance * inpRewardToRisk;
   tpPrice = isBuy ? entryPrice + tpDistance : entryPrice - tpDistance;

   // Normalize prices
   slPrice = NormalizeDouble(slPrice, _Digits);
   tpPrice = NormalizeDouble(tpPrice, _Digits);

   // Execute order
   if(isBuy)
   {
      if(trade.Buy(lotSize, inpSymbol, entryPrice, slPrice, tpPrice, "SMC AI Buy"))
      {
         Log("BUY executed. Lot: " + DoubleToString(lotSize, 2) +
             " SL: " + DoubleToString(slPrice, _Digits) +
             " TP: " + DoubleToString(tpPrice, _Digits));
      }
      else
      {
         Log("BUY failed: " + trade.ResultComment());
      }
   }
   else
   {
      if(trade.Sell(lotSize, inpSymbol, entryPrice, slPrice, tpPrice, "SMC AI Sell"))
      {
         Log("SELL executed. Lot: " + DoubleToString(lotSize, 2) +
             " SL: " + DoubleToString(slPrice, _Digits) +
             " TP: " + DoubleToString(tpPrice, _Digits));
      }
      else
      {
         Log("SELL failed: " + trade.ResultComment());
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Lot Size                                               |
//+------------------------------------------------------------------+
double CalculateLotSize(double slDistance)
{
   double equity = account.Equity();
   double riskAmount = equity * (inpRiskPercent / 100.0);

   double tickValue = sym.TickValue();
   double tickSize = sym.TickSize();
   double volumeMin = sym.LotsMin();
   double volumeMax = sym.LotsMax();
   double volumeStep = sym.LotsStep();

   if(slDistance <= 0 || tickSize <= 0)
      return volumeMin;

   double rawLot = riskAmount / ((slDistance / tickSize) * tickValue);
   double lotSize = MathFloor(rawLot / volumeStep) * volumeStep;

   lotSize = MathMax(volumeMin, MathMin(lotSize, volumeMax));

   return NormalizeDouble(lotSize, 2);
}

//+------------------------------------------------------------------+
//| Update Trailing Stops                                            |
//+------------------------------------------------------------------+
void UpdateTrailingStops()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() != inpSymbol) continue;
      if(position.Magic() != inpMagicNumber) continue;

      double openPrice = position.PriceOpen();
      double currentSL = position.StopLoss();
      double currentTP = position.TakeProfit();

      double currentPrice;
      if(position.PositionType() == POSITION_TYPE_BUY)
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_BID);
      else
         currentPrice = SymbolInfoDouble(inpSymbol, SYMBOL_ASK);

      double profitPoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         profitPoints = (currentPrice - openPrice) / _Point;
      else
         profitPoints = (openPrice - currentPrice) / _Point;

      double slPoints;
      if(position.PositionType() == POSITION_TYPE_BUY)
         slPoints = (openPrice - currentSL) / _Point;
      else
         slPoints = (currentSL - openPrice) / _Point;

      if(profitPoints >= slPoints * inpTrailingActivationRR)
      {
         double newSL;
         if(position.PositionType() == POSITION_TYPE_BUY)
         {
            newSL = openPrice + (inpBreakEvenPoints * _Point);
            if(newSL > currentSL)
               trade.PositionModify(position.Ticket(), newSL, currentTP);
         }
         else
         {
            newSL = openPrice - (inpBreakEvenPoints * _Point);
            if(newSL < currentSL)
               trade.PositionModify(position.Ticket(), newSL, currentTP);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Check if Market is Open                                          |
//+------------------------------------------------------------------+
bool IsMarketOpen()
{
   //--- Use MqlDateTime to get day-of-week (Sunday=0, Saturday=6)
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   if(now.day_of_week == 0 || now.day_of_week == 6)
      return false;

   if(!SymbolInfoInteger(inpSymbol, SYMBOL_TRADE_MODE))
      return false;

   return true;
}

//+------------------------------------------------------------------+
//| Update Chart Display                                             |
//+------------------------------------------------------------------+
void UpdateChartDisplay(MqlTick &tick, int trend, double rsi, double atr)
{
   string trendText;
   if(trend == 1) trendText = "UPTREND";
   else if(trend == -1) trendText = "DOWNTREND";
   else trendText = "NEUTRAL";

   string comment = "=== XOS SMC AI Bot ===\n";
   comment += "Symbol: " + inpSymbol + "\n";
   comment += "Price: " + DoubleToString(tick.bid, _Digits) + "\n";
   comment += "Trend: " + trendText + "\n";
   comment += "RSI: " + DoubleToString(rsi, 2) + "\n";
   comment += "ATR: " + DoubleToString(atr, _Digits) + "\n";
   comment += "Swing Highs: " + IntegerToString(swingHighsCount) + "\n";
   comment += "Swing Lows: " + IntegerToString(swingLowsCount) + "\n";
   comment += "Equity: $" + DoubleToString(account.Equity(), 2) + "\n";
   comment += "AI: " + (inpEnableAI ? (aiServiceRunning ? "ONLINE" : "OFFLINE") : "DISABLED") + "\n";
   if(aiResponseReceived)
   {
      comment += "AI Signal: " + aiSignal + " (" + IntegerToString(aiConfidence) + "%)\n";
   }
   comment += "Status: " + (tradingEnabled ? "ACTIVE" : "PAUSED") + "\n";

   Comment(comment);
}

//+------------------------------------------------------------------+
//| Logging Helper                                                   |
//+------------------------------------------------------------------+
void Log(string message)
{
   if(inpEnableLogging)
   {
      Print("[XOS SMC AI] " + message);
   }
}

//+------------------------------------------------------------------+
