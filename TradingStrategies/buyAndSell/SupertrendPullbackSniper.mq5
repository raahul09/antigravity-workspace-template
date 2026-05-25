//+------------------------------------------------------------------+
//|                                  SupertrendConfirmedSniper.mq5   |
//|                 Supertrend + Confirmed Pullback Bounces          |
//+------------------------------------------------------------------+
#property copyright "Rahul"
#property link      ""
#property version   "1.00"

#include <Trade\Trade.mqh>

//--- Enums
enum ENUM_TRAIL_MODE {
   TRAIL_OFF = 0,         // No Trailing
   TRAIL_FIXED = 1,       // Fixed Points
   TRAIL_DYNAMIC_ST = 2   // Dynamic (Follow Supertrend Line)
};

//--- 1. Supertrend Trend Settings ---
input group "=== 1. Supertrend Trend ==="
input int    InpStPeriod       = 10;
input double InpStMultiplier   = 3.0;

//--- 2. Pullback Settings ---
input group "=== 2. Pullback & Bounce ==="
input int    InpPullbackDist   = 50;    // Max distance from ST to arm the pullback (Points)
input bool   InpRequireBounce  = true;  // Require a bullish/bearish candle bounce to trigger

//--- 3. Profit and Loss ---
input group "=== 3. Profit and Loss ==="
input int    InpSL_Points      = 200;   // Stop Loss (Points)
input int    InpTP_Points      = 400;   // Take Profit (Points)

//--- 4. Trailing Stop ---
input group "=== 4. Trailing Stop ==="
input ENUM_TRAIL_MODE InpTrailMode     = TRAIL_FIXED; // Trailing Mode
input int             InpTrailFixedPts = 100;         // Fixed Trailing (Points)

//--- 5. Risk Management ---
input group "=== 5. Risk Management ==="
input double InpFixedLot       = 0.01;
input long   InpMagic          = 12345;

//--- Globals
CTrade g_trade;
int    g_atrHandle = INVALID_HANDLE;
bool   g_armedBuy = false;
bool   g_armedSell = false;
datetime g_lastTradeTime = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit() {
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(10);
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpStPeriod);
   if(g_atrHandle == INVALID_HANDLE) {
      Print("Failed to load ATR indicator");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   if(g_atrHandle != INVALID_HANDLE) IndicatorRelease(g_atrHandle);
}

//+------------------------------------------------------------------+
//| Core: Get Supertrend Values for the previous two formed bars     |
//+------------------------------------------------------------------+
bool GetSupertrendFlip(int &stDir0, double &stLevel) {
   int lookback = InpStPeriod + 100;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   if(CopyRates(_Symbol, PERIOD_CURRENT, 0, lookback, rates) < lookback) return false;
   
   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   if(CopyBuffer(g_atrHandle, 0, 0, lookback, atrBuf) < lookback) return false;
   
   double finalUp[], finalDn[];
   int dir[];
   ArrayResize(finalUp, lookback);
   ArrayResize(finalDn, lookback);
   ArrayResize(dir, lookback);
   
   finalUp[0] = (rates[0].high + rates[0].low)/2.0 + InpStMultiplier * atrBuf[0];
   finalDn[0] = (rates[0].high + rates[0].low)/2.0 - InpStMultiplier * atrBuf[0];
   dir[0] = 1; // Default
   
   for(int i=1; i<lookback; i++) {
      double hl2 = (rates[i].high + rates[i].low)/2.0;
      double basicUp = hl2 + InpStMultiplier * atrBuf[i];
      double basicDn = hl2 - InpStMultiplier * atrBuf[i];
      double prevClose = rates[i-1].close;
      
      finalUp[i] = (basicUp < finalUp[i-1] || prevClose > finalUp[i-1]) ? basicUp : finalUp[i-1];
      finalDn[i] = (basicDn > finalDn[i-1] || prevClose < finalDn[i-1]) ? basicDn : finalDn[i-1];
      
      if(dir[i-1] == 1)
         dir[i] = (rates[i].close < finalDn[i]) ? -1 : 1;
      else
         dir[i] = (rates[i].close > finalUp[i]) ? 1 : -1;
   }
   
   stDir0 = dir[lookback-1]; 
   stLevel = (stDir0 == 1) ? finalDn[lookback-1] : finalUp[lookback-1];
   return true;
}

//+------------------------------------------------------------------+
//| Management Utilities                                             |
//+------------------------------------------------------------------+
bool HasOpenPosition() {
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) {
         return true;
      }
   }
   return false;
}

void ManageTrailingStop(double stLevel, int stDir) {
   if(InpTrailMode == TRAIL_OFF) return;
   
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      
      long type = PositionGetInteger(POSITION_TYPE);
      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      
      if(InpTrailMode == TRAIL_FIXED) {
         double trailDist = InpTrailFixedPts * _Point;
         if(type == POSITION_TYPE_BUY) {
            double newSL = NormalizeDouble(bid - trailDist, _Digits);
            if(newSL > currentSL + _Point || currentSL == 0) g_trade.PositionModify(ticket, newSL, currentTP);
         } else {
            double newSL = NormalizeDouble(ask + trailDist, _Digits);
            if(newSL < currentSL - _Point || currentSL == 0) g_trade.PositionModify(ticket, newSL, currentTP);
         }
      }
      else if(InpTrailMode == TRAIL_DYNAMIC_ST) {
         if(type == POSITION_TYPE_BUY && stDir == 1) {
            double newSL = NormalizeDouble(stLevel - 10*_Point, _Digits);
            if(newSL > currentSL + _Point || currentSL == 0) g_trade.PositionModify(ticket, newSL, currentTP);
         } else if(type == POSITION_TYPE_SELL && stDir == -1) {
            double newSL = NormalizeDouble(stLevel + 10*_Point, _Digits);
            if(newSL < currentSL - _Point || currentSL == 0) g_trade.PositionModify(ticket, newSL, currentTP);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| OnTick - Main Logic                                              |
//+------------------------------------------------------------------+
void OnTick() {
   if(iBars(_Symbol, PERIOD_CURRENT) < InpStPeriod + 10) return; // Not enough data
   
   double stLevel;
   int stDir0;
   if(!GetSupertrendFlip(stDir0, stLevel)) return;
   
   // 1. Manage Trailing Stop
   ManageTrailingStop(stLevel, stDir0);
   
   // If a trade is open, wait for it to hit TP/SL. Do not look for new entries.
   if(HasOpenPosition()) {
      g_armedBuy = false;
      g_armedSell = false;
      return; 
   }
   
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   
   // Distance from price to Supertrend line
   double distBuy = (ask - stLevel) / _Point;
   double distSell = (stLevel - bid) / _Point;
   
   // Current Candle formation
   double currentOpen = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double currentClose = iClose(_Symbol, PERIOD_CURRENT, 0); // Approximation in real-time
   bool isBullishCandle = (currentClose > currentOpen);
   bool isBearishCandle = (currentClose < currentOpen);

   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   
   // ----------------------------------------------------------------
   // UPTREND LOGIC (Supertrend = Green)
   // ----------------------------------------------------------------
   if(stDir0 == 1) {
      g_armedSell = false; // Cancel any sell logic
      
      // Step 1: Arm the Pullback (Price dropped close to the line)
      if(!g_armedBuy && distBuy > 0 && distBuy <= InpPullbackDist) {
         g_armedBuy = true;
      }
      
      // Step 2: Trigger the Bounce (We are armed, and we get a bullish confirmation)
      if(g_armedBuy && g_lastTradeTime != currentBarTime) {
         bool trigger = false;
         
         if(InpRequireBounce) {
            // We require price to bounce up. If the candle turns powerfully green, trigger!
            if(isBullishCandle && (currentClose - currentOpen)/_Point > 10) trigger = true; 
         } else {
            // If bounce not required, buy immediately upon arming
            trigger = true;
         }
         
         if(trigger) {
            double sl = NormalizeDouble(ask - InpSL_Points * _Point, _Digits);
            double tp = NormalizeDouble(ask + InpTP_Points * _Point, _Digits);
            if(g_trade.Buy(InpFixedLot, _Symbol, ask, sl, tp, "Confirmed Bounce Buy")) {
               g_lastTradeTime = currentBarTime;
               g_armedBuy = false; // Reset
               Print("BUY: Confirmed Pullback Bounce in Uptrend!");
            }
         }
      }
   }
   
   // ----------------------------------------------------------------
   // DOWNTREND LOGIC (Supertrend = Red)
   // ----------------------------------------------------------------
   else if(stDir0 == -1) {
      g_armedBuy = false; // Cancel any buy logic
      
      // Step 1: Arm the Pullback (Price rallied close to the line)
      if(!g_armedSell && distSell > 0 && distSell <= InpPullbackDist) {
         g_armedSell = true;
      }
      
      // Step 2: Trigger the Bounce (We are armed, and we get a bearish confirmation)
      if(g_armedSell && g_lastTradeTime != currentBarTime) {
         bool trigger = false;
         
         if(InpRequireBounce) {
            // We require price to bounce down. If the candle turns powerfully red, trigger!
            if(isBearishCandle && (currentOpen - currentClose)/_Point > 10) trigger = true; 
         } else {
            // If bounce not required, sell immediately upon arming
            trigger = true;
         }
         
         if(trigger) {
            double sl = NormalizeDouble(bid + InpSL_Points * _Point, _Digits);
            double tp = NormalizeDouble(bid - InpTP_Points * _Point, _Digits);
            if(g_trade.Sell(InpFixedLot, _Symbol, bid, sl, tp, "Confirmed Bounce Sell")) {
               g_lastTradeTime = currentBarTime;
               g_armedSell = false; // Reset
               Print("SELL: Confirmed Pullback Bounce in Downtrend!");
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
