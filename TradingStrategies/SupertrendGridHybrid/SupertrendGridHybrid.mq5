//+------------------------------------------------------------------+
//|                   SupertrendGridHybrid.mq5                       |
//|  Phase 6 — FINAL COMPLETE EA                                    |
//|  Global Kill Switches: Daily Drawdown Halt + Friday EOD Close.  |
//|  All 6 phases active. Production ready for MT5.                 |
//+------------------------------------------------------------------+
#property copyright "Rahul — SupertrendGridHybrid EA"
#property link ""
#property version "6.00"
#property description "Supertrend Grid Hybrid EA — COMPLETE (All 6 Phases)"
#property strict

#include <Trade\Trade.mqh>

//===================================================================
//  INPUT PARAMETERS
//===================================================================
input group "══ Supertrend Settings ══" input int InpStAtrPeriod =
    10;                             // ST: ATR Period
input double InpStMultiplier = 3.0; // ST: Multiplier

input group "══ ADX Filter ══" input int InpAdxPeriod = 14; // ADX Period
input double InpAdxMinLevel = 25.0; // ADX Minimum Level (trend strength)

input group "══ ATR Trailing Stop (Phase 3+) ══" input int InpAtrTrailPeriod =
    14;                             // ATR Trail: Period
input double InpAtrTrailMult = 1.5; // ATR Trail: Multiplier

input group "══ Debounce Timer ══" input int InpDebounceSec =
    60; // Debounce: seconds between evaluations

input group "══ Trade Entry (Phase 2) ══" input double InpLotSize =
    0.01;                              // Lot Size
input int InpMaxSpreadPts = 20;        // Max Allowed Spread (points)
input double InpMinFreeMargin = 100.0; // Min Free Margin (USD)
input int InpSL_Points = 200;          // Stop Loss (points)
input int InpTP_Points = 400;          // Take Profit (points)

input group
    "══ Stage 1 Trail — Fixed Pad (Phase 3) ══" input int InpS1_ActivatePts =
        50;                   // Stage 1: Activate when profit ≥ N points
input int InpS1_LockPts = 10; // Stage 1: Lock SL at Entry + N points

input group "══ Stage 2 Trail — ATR Dynamic (Phase 3) ══"
    // Uses InpAtrTrailPeriod / InpAtrTrailMult already declared above

    input group "══ Scalp Trade (Phase 4) ══" input double InpScalpLot =
        0.01;                   // Scalp: Lot Size
input int InpScalpSL_Pts = 150; // Scalp: Stop Loss (points)
input int InpScalpTP_Pts = 300; // Scalp: Take Profit (points)

input group "══ Recovery Grid (Phase 5) ══" input int InpGridStartPts =
    100;                       // Grid: Trigger if Trade1 <= -N points
input int InpGridStepPts = 50; // Grid: Distance between grid trades (points)
input double InpGridLotMult = 1.5; // Grid: Lot multiplier per grid level
input int InpBasketTPPts = 20;     // Grid: Basket TP above breakeven (points)

input group
    "══ Global Kill Switches (Phase 6) ══" input double InpMaxDailyDrawdownPct =
        3.0;                       // Max Daily Drawdown % (0 = disabled)
input bool InpFridayClose = true;  // Close all on Friday EOD?
input int InpFridayCloseHour = 21; // Friday Close: Broker Hour (0-23)
input int InpFridayCloseMin = 0;   // Friday Close: Broker Minute (0-59)

input group "══ Magic Numbers ══" input long InpMagic1 =
    1000;                    // Magic — Main Runner
input long InpMagic2 = 2000; // Magic — Scalp

//===================================================================
//  INDICATOR HANDLES
//===================================================================
int g_atrStHandle = INVALID_HANDLE;  // ATR for Supertrend calculation
int g_atrTrlHandle = INVALID_HANDLE; // ATR for trailing stop (Phase 3)
int g_adxHandle = INVALID_HANDLE;    // ADX for trend filter  (Phase 2)

//===================================================================
//  SUPERTREND DIRECTION ENUM
//===================================================================
enum ENUM_ST_DIR {
  ST_NONE = 0,
  ST_BULL = 1, // Green — price above Supertrend line
  ST_BEAR = 2  // Red   — price below Supertrend line
};

//===================================================================
//  SIGNAL TRACKING — duplicate guard
//===================================================================
datetime g_lastLabelBar = 0;          // Bar-open-time of the last drawn label
ENUM_ST_DIR g_lastLabelDir = ST_NONE; // Direction of the last drawn label

//===================================================================
//  DEBOUNCE
//===================================================================
datetime g_lastProcessTime = 0;

//===================================================================
//  PHASE 2 — STATE FLAGS
//===================================================================
bool g_trade1Stage1Active =
    false; // true once Stage 1 trail is locked (Phase 3)

//===================================================================
//  PHASE 5 — RECOVERY GRID FLAGS
//===================================================================
bool g_gridActive = false; // true when recovery grid is running
double g_gridLastPrice =
    0.0;             // price of last placed grid order (to step correctly)
int g_gridLevel = 0; // number of grid orders placed (0 = none yet)

//===================================================================
//  PHASE 6 — GLOBAL KILL STATE
//===================================================================
datetime g_haltUntilDate =
    0; // UTC date until trading is halted (drawdown trigger)
bool g_fridayKillFired = false; // prevent re-firing on same Friday minute

//===================================================================
//  TRADE OBJECT (CTrade)
//===================================================================
CTrade g_trade;

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
bool GetSupertrendDirs(ENUM_ST_DIR &dir0, ENUM_ST_DIR &dir1) {
  dir0 = ST_NONE;
  dir1 = ST_NONE;

  int lookback = InpStAtrPeriod + 100; // generous history for stable bands

  //--- Copy rates (oldest first)
  MqlRates rates[];
  ArraySetAsSeries(rates, false);
  int rCopied = CopyRates(_Symbol, PERIOD_CURRENT, 0, lookback, rates);
  if (rCopied < InpStAtrPeriod + 3) {
    Print("GetSupertrendDirs — CopyRates insufficient: ", rCopied,
          " | Err: ", GetLastError());
    return false;
  }

  //--- Copy ATR buffer (oldest first, matching rates[] indexing)
  double atrBuf[];
  ArraySetAsSeries(atrBuf, false);
  int aCopied = CopyBuffer(g_atrStHandle, 0, 0, lookback, atrBuf);
  if (aCopied < InpStAtrPeriod + 3) {
    Print("GetSupertrendDirs — CopyBuffer(ATR) insufficient: ", aCopied,
          " | Err: ", GetLastError());
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
  ArrayResize(dir, n);

  // Seed the first element
  finalUp[0] =
      (rates[0].high + rates[0].low) / 2.0 + InpStMultiplier * atrBuf[0];
  finalDn[0] =
      (rates[0].high + rates[0].low) / 2.0 - InpStMultiplier * atrBuf[0];
  dir[0] = ST_BULL;

  //--- Build Supertrend from oldest bar to newest
  for (int i = 1; i < n; i++) {
    double atr = atrBuf[i];
    double hl2 = (rates[i].high + rates[i].low) / 2.0;
    double basicUp = hl2 + InpStMultiplier * atr;
    double basicDn = hl2 - InpStMultiplier * atr;
    double prevClose = rates[i - 1].close;

    //--- Final Upper Band:
    //    Tighten only if new basicUp < prevFinalUp,
    //    or reset if previous close moved above the old upper band
    finalUp[i] = (basicUp < finalUp[i - 1] || prevClose > finalUp[i - 1])
                     ? basicUp
                     : finalUp[i - 1];

    //--- Final Lower Band:
    //    Raise only if new basicDn > prevFinalDn,
    //    or reset if previous close fell below the old lower band
    finalDn[i] = (basicDn > finalDn[i - 1] || prevClose < finalDn[i - 1])
                     ? basicDn
                     : finalDn[i - 1];

    //--- Direction: follow previous direction until price crosses the opposite
    //band
    if (dir[i - 1] == ST_BULL)
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
void DrawLabel(datetime barTime, double price, bool isBuy) {
  string objName =
      LABEL_PREFIX + TimeToString(barTime, TIME_DATE | TIME_MINUTES);

  ObjectDelete(0, objName); // remove stale label if present

  string text = isBuy ? "▲ BUY" : "▼ SELL";
  color clr = isBuy ? clrLime : clrRed;
  int anchor = isBuy ? ANCHOR_TOP : ANCHOR_BOTTOM;

  if (!ObjectCreate(0, objName, OBJ_TEXT, 0, barTime, price)) {
    Print("DrawLabel — ObjectCreate failed. ObjName: ", objName,
          " | Price: ", price, " | Err: ", GetLastError());
    return;
  }

  ObjectSetString(0, objName, OBJPROP_TEXT, text);
  ObjectSetInteger(0, objName, OBJPROP_COLOR, clr);
  ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, 11);
  ObjectSetString(0, objName, OBJPROP_FONT, "Arial Bold");
  ObjectSetInteger(0, objName, OBJPROP_ANCHOR, anchor);
  ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
  ObjectSetInteger(0, objName, OBJPROP_HIDDEN, true);
  ObjectSetInteger(0, objName, OBJPROP_BACK, false);

  ChartRedraw(0);
}

//+------------------------------------------------------------------+
//|  GetADX — returns current ADX main line value                   |
//|  Returns -1.0 on failure.                                        |
//+------------------------------------------------------------------+
double GetADX() {
  double adxBuf[];
  ArraySetAsSeries(adxBuf, true);
  if (CopyBuffer(g_adxHandle, 0, 0, 3, adxBuf) < 1) {
    PrintFormat("GetADX — CopyBuffer failed. Err: %d", GetLastError());
    return -1.0;
  }
  return adxBuf[0];
}

//+------------------------------------------------------------------+
//|  HasOpenPosition                                                  |
//|  Returns true if there is an open position on _Symbol with the  |
//|  given magic number and direction (ORDER_TYPE_BUY/SELL).        |
//+------------------------------------------------------------------+
bool HasOpenPosition(long magic, ENUM_ORDER_TYPE direction) {
  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong ticket = PositionGetTicket(i);
    if (ticket == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;
    if (PositionGetInteger(POSITION_MAGIC) != magic)
      continue;
    if ((ENUM_ORDER_TYPE)PositionGetInteger(POSITION_TYPE) != direction)
      continue;
    return true;
  }
  return false;
}

//+------------------------------------------------------------------+
//|  SetSmartFilling                                                 |
//|  Automatically detects the correct broker filling policy for EA. |
//+------------------------------------------------------------------+
void SetSmartFilling(CTrade &tradeObj) {
  int filling = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
  if ((filling & SYMBOL_FILLING_FOK) != 0)
    tradeObj.SetTypeFilling(ORDER_FILLING_FOK);
  else if ((filling & SYMBOL_FILLING_IOC) != 0)
    tradeObj.SetTypeFilling(ORDER_FILLING_IOC);
  else
    tradeObj.SetTypeFilling(ORDER_FILLING_RETURN);
}

//+------------------------------------------------------------------+
//|  PreTradeFiltersPass                                             |
//|  Runs all pre-trade safety checks before any order is sent.     |
//|  Returns true only when ALL conditions are met.                 |
//+------------------------------------------------------------------+
bool PreTradeFiltersPass(bool isBuy) {
  //--- Filter 1: ADX trend strength
  double adx = GetADX();
  if (adx < 0) {
    Print("FILTER BLOCK: ADX read failed.");
    return false;
  }
  if (adx < InpAdxMinLevel) {
    PrintFormat("FILTER BLOCK: ADX %.1f < %.1f — market not trending.", adx,
                InpAdxMinLevel);
    return false;
  }

  //--- Filter 2: Spread
  long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
  if (spreadPts > InpMaxSpreadPts) {
    PrintFormat("FILTER BLOCK: Spread %d pts > Max %d pts.", (int)spreadPts,
                InpMaxSpreadPts);
    return false;
  }

  //--- Filter 3: Free margin
  double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
  if (freeMargin < InpMinFreeMargin) {
    PrintFormat("FILTER BLOCK: Free margin %.2f < Min %.2f.", freeMargin,
                InpMinFreeMargin);
    return false;
  }

  return true; // all filters passed
}

//+------------------------------------------------------------------+
//|  OpenMainTrade                                                   |
//|  Sends the Magic 1000 entry order in the direction of the flip. |
//|  Wraps OrderSend in full GetLastError() logging.                |
//+------------------------------------------------------------------+
void OpenMainTrade(bool isBuy) {
  //--- Guard: don't stack two Main Runner trades in same direction
  ENUM_ORDER_TYPE dir = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
  if (HasOpenPosition(InpMagic1, dir)) {
    PrintFormat("ENTRY SKIP: Magic %d %s position already open.",
                (int)InpMagic1, isBuy ? "BUY" : "SELL");
    return;
  }

  //--- Pre-trade filters
  if (!PreTradeFiltersPass(isBuy))
    return;

  //--- Build price levels
  double price, sl, tp;
  double slDist = InpSL_Points * _Point;
  double tpDist = InpTP_Points * _Point;

  if (isBuy) {
    price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    sl = price - slDist;
    tp = price + tpDist;
  } else {
    price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    sl = price + slDist;
    tp = price - tpDist;
  }

  //--- Normalize to broker's digit precision
  price = NormalizeDouble(price, _Digits);
  sl = NormalizeDouble(sl, _Digits);
  tp = NormalizeDouble(tp, _Digits);

  //--- Configure CTrade
  g_trade.SetExpertMagicNumber(InpMagic1);
  g_trade.SetDeviationInPoints(10);
  SetSmartFilling(g_trade);

  //--- Send order
  bool result =
      isBuy ? g_trade.Buy(InpLotSize, _Symbol, price, sl, tp, "SGH Main BUY")
            : g_trade.Sell(InpLotSize, _Symbol, price, sl, tp, "SGH Main SELL");

  if (!result) {
    PrintFormat("ORDER FAILED: %s Magic %d | RetCode: %d | Err: %d | Msg: %s",
                isBuy ? "BUY" : "SELL", (int)InpMagic1, g_trade.ResultRetcode(),
                GetLastError(), g_trade.ResultRetcodeDescription());
  } else {
    PrintFormat("ORDER OK: %s Magic %d | Ticket: %d | Price: %.5f | SL: %.5f | "
                "TP: %.5f | Lots: %.2f",
                isBuy ? "BUY" : "SELL", (int)InpMagic1,
                (int)g_trade.ResultOrder(), price, sl, tp, InpLotSize);
    g_trade1Stage1Active = false; // reset stage flag for new trade
  }
}

//+------------------------------------------------------------------+
//|  CloseAllPositions                                               |
//|  Closes every open position and deletes all pending orders      |
//|  on the current symbol. Used by kill switches.                  |
//+------------------------------------------------------------------+
void CloseAllPositions(string reason) {
  Print("KILL SWITCH [", reason, "] — Closing all positions and orders.");

  //--- Close all open positions
  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong ticket = PositionGetTicket(i);
    if (ticket == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;

    if (!g_trade.PositionClose(ticket)) {
      PrintFormat(
          "KILL SWITCH CLOSE FAIL: Ticket %d | RetCode: %d | Err: %d | %s",
          (int)ticket, g_trade.ResultRetcode(), GetLastError(),
          g_trade.ResultRetcodeDescription());
    } else {
      PrintFormat("KILL SWITCH CLOSED: Ticket %d | Reason: %s", (int)ticket,
                  reason);
    }
  }

  //--- Delete all pending orders
  for (int i = OrdersTotal() - 1; i >= 0; i--) {
    ulong ticket = OrderGetTicket(i);
    if (ticket == 0)
      continue;
    if (OrderGetString(ORDER_SYMBOL) != _Symbol)
      continue;

    if (!g_trade.OrderDelete(ticket)) {
      PrintFormat("KILL SWITCH ORDER DEL FAIL: Ticket %d | Err: %d",
                  (int)ticket, GetLastError());
    }
  }

  //--- Reset all state flags
  g_gridActive = false;
  g_gridLevel = 0;
  g_gridLastPrice = 0.0;
  g_trade1Stage1Active = false;
  g_lastProcessTime = 0;
}

//+------------------------------------------------------------------+
//|  GlobalKillSwitchCheck                                           |
//|  Returns true if any kill condition blocks trading.             |
//|  Must be called as the VERY FIRST check in OnTick().            |
//+------------------------------------------------------------------+
bool GlobalKillSwitchCheck() {
  datetime now = TimeCurrent();
  MqlDateTime dt;
  TimeToStruct(now, dt);

  //--- ── Kill 1: Trading halted until next day (drawdown trigger) ──
  if (g_haltUntilDate > 0 && now < g_haltUntilDate) {
    // silently return true — no log spam every tick
    return true;
  } else if (g_haltUntilDate > 0 && now >= g_haltUntilDate) {
    g_haltUntilDate = 0; // reset at new day
    Print("KILL SWITCH: Daily drawdown halt lifted. Resuming trading.");
  }

  //--- ── Kill 2: Max Daily Drawdown % ──────────────────────────────
  if (InpMaxDailyDrawdownPct > 0.0) {
    double balance = AccountInfoDouble(ACCOUNT_BALANCE);
    double equity = AccountInfoDouble(ACCOUNT_EQUITY);
    double ddPct = ((balance - equity) / balance) * 100.0;

    if (ddPct >= InpMaxDailyDrawdownPct) {
      PrintFormat(
          "KILL SWITCH: Daily drawdown %.2f%% >= limit %.2f%%. Closing all.",
          ddPct, InpMaxDailyDrawdownPct);
      CloseAllPositions("MaxDailyDrawdown");

      // Halt until start of next broker day (midnight + 1 second)
      datetime nextDay = (datetime)(((long)now / 86400 + 1) * 86400 + 1);
      g_haltUntilDate = nextDay;
      PrintFormat("KILL SWITCH: Trading halted until %s.",
                  TimeToString(nextDay));
      return true;
    }
  }

  //--- ── Kill 3: Friday EOD Kill Switch ─────────────────────────────
  if (InpFridayClose) {
    // DayOfWeek: 0=Sun,1=Mon,...,5=Fri,6=Sat
    bool isFriday = (dt.day_of_week == 5);
    bool isPastTime =
        (dt.hour > InpFridayCloseHour) ||
        (dt.hour == InpFridayCloseHour && dt.min >= InpFridayCloseMin);

    if (isFriday && isPastTime && !g_fridayKillFired) {
      PrintFormat(
          "KILL SWITCH: Friday EOD at %02d:%02d broker time. Closing all.",
          InpFridayCloseHour, InpFridayCloseMin);
      CloseAllPositions("FridayEOD");
      g_fridayKillFired = true;
      return true;
    }

    // Reset flag on Saturday/Sunday so it fires again next Friday
    if (dt.day_of_week != 5)
      g_fridayKillFired = false;

    // If already fired this Friday, keep blocking entry
    if (g_fridayKillFired)
      return true;
  }

  return false; // all checks passed
}

//+------------------------------------------------------------------+
//|  ManageRecoveryGrid                                              |
//|  Called on every tick.                                          |
//|  1. Checks if Trade1 drawdown >= GridStartPts.                  |
//|  2. Activates grid mode, disables pyramiding.                   |
//|  3. Opens grid orders at fixed step intervals.                  |
//|  4. Calculates basket breakeven, sets basket TP on all trades.  |
//|  5. Detects basket closure and resets to State 0.               |
//+------------------------------------------------------------------+
void ManageRecoveryGrid() {
  //--- ── PHASE 5a: Check if grid should be triggered ───────────────────
  if (!g_gridActive) {
    // Find any open Magic 1000 position
    for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0)
        continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol)
        continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic1)
        continue;

      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      ENUM_POSITION_TYPE posType =
          (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double drawdownPts = 0.0;

      if (posType == POSITION_TYPE_BUY)
        drawdownPts = (openPrice - currentBid) / _Point; // negative = in loss
      else
        drawdownPts = (currentAsk - openPrice) / _Point;

      if (drawdownPts >= InpGridStartPts) {
        g_gridActive = true;
        g_gridLastPrice =
            (posType == POSITION_TYPE_BUY) ? currentBid : currentAsk;
        g_gridLevel = 0;
        PrintFormat("GRID TRIGGERED: Trade1 Ticket %d | Drawdown %.0f pts >= "
                    "threshold %d pts",
                    (int)ticket, drawdownPts, InpGridStartPts);
      }
      break; // only check first Magic 1000 position
    }
    return; // Grid not active
  }

  //--- ── PHASE 5b: Reset check — has basket fully closed? ──────────────
  if (CountPositions(InpMagic1) == 0) {
    PrintFormat("GRID CLOSED: Basket fully closed. Resetting to State 0.");
    g_gridActive = false;
    g_gridLastPrice = 0.0;
    g_gridLevel = 0;
    g_trade1Stage1Active = false;
    return;
  }

  //--- ── PHASE 5c: Determine basket direction ───────────────────────────
  ENUM_POSITION_TYPE basketDir = POSITION_TYPE_BUY;
  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong t = PositionGetTicket(i);
    if (t == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;
    if (PositionGetInteger(POSITION_MAGIC) != InpMagic1)
      continue;
    basketDir = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
    break;
  }

  double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
  double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
  double stepDist = InpGridStepPts * _Point;

  //--- ── PHASE 5d: Open next grid level if step distance reached ───
  bool openNextLevel = false;
  if (basketDir == POSITION_TYPE_BUY)
    openNextLevel = (g_gridLastPrice - currentBid) >= stepDist;
  else
    openNextLevel = (currentAsk - g_gridLastPrice) >= stepDist;

  if (openNextLevel) {
    double lotForLevel = InpLotSize * MathPow(InpGridLotMult, g_gridLevel + 1);
    lotForLevel = NormalizeDouble(lotForLevel, 2);

    //--- Configure CTrade
    g_trade.SetExpertMagicNumber(InpMagic1);
    g_trade.SetDeviationInPoints(10);
    SetSmartFilling(g_trade);

    bool gResult =
        (basketDir == POSITION_TYPE_BUY)
            ? g_trade.Buy(lotForLevel, _Symbol, 0, 0, 0, "SGH Grid Buy")
            : g_trade.Sell(lotForLevel, _Symbol, 0, 0, 0, "SGH Grid Sell");

    if (!gResult) {
      PrintFormat("GRID ORDER FAILED: Level %d | Lots: %.2f | RetCode: %d | "
                  "Err: %d | %s",
                  g_gridLevel + 1, lotForLevel, g_trade.ResultRetcode(),
                  GetLastError(), g_trade.ResultRetcodeDescription());
    } else {
      g_gridLevel++;
      g_gridLastPrice =
          (basketDir == POSITION_TYPE_BUY) ? currentBid : currentAsk;
      PrintFormat("GRID ORDER OK: Level %d | Ticket %d | Lots: %.2f",
                  g_gridLevel, (int)g_trade.ResultOrder(), lotForLevel);
    }
  }

  //--- ── PHASE 5e: Basket Breakeven Calculator + Set Basket TP ───────
  double totalVolume = 0.0;
  double weightedSum = 0.0;
  int basketCount = 0;

  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong t = PositionGetTicket(i);
    if (t == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;
    if (PositionGetInteger(POSITION_MAGIC) != InpMagic1)
      continue;

    double vol = PositionGetDouble(POSITION_VOLUME);
    double entry = PositionGetDouble(POSITION_PRICE_OPEN);
    weightedSum += entry * vol;
    totalVolume += vol;
    basketCount++;
  }

  if (basketCount > 0 && totalVolume > 0.0) {
    double breakevenPrice = weightedSum / totalVolume;
    double basketTP;

    if (basketDir == POSITION_TYPE_BUY)
      basketTP =
          NormalizeDouble(breakevenPrice + InpBasketTPPts * _Point, _Digits);
    else
      basketTP =
          NormalizeDouble(breakevenPrice - InpBasketTPPts * _Point, _Digits);

    //--- Apply basket TP to all Magic 1000 positions
    for (int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if (t == 0)
        continue;
      if (PositionGetString(POSITION_SYMBOL) != _Symbol)
        continue;
      if (PositionGetInteger(POSITION_MAGIC) != InpMagic1)
        continue;

      double currentSL = PositionGetDouble(POSITION_SL);
      double currentTP = PositionGetDouble(POSITION_TP);

      if (MathAbs(currentTP - basketTP) > _Point) // only modify if TP changed
      {
        if (!g_trade.PositionModify(t, currentSL, basketTP)) {
          PrintFormat("BASKET TP SET FAIL: Ticket %d | Err: %d | %s", (int)t,
                      GetLastError(), g_trade.ResultRetcodeDescription());
        }
      }
    }
  }
}

//+------------------------------------------------------------------+
//|  CountPositions                                                  |
//|  Returns the number of open positions matching symbol + magic.  |
//+------------------------------------------------------------------+
int CountPositions(long magic) {
  int count = 0;
  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong ticket = PositionGetTicket(i);
    if (ticket == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;
    if (PositionGetInteger(POSITION_MAGIC) != magic)
      continue;
    count++;
  }
  return count;
}

//+------------------------------------------------------------------+
//|  OpenScalpTrade                                                  |
//|  Pyramiding module — Magic 2000.                                 |
//|  Conditions to fire:                                            |
//|   1. Total same-direction positions <= 1 (cap = 2 total).       |
//|   2. Magic 1000 trade is open.                                   |
//|   3. Stage 1 trail is active (g_trade1Stage1Active == true).    |
//|   4. Current candle breaks prev candle High (BUY) or Low (SELL).|
//+------------------------------------------------------------------+
void OpenScalpTrade(bool isBuy) {
  //--- Guard 1: Max 2 open positions in same direction (Magic1 + Magic2
  //combined)
  ENUM_ORDER_TYPE dir = isBuy ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
  int sameDir = 0;
  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong ticket = PositionGetTicket(i);
    if (ticket == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;
    if ((ENUM_ORDER_TYPE)PositionGetInteger(POSITION_TYPE) != dir)
      continue;
    sameDir++;
  }
  if (sameDir >= 2) {
    // max 2 open in same direction reached
    return;
  }

  //--- Guard 2: Magic 1000 trade must be open
  if (!HasOpenPosition(InpMagic1, dir)) {
    Print("SCALP SKIP: Magic 1000 trade not open in same direction.");
    return;
  }

  //--- Guard 3: Stage 1 trail must be locked
  if (!g_trade1Stage1Active) {
    Print("SCALP SKIP: Stage 1 trail not yet active.");
    return;
  }

  //--- Guard 4: Already have a Magic 2000 trade open?
  if (HasOpenPosition(InpMagic2, dir)) {
    Print("SCALP SKIP: Magic 2000 position already open.");
    return;
  }

  //--- Momentum Trigger: price must break prev candle High (BUY) or Low (SELL)
  double prevHigh = iHigh(_Symbol, PERIOD_CURRENT, 1);
  double prevLow = iLow(_Symbol, PERIOD_CURRENT, 1);
  double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
  double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

  if (isBuy && ask <= prevHigh) {
    Print("SCALP SKIP: BUY — Ask has not broken prev candle High yet.");
    return;
  }
  if (!isBuy && bid >= prevLow) {
    Print("SCALP SKIP: SELL — Bid has not broken prev candle Low yet.");
    return;
  }

  //--- Build price levels (independent SL/TP for scalp)
  double price, sl, tp;
  double slDist = InpScalpSL_Pts * _Point;
  double tpDist = InpScalpTP_Pts * _Point;

  if (isBuy) {
    price = ask;
    sl = NormalizeDouble(price - slDist, _Digits);
    tp = NormalizeDouble(price + tpDist, _Digits);
  } else {
    price = bid;
    sl = NormalizeDouble(price + slDist, _Digits);
    tp = NormalizeDouble(price - tpDist, _Digits);
  }

  //--- Configure CTrade for Magic 2000
  g_trade.SetExpertMagicNumber(InpMagic2);
  g_trade.SetDeviationInPoints(10);
  g_trade.SetTypeFilling(ORDER_FILLING_IOC);

  bool result =
      isBuy
          ? g_trade.Buy(InpScalpLot, _Symbol, price, sl, tp, "SGH Scalp BUY")
          : g_trade.Sell(InpScalpLot, _Symbol, price, sl, tp, "SGH Scalp SELL");

  if (!result) {
    PrintFormat("SCALP FAILED: %s Magic %d | RetCode: %d | Err: %d | Msg: %s",
                isBuy ? "BUY" : "SELL", (int)InpMagic2, g_trade.ResultRetcode(),
                GetLastError(), g_trade.ResultRetcodeDescription());
  } else {
    PrintFormat("SCALP OK: %s Magic %d | Ticket: %d | Price: %.5f | SL: %.5f | "
                "TP: %.5f | Lots: %.2f",
                isBuy ? "BUY" : "SELL", (int)InpMagic2,
                (int)g_trade.ResultOrder(), price, sl, tp, InpScalpLot);
  }

  //--- Restore Magic 1000 as default on g_trade
  g_trade.SetExpertMagicNumber(InpMagic1);
}

//+------------------------------------------------------------------+
//|  ManageMainTrail                                                 |
//|  Called on every tick. Manages Stage 1 and Stage 2 trailing     |
//|  for the open Magic 1000 position.                              |
//|                                                                  |
//|  Stage 1: When floating profit ≥ InpS1_ActivatePts,            |
//|           move SL to (EntryPrice +/- InpS1_LockPts * _Point).  |
//|           Sets g_trade1Stage1Active = true.                     |
//|  Stage 2: Once Stage 1 active, trail SL using ATR * Multiplier. |
//|           SL only moves TOWARD profit; never below Stage 1 lock. |
//+------------------------------------------------------------------+
void ManageMainTrail() {
  for (int i = PositionsTotal() - 1; i >= 0; i--) {
    ulong ticket = PositionGetTicket(i);
    if (ticket == 0)
      continue;
    if (PositionGetString(POSITION_SYMBOL) != _Symbol)
      continue;
    if (PositionGetInteger(POSITION_MAGIC) != InpMagic1)
      continue;

    ENUM_POSITION_TYPE posType =
        (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
    double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
    double currentSL = PositionGetDouble(POSITION_SL);
    double currentTP = PositionGetDouble(POSITION_TP);
    double currentBid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
    double currentAsk = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

    double s1LockPts = InpS1_LockPts * _Point;
    double s1ActivatePts = InpS1_ActivatePts * _Point;

    //--- ── STAGE 1: Fixed Breakeven + Pad Lock ─────────────────────
    if (!g_trade1Stage1Active) {
      bool s1Triggered = false;
      double requiredSL = 0.0;

      if (posType == POSITION_TYPE_BUY) {
        // Profit in points = Bid - OpenPrice
        if ((currentBid - openPrice) >= s1ActivatePts) {
          requiredSL = NormalizeDouble(openPrice + s1LockPts, _Digits);
          s1Triggered =
              (requiredSL > currentSL + _Point); // only raise, never lower
        }
      } else // SELL
      {
        // Profit in points = OpenPrice - Ask
        if ((openPrice - currentAsk) >= s1ActivatePts) {
          requiredSL = NormalizeDouble(openPrice - s1LockPts, _Digits);
          s1Triggered = (requiredSL < currentSL - _Point ||
                         currentSL == 0); // only lower, never raise
        }
      }

      if (s1Triggered) {
        g_trade.SetExpertMagicNumber(InpMagic1);
        if (g_trade.PositionModify(ticket, requiredSL, currentTP)) {
          g_trade1Stage1Active = true;
          PrintFormat("TRAIL STAGE 1 LOCKED: Ticket %d | SL moved to %.5f "
                      "(Entry+%d pts)",
                      (int)ticket, requiredSL, InpS1_LockPts);
        } else {
          PrintFormat(
              "TRAIL STAGE 1 FAIL: Ticket %d | RetCode: %d | Err: %d | %s",
              (int)ticket, g_trade.ResultRetcode(), GetLastError(),
              g_trade.ResultRetcodeDescription());
        }
      }
      return; // Stage 1 not yet locked — do not run Stage 2
    }

    //--- ── STAGE 2: ATR Dynamic Trail ──────────────────────────────
    //   Only executes when Stage 1 is already locked.
    //   Reads live ATR from handle (bar[1] = completed bar).
    double atrBuf[];
    ArraySetAsSeries(atrBuf, true);
    if (CopyBuffer(g_atrTrlHandle, 0, 1, 1, atrBuf) < 1) {
      PrintFormat("TRAIL STAGE 2: ATR CopyBuffer failed. Err: %d",
                  GetLastError());
      return;
    }
    double atrVal = atrBuf[0] * InpAtrTrailMult;
    double stage1Floor = 0.0; // Minimum SL allowed (Stage 1 lock price)
    double newSL = 0.0;
    bool shouldModify = false;

    if (posType == POSITION_TYPE_BUY) {
      stage1Floor = NormalizeDouble(openPrice + s1LockPts, _Digits);
      newSL = NormalizeDouble(currentBid - atrVal, _Digits);
      // Only move SL higher AND never below Stage 1 floor
      newSL = MathMax(newSL, stage1Floor);
      shouldModify = (newSL > currentSL + _Point);
    } else // SELL
    {
      stage1Floor = NormalizeDouble(openPrice - s1LockPts, _Digits);
      newSL = NormalizeDouble(currentAsk + atrVal, _Digits);
      // Only move SL lower AND never above Stage 1 floor
      newSL = MathMin(newSL, stage1Floor);
      shouldModify = (newSL < currentSL - _Point || currentSL == 0);
    }

    if (shouldModify) {
      if (g_trade.PositionModify(ticket, newSL, currentTP)) {
        PrintFormat("TRAIL STAGE 2: Ticket %d | SL → %.5f (ATR %.5f x %.1f)",
                    (int)ticket, newSL, atrBuf[0], InpAtrTrailMult);
      } else {
        PrintFormat(
            "TRAIL STAGE 2 FAIL: Ticket %d | RetCode: %d | Err: %d | %s",
            (int)ticket, g_trade.ResultRetcode(), GetLastError(),
            g_trade.ResultRetcodeDescription());
      }
    }
  } // end for
}

//+------------------------------------------------------------------+
//|  OnInit                                                          |
//+------------------------------------------------------------------+
int OnInit() {
  //--- ATR handle for Supertrend
  g_atrStHandle = iATR(_Symbol, PERIOD_CURRENT, InpStAtrPeriod);
  if (g_atrStHandle == INVALID_HANDLE) {
    Print("INIT ERROR: ATR (Supertrend) handle creation failed. Err: ",
          GetLastError());
    return INIT_FAILED;
  }

  //--- ATR handle for trailing stop (Phase 3)
  g_atrTrlHandle = iATR(_Symbol, PERIOD_CURRENT, InpAtrTrailPeriod);
  if (g_atrTrlHandle == INVALID_HANDLE) {
    Print("INIT ERROR: ATR (Trail) handle creation failed. Err: ",
          GetLastError());
    return INIT_FAILED;
  }

  //--- ADX handle
  g_adxHandle = iADX(_Symbol, PERIOD_CURRENT, InpAdxPeriod);
  if (g_adxHandle == INVALID_HANDLE) {
    Print("INIT ERROR: ADX handle creation failed. Err: ", GetLastError());
    return INIT_FAILED;
  }

  //--- Configure CTrade defaults
  g_trade.SetExpertMagicNumber(InpMagic1);
  g_trade.SetDeviationInPoints(10);
  SetSmartFilling(g_trade);
  g_trade.LogLevel(LOG_LEVEL_ERRORS);

  //--- Startup banner
  PrintFormat("══════════════════════════════════════════════");
  PrintFormat("  SupertrendGridHybrid EA v6.00 — FINAL (All 6 Phases)");
  PrintFormat("  Symbol  : %s | TF: %s", _Symbol, EnumToString(Period()));
  PrintFormat("  ST ATR  : %d  | Mult: %.1f", InpStAtrPeriod, InpStMultiplier);
  PrintFormat("  ADX Min : %.0f | Spread Max: %d", InpAdxMinLevel,
              InpMaxSpreadPts);
  PrintFormat("  Lot: %.2f | SL: %d pts | TP: %d pts", InpLotSize, InpSL_Points,
              InpTP_Points);
  PrintFormat("  S1 Activate: %d pts | S1 Lock: %d pts", InpS1_ActivatePts,
              InpS1_LockPts);
  PrintFormat("  S2 ATR Trl: %d x %.1f", InpAtrTrailPeriod, InpAtrTrailMult);
  PrintFormat("  Scalp: %.2f lots | SL:%d | TP:%d", InpScalpLot, InpScalpSL_Pts,
              InpScalpTP_Pts);
  PrintFormat("  Grid: Trig-%d | Step-%d | Mult-%.1f | BE+%d", InpGridStartPts,
              InpGridStepPts, InpGridLotMult, InpBasketTPPts);
  PrintFormat("  Drawdown Kill: %.1f%% | Friday Close: %s @%02d:%02d",
              InpMaxDailyDrawdownPct, InpFridayClose ? "YES" : "NO",
              InpFridayCloseHour, InpFridayCloseMin);
  PrintFormat("  Magic 1 : %d  | Magic 2: %d", (int)InpMagic1, (int)InpMagic2);
  PrintFormat("══════════════════════════════════════════════");

  return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//|  OnDeinit                                                        |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
  //--- Release all indicator handles
  if (g_atrStHandle != INVALID_HANDLE) {
    IndicatorRelease(g_atrStHandle);
    g_atrStHandle = INVALID_HANDLE;
  }
  if (g_atrTrlHandle != INVALID_HANDLE) {
    IndicatorRelease(g_atrTrlHandle);
    g_atrTrlHandle = INVALID_HANDLE;
  }
  if (g_adxHandle != INVALID_HANDLE) {
    IndicatorRelease(g_adxHandle);
    g_adxHandle = INVALID_HANDLE;
  }

  //--- Remove all EA-created chart objects
  ObjectsDeleteAll(0, LABEL_PREFIX);

  PrintFormat("SupertrendGridHybrid EA deinitialized. Reason code: %d", reason);
}

//+------------------------------------------------------------------+
//|  OnTick — Main Event Loop                                        |
//+------------------------------------------------------------------+
void OnTick() {
  //--- ── 0. GLOBAL KILL SWITCH ────────────────────────────────────────
  //   First check in OnTick — overrides everything if triggered.
  if (GlobalKillSwitchCheck())
    return;

  //--- ── 1. DEBOUNCE GATE ─────────────────────────────────────────
  datetime now = TimeCurrent();
  if ((int)(now - g_lastProcessTime) < InpDebounceSec) {
    // Even within debounce, run trail + grid manager every tick for precision
    ManageMainTrail();
    ManageRecoveryGrid();
    return;
  }

  //--- ── 2. MINIMUM BARS GUARD ────────────────────────────────────
  if (iBars(_Symbol, PERIOD_CURRENT) < InpStAtrPeriod + 10)
    return;

  //--- ── 3. COMPUTE SUPERTREND DIRECTIONS ─────────────────────────
  ENUM_ST_DIR dir0 = ST_NONE; // current forming bar
  ENUM_ST_DIR dir1 = ST_NONE; // previous closed bar
  if (!GetSupertrendDirs(dir0, dir1))
    return;

  //--- ── 4. DETECT TREND FLIP ─────────────────────────────────────
  bool bullFlip = (dir1 == ST_BEAR && dir0 == ST_BULL); // Red → Green
  bool bearFlip = (dir1 == ST_BULL && dir0 == ST_BEAR); // Green → Red

  if (!bullFlip && !bearFlip)
    return; // no flip — nothing to act on

  //--- ── 5. DUPLICATE LABEL GUARD ────────────────────────────────
  datetime barTime = iTime(_Symbol, PERIOD_CURRENT, 0);
  ENUM_ST_DIR flipDir = bullFlip ? ST_BULL : ST_BEAR;

  if (g_lastLabelBar == barTime && g_lastLabelDir == flipDir)
    return; // already drew this signal on this bar

  //--- ── 6. DRAW LABEL ────────────────────────────────────────────
  if (bullFlip) {
    double labelPrice = iLow(_Symbol, PERIOD_CURRENT, 0) - 15.0 * _Point;
    DrawLabel(barTime, labelPrice, true);
    PrintFormat("SIGNAL ▲ BUY  — ST flipped BEAR→BULL | Bar: %s | Price: %.5f",
                TimeToString(barTime), SymbolInfoDouble(_Symbol, SYMBOL_BID));
  } else {
    double labelPrice = iHigh(_Symbol, PERIOD_CURRENT, 0) + 15.0 * _Point;
    DrawLabel(barTime, labelPrice, false);
    PrintFormat("SIGNAL ▼ SELL — ST flipped BULL→BEAR | Bar: %s | Price: %.5f",
                TimeToString(barTime), SymbolInfoDouble(_Symbol, SYMBOL_ASK));
  }

  //--- ── 7. EXECUTE MAIN TRADE (Magic 1000) ───────────────────────
  OpenMainTrade(bullFlip);

  //--- ── 8. MANAGE TRAILING STOP (Magic 1000) ─────────────────────
  ManageMainTrail();

  //--- ── 9. PYRAMIDING: Scalp Trade (Magic 2000) ──────────────────
  //   Disabled if recovery grid is active
  if (!g_gridActive)
    OpenScalpTrade(bullFlip);

  //--- ── 10. RECOVERY GRID MANAGER ──────────────────────────────
  ManageRecoveryGrid();

  //--- ── 11. UPDATE TRACKING STATE ─────────────────────────────
  g_lastLabelBar = barTime;
  g_lastLabelDir = flipDir;
  g_lastProcessTime = now;
}

//+------------------------------------------------------------------+
//  SUPERTREND GRID HYBRID EA — v6.00 COMPLETE                       |
//  All 6 Phases Active:                                             |
//  1. Core indicators + visuals   4. Pyramiding (Magic 2000)        |
//  2. Filters + entry (Magic 1000) 5. Recovery Grid                 |
//  3. Multi-stage trailing        6. Drawdown halt + Friday EOD     |
//+------------------------------------------------------------------+
