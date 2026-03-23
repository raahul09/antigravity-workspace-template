//+------------------------------------------------------------------+
//|                   SupertrendGridHybrid.mq5                       |
//|        Phase 1 — Core Indicators, Visuals & Debounce            |
//|   Planner 2 Merged: ADX + ATR Trail handles, 60s debounce,      |
//|   GetLastError logging, OBJ_TEXT signals, duplicate guard.       |
//+------------------------------------------------------------------+
#property copyright   "Rahul — SupertrendGridHybrid EA"
#property link        ""
#property version     "1.00"
#property description "Supertrend Grid Hybrid EA — Phase 1 of 6"
#property strict

#include <Trade\Trade.mqh>

//===================================================================
//  INPUT PARAMETERS
//===================================================================
input group "══ Supertrend Settings ══"
input int    InpStAtrPeriod     = 10;    // ST: ATR Period
input double InpStMultiplier    = 3.0;   // ST: Multiplier

input group "══ ADX Filter (Phase 2+) ══"
input int    InpAdxPeriod       = 14;    // ADX Period

input group "══ ATR Trailing Stop (Phase 3+) ══"
input int    InpAtrTrailPeriod  = 14;    // ATR Trail: Period
input double InpAtrTrailMult    = 1.5;   // ATR Trail: Multiplier

input group "══ Debounce Timer ══"
input int    InpDebounceSec     = 60;    // Debounce: seconds between evaluations

input group "══ Magic Numbers ══"
input long   InpMagic1          = 1000;  // Magic — Main Runner
input long   InpMagic2          = 2000;  // Magic — Scalp

//===================================================================
//  INDICATOR HANDLES
//===================================================================
int g_atrStHandle   = INVALID_HANDLE;  // ATR for Supertrend calculation
int g_atrTrlHandle  = INVALID_HANDLE;  // ATR for trailing stop (Phase 3)
int g_adxHandle     = INVALID_HANDLE;  // ADX for trend filter  (Phase 2)

//===================================================================
//  SUPERTREND DIRECTION ENUM
//===================================================================
enum ENUM_ST_DIR
{
   ST_NONE = 0,
   ST_BULL = 1,   // Green — price above Supertrend line
   ST_BEAR = 2    // Red   — price below Supertrend line
};

//===================================================================
//  SIGNAL TRACKING — duplicate guard
//===================================================================
datetime    g_lastLabelBar  = 0;       // Bar-open-time of the last drawn label
ENUM_ST_DIR g_lastLabelDir  = ST_NONE; // Direction of the last drawn label

//===================================================================
//  DEBOUNCE
//===================================================================
datetime g_lastProcessTime = 0;

//===================================================================
//  CHART OBJECT NAMING
//===================================================================
#define LABEL_PREFIX "SGH_"


//+------------------------------------------------------------------+
//|  GetSupertrendDirs                                               |
//|  Computes Supertrend direction for bar[0] (current, forming)     |
//|  and bar[1] (previous, closed).                                  |
//|  Returns false if not enough bars / copy failed.                 |
//+------------------------------------------------------------------+
bool GetSupertrendDirs(ENUM_ST_DIR &dir0, ENUM_ST_DIR &dir1)
{
   dir0 = ST_NONE;
   dir1 = ST_NONE;

   int lookback = InpStAtrPeriod + 100; // generous history for stable bands

   //--- Copy rates (oldest first)
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int rCopied = CopyRates(_Symbol, PERIOD_CURRENT, 0, lookback, rates);
   if(rCopied < InpStAtrPeriod + 3)
   {
      Print("GetSupertrendDirs — CopyRates insufficient: ", rCopied, " | Err: ", GetLastError());
      return false;
   }

   //--- Copy ATR buffer (oldest first, matching rates[] indexing)
   double atrBuf[];
   ArraySetAsSeries(atrBuf, false);
   int aCopied = CopyBuffer(g_atrStHandle, 0, 0, lookback, atrBuf);
   if(aCopied < InpStAtrPeriod + 3)
   {
      Print("GetSupertrendDirs — CopyBuffer(ATR) insufficient: ", aCopied, " | Err: ", GetLastError());
      return false;
   }

   //--- Use the smaller count so indices are always valid
   int n = (int)MathMin(rCopied, aCopied);

   //--- Allocate Supertrend arrays
   double finalUp[];
   double finalDn[];
   ENUM_ST_DIR dir[];
   ArrayResize(finalUp, n);
   ArrayResize(finalDn, n);
   ArrayResize(dir,     n);

   // Seed the first element
   finalUp[0] = (rates[0].high + rates[0].low) / 2.0 + InpStMultiplier * atrBuf[0];
   finalDn[0] = (rates[0].high + rates[0].low) / 2.0 - InpStMultiplier * atrBuf[0];
   dir[0]     = ST_BULL;

   //--- Build Supertrend from oldest bar to newest
   for(int i = 1; i < n; i++)
   {
      double atr    = atrBuf[i];
      double hl2    = (rates[i].high + rates[i].low) / 2.0;
      double basicUp = hl2 + InpStMultiplier * atr;
      double basicDn = hl2 - InpStMultiplier * atr;
      double prevClose = rates[i - 1].close;

      //--- Final Upper Band:
      //    Tighten only if new basicUp < prevFinalUp,
      //    or reset if previous close moved above the old upper band
      finalUp[i] = (basicUp < finalUp[i-1] || prevClose > finalUp[i-1])
                   ? basicUp
                   : finalUp[i-1];

      //--- Final Lower Band:
      //    Raise only if new basicDn > prevFinalDn,
      //    or reset if previous close fell below the old lower band
      finalDn[i] = (basicDn > finalDn[i-1] || prevClose < finalDn[i-1])
                   ? basicDn
                   : finalDn[i-1];

      //--- Direction: follow previous direction until price crosses the opposite band
      if(dir[i-1] == ST_BULL)
         dir[i] = (rates[i].close < finalDn[i]) ? ST_BEAR : ST_BULL;
      else
         dir[i] = (rates[i].close > finalUp[i]) ? ST_BULL : ST_BEAR;
   }

   //--- Expose results: index n-1 = bar[0] (newest), n-2 = bar[1] (prev closed)
   dir0 = dir[n - 1];
   dir1 = dir[n - 2];
   return true;
}


//+------------------------------------------------------------------+
//|  DrawLabel                                                       |
//|  Creates an OBJ_TEXT label on the chart. Deletes any prior       |
//|  object with the same name first to avoid stacking.              |
//+------------------------------------------------------------------+
void DrawLabel(datetime barTime, double price, bool isBuy)
{
   string objName = LABEL_PREFIX + TimeToString(barTime, TIME_DATE | TIME_MINUTES);

   ObjectDelete(0, objName); // remove stale label if present

   string text   = isBuy ? "▲ BUY" : "▼ SELL";
   color  clr    = isBuy ? clrLime  : clrRed;
   int    anchor = isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM;

   if(!ObjectCreate(0, objName, OBJ_TEXT, 0, barTime, price))
   {
      Print("DrawLabel — ObjectCreate failed. ObjName: ", objName,
            " | Price: ", price, " | Err: ", GetLastError());
      return;
   }

   ObjectSetString (0, objName, OBJPROP_TEXT,      text);
   ObjectSetInteger(0, objName, OBJPROP_COLOR,      clr);
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE,   11);
   ObjectSetString (0, objName, OBJPROP_FONT,       "Arial Bold");
   ObjectSetInteger(0, objName, OBJPROP_ANCHOR,     anchor);
   ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, objName, OBJPROP_HIDDEN,     true);
   ObjectSetInteger(0, objName, OBJPROP_BACK,       false);

   ChartRedraw(0);
}


//+------------------------------------------------------------------+
//|  OnInit                                                          |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- ATR handle for Supertrend
   g_atrStHandle = iATR(_Symbol, PERIOD_CURRENT, InpStAtrPeriod);
   if(g_atrStHandle == INVALID_HANDLE)
   {
      Print("INIT ERROR: ATR (Supertrend) handle creation failed. Err: ", GetLastError());
      return INIT_FAILED;
   }

   //--- ATR handle for trailing stop (reserved — Phase 3)
   g_atrTrlHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrTrailPeriod);
   if(g_atrTrlHandle == INVALID_HANDLE)
   {
      Print("INIT ERROR: ATR (Trail) handle creation failed. Err: ", GetLastError());
      return INIT_FAILED;
   }

   //--- ADX handle (reserved — Phase 2)
   g_adxHandle = iADX(_Symbol, PERIOD_CURRENT, InpAdxPeriod);
   if(g_adxHandle == INVALID_HANDLE)
   {
      Print("INIT ERROR: ADX handle creation failed. Err: ", GetLastError());
      return INIT_FAILED;
   }

   //--- Startup banner
   PrintFormat("══════════════════════════════════════════════");
   PrintFormat("  SupertrendGridHybrid EA v1.00 — Phase 1     ");
   PrintFormat("  Symbol  : %s | TF: %s",        _Symbol, EnumToString(Period()));
   PrintFormat("  ST ATR  : %d  | Mult: %.1f",   InpStAtrPeriod, InpStMultiplier);
   PrintFormat("  ADX     : %d  | Debounce: %ds",InpAdxPeriod,   InpDebounceSec);
   PrintFormat("  Magic 1 : %d  | Magic 2: %d",  (int)InpMagic1, (int)InpMagic2);
   PrintFormat("══════════════════════════════════════════════");

   return INIT_SUCCEEDED;
}


//+------------------------------------------------------------------+
//|  OnDeinit                                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   //--- Release all indicator handles
   if(g_atrStHandle  != INVALID_HANDLE) { IndicatorRelease(g_atrStHandle);  g_atrStHandle  = INVALID_HANDLE; }
   if(g_atrTrlHandle != INVALID_HANDLE) { IndicatorRelease(g_atrTrlHandle); g_atrTrlHandle = INVALID_HANDLE; }
   if(g_adxHandle    != INVALID_HANDLE) { IndicatorRelease(g_adxHandle);    g_adxHandle    = INVALID_HANDLE; }

   //--- Remove all EA-created chart objects
   ObjectsDeleteAll(0, LABEL_PREFIX);

   PrintFormat("SupertrendGridHybrid EA deinitialized. Reason code: %d", reason);
}


//+------------------------------------------------------------------+
//|  OnTick — Main Event Loop                                        |
//+------------------------------------------------------------------+
void OnTick()
{
   //--- ── 1. DEBOUNCE GATE ─────────────────────────────────────────
   //   Prevents CPU spike from processing every single tick.
   //   The bot "sleeps" for InpDebounceSec seconds between evaluations.
   datetime now = TimeCurrent();
   if((int)(now - g_lastProcessTime) < InpDebounceSec)
      return;

   //--- ── 2. MINIMUM BARS GUARD ────────────────────────────────────
   if(iBars(_Symbol, PERIOD_CURRENT) < InpStAtrPeriod + 10)
      return;

   //--- ── 3. COMPUTE SUPERTREND DIRECTIONS ─────────────────────────
   ENUM_ST_DIR dir0 = ST_NONE; // current forming bar
   ENUM_ST_DIR dir1 = ST_NONE; // previous closed bar
   if(!GetSupertrendDirs(dir0, dir1))
      return;

   //--- ── 4. DETECT TREND FLIP ─────────────────────────────────────
   bool bullFlip = (dir1 == ST_BEAR && dir0 == ST_BULL); // Red → Green
   bool bearFlip = (dir1 == ST_BULL && dir0 == ST_BEAR); // Green → Red

   if(!bullFlip && !bearFlip) return; // no flip — nothing to act on

   //--- ── 5. DUPLICATE LABEL GUARD ────────────────────────────────
   datetime    barTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   ENUM_ST_DIR flipDir = bullFlip ? ST_BULL : ST_BEAR;

   if(g_lastLabelBar == barTime && g_lastLabelDir == flipDir)
      return; // already drew this signal on this bar

   //--- ── 6. DRAW LABEL ────────────────────────────────────────────
   if(bullFlip)
   {
      // BUY label: placed just below the candle low
      double labelPrice = iLow(_Symbol, PERIOD_CURRENT, 0) - 15.0 * _Point;
      DrawLabel(barTime, labelPrice, true);
      PrintFormat("SIGNAL ▲ BUY  — ST flipped BEAR→BULL | Bar: %s | Price: %.5f",
                  TimeToString(barTime), SymbolInfoDouble(_Symbol, SYMBOL_BID));
   }
   else // bearFlip
   {
      // SELL label: placed just above the candle high
      double labelPrice = iHigh(_Symbol, PERIOD_CURRENT, 0) + 15.0 * _Point;
      DrawLabel(barTime, labelPrice, false);
      PrintFormat("SIGNAL ▼ SELL — ST flipped BULL→BEAR | Bar: %s | Price: %.5f",
                  TimeToString(barTime), SymbolInfoDouble(_Symbol, SYMBOL_ASK));
   }

   //--- ── 7. UPDATE TRACKING STATE ────────────────────────────────
   g_lastLabelBar    = barTime;
   g_lastLabelDir    = flipDir;
   g_lastProcessTime = now;
}

//+------------------------------------------------------------------+
//  END OF PHASE 1 — SupertrendGridHybrid.mq5
//  Next: Phase 2 — Filters & Main Entry (Magic 1000)
//+------------------------------------------------------------------+
