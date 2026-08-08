//+------------------------------------------------------------------+
//|                                       RSIFibRetracementEA.mq5    |
//|               Copyright 2026, RSI Fib Retracement EA Team        |
//|                                                                  |
//| Expert Advisor for MT5 based on RSI zone exit and custom Fib     |
//| projections. strictly designed for demo testing and safety.       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property link      ""
#property version   "3.01"
#property description "RSI Custom Fibonacci Limit Expert Advisor for MT5 (Strict Demo/Tester Research)"
#property strict

#include <Trade/Trade.mqh>

//--- State Machine Enums
enum ENUM_STATE
{
   STATE_IDLE = 0,               // Searching for RSI Crossover signal
   STATE_WAITING_FOR_ANCHOR = 1, // RSI Signal active, waiting for opposite candle anchor
   STATE_PENDING_ORDER = 2,      // Limit Order placed, waiting for execution or expiry
   STATE_IN_POSITION = 3,        // Position active
   STATE_FAULT = 4               // Ambiguous/unsafe broker state: no new entries
};

enum ENUM_PROTECTION_STATUS
{
   PROTECTION_NOT_FOUND = 0,
   PROTECTION_OK = 1,
   PROTECTION_INVALID = 2
};

enum ENUM_SIGNAL_DIR
{
   SIGNAL_NONE = 0,
   SIGNAL_BUY = 1,
   SIGNAL_SELL = 2
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+
//--- Security & Account Protection
input group "=== Guard & Risk Parameters ==="
input bool     InpDemoOnly              = true;        // Demo Account Only Guard
input ulong    InpMagicNumber           = 20260803;    // EA Magic Number
input double   InpRiskPercent           = 0.25;        // Risk per trade (% of Equity, max 1.00%)
input double   InpMaxDailyLossPct       = 1.0;         // Max Daily Loss/Drawdown (% of Equity)
input int      InpMaxDailyTrades        = 2;           // Max new positions per day (0 = disabled)
input int      InpMaxConsecutiveLosses  = 2;           // Max consecutive losses per day (0 = disabled)
input int      InpMaxSpreadPoints       = 0;           // Max allowed spread in points (0 = disabled)
input double   InpMaxSpreadRiskPct      = 25.0;        // Max spread as % of Entry-to-SL distance (0 = disabled)
input bool     InpCloseUnprotectedPosition = true;     // Close EA position if broker SL/TP is missing
input uint     InpStateWatchdogMs       = 1000;        // Broker-state watchdog interval (milliseconds)
input bool     InpCostModelVerified     = false;       // Explicit broker cost verification gate (mandatory)
input double   InpEstimatedRoundTurnCostPerLot = 0.0;  // Verified commission/fees per lot in account currency (>=0)
input int      InpAdverseEntrySlippageTicks = 1;       // Worst-case adverse slippage at pending fill for sizing
input int      InpAdverseStopSlippageTicks = 1;        // Worst-case adverse slippage beyond SL for sizing
input double   InpMaxFreeMarginUsagePct = 25.0;        // Max share of current free margin for a new order
input int      InpMinDaysToContractExpiry = 7;         // Reject expiring contracts inside this horizon

//--- Session Filter
input group "=== Session Filter ==="
input bool     InpUseSessionFilter      = false;       // Enable Session Time Filter
input int      InpStartHour             = 8;           // Session Start Hour (Broker time)
input int      InpEndHour               = 20;          // Session End Hour (Broker time)

//--- RSI Parameters
input group "=== RSI Parameters ==="
input int                InpRSI_Period        = 14;          // RSI Period
input ENUM_APPLIED_PRICE InpRSI_AppliedPrice  = PRICE_CLOSE; // RSI Applied Price
input ENUM_TIMEFRAMES    InpSignalTimeframe   = PERIOD_CURRENT; // Signal timeframe (current chart by default)
input double             InpOversoldLevel     = 30.0;        // RSI Oversold Level (Buy trigger)
input double             InpOverboughtLevel   = 70.0;        // RSI Overbought Level (Sell trigger)

//--- RSI Quality Filter
input group "=== RSI Quality Filter ==="
input bool               InpUseRSIQualityFilter = false;       // Enable RSI Quality Filter
input int                InpRSIMinBarsInZone    = 2;           // Min consecutive bars in RSI zone before exit
input double             InpRSIMinExitDelta     = 4.0;         // Min RSI exit delta between bar 2 and bar 1

//--- Multi-Timeframe Trend Filter
input group "=== Multi-Timeframe Trend Filter ==="
input bool               InpUseMTFTrendFilter   = false;       // Enable MTF Trend Filter
input ENUM_TIMEFRAMES    InpMTFTimeframe        = PERIOD_H1;   // HTF Trend Timeframe
input int                InpMTFEMAPeriod        = 200;         // HTF EMA Period
input bool               InpMTFUseRSIConfirm    = false;       // Enable HTF RSI Confirmation
input int                InpMTFRSIPeriod        = 14;          // HTF RSI Period
input double             InpMTFRSIMidline       = 50.0;        // HTF RSI Midline Level

//--- Volatility Regime Filter
input group "=== Volatility Regime Filter ==="
input bool               InpUseVolatilityRegime = false;       // Enable Volatility Regime Filter
input int                InpVolFastATRPeriod    = 14;          // Fast ATR Period
input int                InpVolSlowATRPeriod    = 100;         // Slow ATR Period
input double             InpVolMinRatio         = 0.80;        // Min Fast/Slow ATR Ratio
input double             InpVolMaxRatio         = 2.20;        // Max Fast/Slow ATR Ratio

//--- Anchoring & Setup Timing
input group "=== Anchoring & Timing ==="
input int      InpMinImpulseBars        = 1;           // Min bars after signal before anchor
input int      InpAnchorWaitBars        = 8;           // Max bars to wait for anchor candle
input int      InpPendingOrderBars      = 8;           // Pending order lifespan in bars
input double   InpMinRangeATR           = 0.0;         // Min setup range in ATR multiples (0 = off)
input double   InpMaxRangeATR           = 0.0;         // Max setup range in ATR multiples (0 = off)
input int      InpATR_Period            = 14;          // ATR Period for range filter

//--- Fibonacci Custom Ratios
input group "=== Fibonacci Geometry Ratios ==="
input double   InpEntryRatio            = -0.21;       // Limit Entry Ratio (< 0.0)
input double   InpStopRatio             = -0.29;       // Invalidation Stop Ratio (< EntryRatio)
input double   InpTargetRatio           = 2.56;        // Take Profit Ratio (>= 1.0)
input double   InpVisualTargetRatio     = 2.64;        // Second Visual Target Line Ratio

//--- Adaptive Geometry (chart-dependent SL/TP)
input group "=== Adaptive Geometry (ATR-based) ==="
input bool     InpUseAdaptiveSL         = false;       // Adapt SL floor to chart volatility (ATR)
input double   InpMinSLATRMultiple      = 1.5;         // Minimum SL distance in ATR multiples
input bool     InpUseAdaptiveTP         = false;       // Adapt TP to fixed R:R from actual SL distance
input double   InpTPRiskMultiple        = 3.0;         // TP distance = SL distance x this R:R multiple

//--- Position Management
input group "=== Position Management ==="
input bool     InpUseBreakEven          = false;       // Enable structural break-even management
input double   InpBETriggerFibRatio     = 1.00;        // Fib ratio that triggers break-even
input int      InpBEOffsetTicks         = 1;           // Favorable offset from entry in trade ticks
input bool     InpUseFibTrailingStop    = false;       // Enable multi-level Fibonacci trailing stop

//--- Visualization & Logging
input group "=== Display & Diagnostics ==="
input bool     InpDrawChartObjects      = true;        // Draw Fib setup lines on chart
input bool     InpVerboseLog            = true;        // Detailed diagnostic log messages
input bool     InpShowDashboard         = true;        // Lightweight on-chart runtime status
input bool     InpDashboardInTester     = false;       // Show dashboard in Strategy Tester

//--- Strategy Tester Fitness
input group "=== Strategy Tester Fitness ==="
input int      InpTesterMinTrades       = 40;          // Reject samples smaller than this
input int      InpTesterTargetTrades    = 120;         // Full sample weight at/above this size
input double   InpTesterMaxDDPct        = 30.0;        // Reject equity drawdown at/above this value
input double   InpTesterPFCap           = 5.0;         // Cap outlier profit-factor contribution
input double   InpTesterSharpeCap       = 5.0;         // Cap outlier Sharpe contribution

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES & STRUCTURES                                    |
//+------------------------------------------------------------------+
struct SetupStruct
{
   ENUM_SIGNAL_DIR dir;
   datetime        signal_time;
   datetime        anchor_time;
   double          P0;
   double          P1;
   double          range;
   double          entry_price;
   double          stop_price;
   double          target_price;
   double          visual_target_price;
   datetime        pending_order_time;
   ulong           pending_ticket;
   ulong           position_ticket;

   void Reset()
   {
      dir                 = SIGNAL_NONE;
      signal_time         = 0;
      anchor_time         = 0;
      P0                  = 0.0;
      P1                  = 0.0;
      range               = 0.0;
      entry_price         = 0.0;
      stop_price          = 0.0;
      target_price        = 0.0;
      visual_target_price = 0.0;
      pending_order_time  = 0;
      pending_ticket      = 0;
      position_ticket     = 0;
   }
};

struct DailyPositionStat
{
   long   identifier;
   double pnl;
   long   last_exit_msc;
   bool   has_entry;
   bool   has_exit;
};

struct BrokerSnapshot
{
   int   symbol_positions;
   int   symbol_orders;
   int   managed_positions;
   int   managed_orders;
   int   managed_limits;
   int   managed_unsupported;
   ulong position_ticket;
   ulong limit_ticket;

   void Reset()
   {
      symbol_positions = 0;
      symbol_orders = 0;
      managed_positions = 0;
      managed_orders = 0;
      managed_limits = 0;
      managed_unsupported = 0;
      position_ticket = 0;
      limit_ticket = 0;
   }
};

CTrade      m_trade;
CTrade      m_safety_trade;
int         m_rsi_handle = INVALID_HANDLE;
int         m_atr_handle = INVALID_HANDLE;
int         m_mtf_ema_handle = INVALID_HANDLE;
int         m_mtf_rsi_handle = INVALID_HANDLE;
int         m_vol_fast_atr_handle = INVALID_HANDLE;
int         m_vol_slow_atr_handle = INVALID_HANDLE;
datetime    m_last_bar_time = 0;
ENUM_STATE  m_state = STATE_IDLE;
SetupStruct m_setup;
string      m_obj_prefix = "";
ENUM_TIMEFRAMES m_timeframe = PERIOD_CURRENT;
datetime    m_last_emergency_close_attempt = 0;
datetime    m_last_lifecycle_close_attempt = 0;
datetime    m_last_cancel_attempt = 0;
bool        m_sync_required = true;
ulong       m_last_broker_scan_ms = 0;
datetime    m_last_break_even_attempt = 0;
ulong       m_last_dashboard_ms = 0;
ulong       m_residual_order_ticket = 0;
int         m_empty_broker_confirmations = 0;
string      m_fault_reason = "";
string      m_last_status = "initializing";
string      m_protection_status = "N/A";
bool        m_daily_stats_dirty = true;
datetime    m_daily_cache_day = 0;
int         m_daily_cache_trades = 0;
double      m_daily_cache_pnl = 0.0;
int         m_daily_cache_consecutive_losses = 0;

//+------------------------------------------------------------------+
//| Indicator Handle Management Helper                               |
//+------------------------------------------------------------------+
void ReleaseAllHandles()
{
   if (m_rsi_handle != INVALID_HANDLE)
   {
      IndicatorRelease(m_rsi_handle);
      m_rsi_handle = INVALID_HANDLE;
   }

   if (m_atr_handle != INVALID_HANDLE)
   {
      IndicatorRelease(m_atr_handle);
      m_atr_handle = INVALID_HANDLE;
   }

   if (m_mtf_ema_handle != INVALID_HANDLE)
   {
      IndicatorRelease(m_mtf_ema_handle);
      m_mtf_ema_handle = INVALID_HANDLE;
   }

   if (m_mtf_rsi_handle != INVALID_HANDLE)
   {
      IndicatorRelease(m_mtf_rsi_handle);
      m_mtf_rsi_handle = INVALID_HANDLE;
   }

   if (m_vol_fast_atr_handle != INVALID_HANDLE)
   {
      IndicatorRelease(m_vol_fast_atr_handle);
      m_vol_fast_atr_handle = INVALID_HANDLE;
   }

   if (m_vol_slow_atr_handle != INVALID_HANDLE)
   {
      IndicatorRelease(m_vol_slow_atr_handle);
      m_vol_slow_atr_handle = INVALID_HANDLE;
   }
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // 1. Non-bypassable demo/tester guard. The input is retained for preset
   // compatibility, but false is rejected by ValidateInputs().
   if (!IsStrictDemoContext())
   {
      Print("CRITICAL ERROR: [RSIFibEA] Only Strategy Tester or a demo account is allowed. EA execution aborted.");
      return INIT_FAILED;
   }

   // 2. Validate Inputs
   if (!ValidateInputs())
   {
      Print("CRITICAL ERROR: [RSIFibEA] Input parameter validation failed!");
      return INIT_PARAMETERS_INCORRECT;
   }

   m_timeframe = (InpSignalTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : InpSignalTimeframe;

   // A lifecycle cutoff blocks new exposure, but must never prevent restart
   // reconciliation of an already managed pending order or position.
   bool initial_lifecycle_ok = CheckContractLifecycle();
   if (!initial_lifecycle_ok)
   {
      Print("GUARD REJECT: [RSIFibEA] Contract lifecycle blocks new exposure; existing managed exposure will still be synchronized.");
   }

   // 3. Initialize Indicator Handles
   m_rsi_handle = iRSI(_Symbol, m_timeframe, InpRSI_Period, InpRSI_AppliedPrice);
   if (m_rsi_handle == INVALID_HANDLE)
   {
      PrintFormat("CRITICAL ERROR: [RSIFibEA] Failed to create iRSI handle (Error: %d)", GetLastError());
      ReleaseAllHandles();
      return INIT_FAILED;
   }

   if (InpMinRangeATR > 0.0 || InpMaxRangeATR > 0.0 || InpUseAdaptiveSL || InpUseAdaptiveTP)
   {
      m_atr_handle = iATR(_Symbol, m_timeframe, InpATR_Period);
      if (m_atr_handle == INVALID_HANDLE)
      {
         PrintFormat("CRITICAL ERROR: [RSIFibEA] Failed to create iATR handle (Error: %d)", GetLastError());
         ReleaseAllHandles();
         return INIT_FAILED;
      }
   }

   if (InpUseMTFTrendFilter)
   {
      ENUM_TIMEFRAMES eval_tf = (InpMTFTimeframe == PERIOD_CURRENT) ? m_timeframe : InpMTFTimeframe;
      m_mtf_ema_handle = iMA(_Symbol, eval_tf, InpMTFEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
      if (m_mtf_ema_handle == INVALID_HANDLE)
      {
         PrintFormat("CRITICAL ERROR: [RSIFibEA] Failed to create MTF iMA handle (Error: %d)", GetLastError());
         ReleaseAllHandles();
         return INIT_FAILED;
      }

      if (InpMTFUseRSIConfirm)
      {
         m_mtf_rsi_handle = iRSI(_Symbol, eval_tf, InpMTFRSIPeriod, PRICE_CLOSE);
         if (m_mtf_rsi_handle == INVALID_HANDLE)
         {
            PrintFormat("CRITICAL ERROR: [RSIFibEA] Failed to create MTF iRSI handle (Error: %d)", GetLastError());
            ReleaseAllHandles();
            return INIT_FAILED;
         }
      }
   }

   if (InpUseVolatilityRegime)
   {
      m_vol_fast_atr_handle = iATR(_Symbol, m_timeframe, InpVolFastATRPeriod);
      if (m_vol_fast_atr_handle == INVALID_HANDLE)
      {
         PrintFormat("CRITICAL ERROR: [RSIFibEA] Failed to create Fast iATR handle (Error: %d)", GetLastError());
         ReleaseAllHandles();
         return INIT_FAILED;
      }

      m_vol_slow_atr_handle = iATR(_Symbol, m_timeframe, InpVolSlowATRPeriod);
      if (m_vol_slow_atr_handle == INVALID_HANDLE)
      {
         PrintFormat("CRITICAL ERROR: [RSIFibEA] Failed to create Slow iATR handle (Error: %d)", GetLastError());
         ReleaseAllHandles();
         return INIT_FAILED;
      }
   }

   // 4. Configure Trade Object & Object Prefix
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetMarginMode();
   if (!m_trade.SetTypeFillingBySymbol(_Symbol))
      Print("WARNING: [RSIFibEA] Broker filling policy could not be inferred; using RETURN for pending orders.");
   // MQL5 specifies ORDER_FILLING_RETURN for pending orders regardless of execution mode.
   m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
   m_trade.SetAsyncMode(false);

   m_safety_trade.SetExpertMagicNumber(InpMagicNumber);
   m_safety_trade.SetMarginMode();
   if (!m_safety_trade.SetTypeFillingBySymbol(_Symbol))
      Print("WARNING: [RSIFibEA] Safety-close filling policy could not be inferred from the symbol.");
   m_safety_trade.SetAsyncMode(false);

   m_obj_prefix = "RSIFib_" + IntegerToString((long)InpMagicNumber) + "_" + _Symbol + "_";
   m_setup.Reset();

   // 5. Initial Sync
   SyncState();
   bool lifecycle_service_ok = EnforceContractCutoffExposure();
   m_last_bar_time = iTime(_Symbol, m_timeframe, 0);
   if (m_state == STATE_IDLE)
      m_last_status = (initial_lifecycle_ok && lifecycle_service_ok)
                      ? "ready"
                      : "contract lifecycle blocks entries";

   PrintFormat("SUCCESS: [RSIFibEA] Initialized cleanly. Symbol: %s, Magic: %llu, State: %s",
               _Symbol, InpMagicNumber, EnumToString(m_state));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ReleaseAllHandles();
   RemoveChartObjects();
   Comment("");

   PrintFormat("INFO: [RSIFibEA] Deinitialized. Reason code: %d", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Re-check before synchronization: SyncState() may otherwise delete or
   // modify broker objects while reconciling an unsafe runtime context.
   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard failed at runtime");
      return;
   }

   // Detect New Closed Bar
   bool is_new_bar = false;
   long series_bar_time = 0;
   datetime current_bar_time = 0;
   if (SeriesInfoInteger(_Symbol, m_timeframe, SERIES_LASTBAR_DATE, series_bar_time))
      current_bar_time = (datetime)series_bar_time;
   if (current_bar_time > 0 && current_bar_time != m_last_bar_time)
   {
      m_last_bar_time = current_bar_time;
      is_new_bar = true;
   }

   // Broker scans are event-driven and coalesced, with a bounded watchdog.
   MaybeSyncState(is_new_bar);
   bool lifecycle_service_ok = EnforceContractCutoffExposure();
   UpdateDashboard();

   // At the futures cutoff, service existing exposure and never execute the
   // strategy state machine. Failed broker mutations remain queued for retry.
   if (!lifecycle_service_ok)
      return;

   // Check system permissions after synchronization so unsafe states remain visible.
   if (!IsTradeAllowed())
      return;

   // Execute State Logic
   switch (m_state)
   {
      case STATE_IDLE:
         if (is_new_bar)
            ProcessStateIdle();
         break;

      case STATE_WAITING_FOR_ANCHOR:
         if (is_new_bar)
            ProcessStateWaitingForAnchor();
         break;

      case STATE_PENDING_ORDER:
         ProcessStatePendingOrder(is_new_bar);
         break;

      case STATE_IN_POSITION:
         ProcessStateInPosition(is_new_bar);
         break;

      case STATE_FAULT:
         // A fault is reconciled by the broker-state service. Never open new risk here.
         break;
   }
}

// Keep this handler intentionally tiny: MT5 transaction arrival order is not guaranteed.
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   bool relevant = (trans.symbol == _Symbol);
   if (trans.type == TRADE_TRANSACTION_REQUEST)
      relevant = relevant || (request.symbol == _Symbol);

   if (relevant)
      m_sync_required = true;
   if (relevant &&
       (trans.type == TRADE_TRANSACTION_DEAL_ADD ||
        trans.type == TRADE_TRANSACTION_DEAL_UPDATE ||
        trans.type == TRADE_TRANSACTION_DEAL_DELETE))
      m_daily_stats_dirty = true;
}

double OnTester(void)
{
   double trades = TesterStatistics(STAT_TRADES);
   double profit = TesterStatistics(STAT_PROFIT);
   double profit_factor = TesterStatistics(STAT_PROFIT_FACTOR);
   double sharpe = TesterStatistics(STAT_SHARPE_RATIO);
   double drawdown = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);

   if (!MathIsValidNumber(trades) || !MathIsValidNumber(profit) ||
       !MathIsValidNumber(profit_factor) || !MathIsValidNumber(sharpe) ||
       !MathIsValidNumber(drawdown) || trades < (double)InpTesterMinTrades ||
       profit <= 0.0 || profit_factor < 0.0 || sharpe <= 0.0 ||
       drawdown < 0.0 || drawdown > InpTesterMaxDDPct)
      return -1.0;

   double capped_pf = MathMin(profit_factor, InpTesterPFCap);
   double capped_sharpe = MathMin(sharpe, InpTesterSharpeCap);
   double trade_weight = MathMin(1.0, MathSqrt(trades / (double)InpTesterTargetTrades));
   double dd_weight = 1.0 - drawdown / InpTesterMaxDDPct;
   double score = capped_sharpe * MathSqrt(capped_pf) * trade_weight * dd_weight * dd_weight;

   return MathIsValidNumber(score) ? score : -1.0;
}

//+------------------------------------------------------------------+
//| STATE PROCESSORS                                                 |
//+------------------------------------------------------------------+

//--- State: IDLE -> Looking for RSI crossover on closed bars
void ProcessStateIdle()
{
   double rsi_1 = 0.0, rsi_2 = 0.0;
   if (!GetClosedRSIPair(rsi_1, rsi_2))
      return;

   bool buy_signal  = (rsi_2 <= InpOversoldLevel && rsi_1 > InpOversoldLevel);
   bool sell_signal = (rsi_2 >= InpOverboughtLevel && rsi_1 < InpOverboughtLevel);

   if (!buy_signal && !sell_signal)
      return;

   ENUM_SIGNAL_DIR candidate_dir = buy_signal ? SIGNAL_BUY : SIGNAL_SELL;

   // Check Advanced Strategy Filters before registering signal
   if (!CheckRSIQualityFilter(candidate_dir, rsi_1, rsi_2) ||
       !CheckMTFTrendFilter(candidate_dir) ||
       !CheckVolatilityRegimeFilter())
   {
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] RSI signal detected but rejected by advanced strategy filters.");
      return;
   }

   // Check Risk & Session Guards before registering signal
   if (!CheckRiskGuards() || !CheckSpread() || !CheckSession() || !CheckContractLifecycle())
   {
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] RSI signal detected but rejected by risk, spread, or session guard.");
      return;
   }

   m_setup.Reset();
   m_setup.dir = candidate_dir;
   m_setup.signal_time = iTime(_Symbol, m_timeframe, 1);
   m_state = STATE_WAITING_FOR_ANCHOR;

   if (InpVerboseLog)
      PrintFormat("SIGNAL: [RSIFibEA] %s RSI crossover confirmed at bar 1 (%s). Waiting for anchor...",
                  (m_setup.dir == SIGNAL_BUY ? "BUY" : "SELL"), TimeToString(m_setup.signal_time));
}

//--- State: WAITING_FOR_ANCHOR -> Searching for first opposite closed candle
void ProcessStateWaitingForAnchor()
{
   if (!CheckContractLifecycle())
   {
      Print("INFO: [RSIFibEA] Contract lifecycle changed while waiting for anchor. Setup cancelled.");
      ResetSetupToIdle();
      return;
   }

   int bars_since_signal = iBarShift(_Symbol, m_timeframe, m_setup.signal_time);

   if (bars_since_signal < 0)
   {
      Print("WARNING: [RSIFibEA] Signal bar is no longer available. Setup reset.");
      ResetSetupToIdle();
      return;
   }

   int completed_bars_after_signal = bars_since_signal - 1;

   // Check expiration of anchor window
   if (completed_bars_after_signal > InpAnchorWaitBars)
   {
      if (InpVerboseLog)
         PrintFormat("INFO: [RSIFibEA] Anchor wait timeout (%d bars passed > max %d). Resetting to IDLE.",
                     completed_bars_after_signal, InpAnchorWaitBars);
      ResetSetupToIdle();
      return;
   }

   // Minimum impulse bars check
   if (completed_bars_after_signal < InpMinImpulseBars)
      return;

   // A fresh opposite RSI regime invalidates the directional thesis before an anchor exists.
   double rsi_1 = 0.0, rsi_2 = 0.0;
   if (GetClosedRSIPair(rsi_1, rsi_2))
   {
      bool buy_signal  = (rsi_2 <= InpOversoldLevel && rsi_1 > InpOversoldLevel);
      bool sell_signal = (rsi_2 >= InpOverboughtLevel && rsi_1 < InpOverboughtLevel);
      if ((m_setup.dir == SIGNAL_BUY && sell_signal) ||
          (m_setup.dir == SIGNAL_SELL && buy_signal))
      {
         Print("INFO: [RSIFibEA] Opposite RSI signal appeared while waiting for anchor. Setup cancelled.");
         ResetSetupToIdle();
         return;
      }
   }

   // Check if closed candle at shift 1 is opposite direction
   double close1 = iClose(_Symbol, m_timeframe, 1);
   double open1  = iOpen(_Symbol, m_timeframe, 1);

   if (close1 <= 0.0 || open1 <= 0.0 || !MathIsValidNumber(close1) || !MathIsValidNumber(open1))
      return;

   bool is_opposite = false;
   if (m_setup.dir == SIGNAL_BUY)
      is_opposite = (close1 < open1); // Bearish candle
   else if (m_setup.dir == SIGNAL_SELL)
      is_opposite = (close1 > open1); // Bullish candle

   if (!is_opposite)
      return; // Keep waiting

   // Found opposite candle! Compute P0 and P1
   m_setup.anchor_time = iTime(_Symbol, m_timeframe, 1);
   int window_start_shift = 1;
   int window_end_shift = bars_since_signal;

   bool anchor_ok = (m_setup.dir == SIGNAL_BUY)
                    ? ComputeBuyAnchorLevels(window_start_shift, window_end_shift)
                    : ComputeSellAnchorLevels(window_start_shift, window_end_shift);

   if (!anchor_ok || m_setup.range <= 0.0)
   {
      if (InpVerboseLog)
         PrintFormat("WARNING: [RSIFibEA] Invalid anchor range R=%.5f <= 0. Setup aborted.", m_setup.range);
      ResetSetupToIdle();
      return;
   }

   // Check ATR Range filter
   if (!CheckATRRangeFilter(m_setup.range))
   {
      if (InpVerboseLog)
         PrintFormat("INFO: [RSIFibEA] Setup range %.5f rejected by ATR filter bounds. Setup aborted.", m_setup.range);
      ResetSetupToIdle();
      return;
   }

   // Compute and validate tick-aligned prices
   if (!ComputeFibPrices())
   {
      Print("WARNING: [RSIFibEA] Fib prices became invalid after tick-size normalization. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // Adapt SL/TP to the chart's actual volatility if enabled
   if (!AdaptSLTPToVolatility())
   {
      if (InpVerboseLog)
         Print("WARNING: [RSIFibEA] Adaptive SL/TP adjustment failed or geometry invalid. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // Pre-placement Invalidation Check
   if (IsSetupInvalidatedByPrice())
   {
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] Setup invalidated by pre-placement price action. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // Check Stops Level
   if (!CheckStopsLevel(m_setup.entry_price, m_setup.stop_price, m_setup.target_price))
   {
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] Fib levels violate broker SYMBOL_TRADE_STOPS_LEVEL. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   if (!CheckSetupSpread())
   {
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] Spread is too large relative to the Entry-to-SL risk distance. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // Check Order Placement Rules (Buy Limit requires Entry < Ask, Sell Limit requires Entry > Bid)
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if (m_setup.dir == SIGNAL_BUY && m_setup.entry_price >= ask)
   {
      if (InpVerboseLog)
         PrintFormat("INFO: [RSIFibEA] Buy Limit entry %.5f >= Ask %.5f. Cannot place Limit order. Setup aborted.",
                     m_setup.entry_price, ask);
      ResetSetupToIdle();
      return;
   }
   if (m_setup.dir == SIGNAL_SELL && m_setup.entry_price <= bid)
   {
      if (InpVerboseLog)
         PrintFormat("INFO: [RSIFibEA] Sell Limit entry %.5f <= Bid %.5f. Cannot place Limit order. Setup aborted.",
                     m_setup.entry_price, bid);
      ResetSetupToIdle();
      return;
   }

   // Re-verify Risk Guards before ordering
   if (!CheckRiskGuards() || !CheckSpread() || !CheckSession() || !CheckContractLifecycle())
   {
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] Risk/Spread/Session guard rejected order placement. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   if (!IsDirectionAllowed(m_setup.dir))
   {
      Print("GUARD REJECT: Broker symbol mode does not allow this trade direction. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // On netting accounts, any foreign/manual position on this symbol would be merged
   // with the EA trade. Refuse all pre-existing exposure on the symbol in every mode.
   if (HasAnySymbolExposure())
   {
      Print("GUARD REJECT: Existing order or position detected on this symbol. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // Position Sizing
   ENUM_ORDER_TYPE order_type = (m_setup.dir == SIGNAL_BUY) ? ORDER_TYPE_BUY_LIMIT : ORDER_TYPE_SELL_LIMIT;
   double vol = 0.0;
   if (!CalculatePositionSize(m_setup.entry_price, m_setup.stop_price, order_type, vol))
   {
      if (InpVerboseLog)
         Print("WARNING: [RSIFibEA] Position sizing failed or volume < min lot. Setup aborted.");
      ResetSetupToIdle();
      return;
   }

   // Send Pending Limit Order
   ExecutePendingOrder(order_type, vol);
}

//--- State: PENDING_ORDER -> Monitoring placed order for expiry, invalidation, or execution
void ProcessStatePendingOrder(bool is_new_bar)
{
   if (m_setup.pending_ticket <= 0)
   {
      ResetSetupToIdle();
      return;
   }

   // Conditions can deteriorate after placement. Cancellation reduces exposure,
   // although a broker-side fill can still race the cancellation request.
   if (!CheckRiskGuards() || !CheckSpread() || !CheckSetupSpread() ||
       !CheckSession() || !CheckContractLifecycle())
   {
      Print("INFO: [RSIFibEA] Pending order no longer satisfies risk/spread/session/contract guards. Cancelling.");
      CancelPendingOrder();
      return;
   }

   // Check price invalidation on every tick
   if (IsSetupInvalidatedByPrice())
   {
      Print("INFO: [RSIFibEA] Pending order setup invalidated by price touching Stop/Target. Cancelling order.");
      CancelPendingOrder();
      return;
   }

   if (is_new_bar)
   {
      // Check order lifespan in bars
      int bars_passed = iBarShift(_Symbol, m_timeframe, m_setup.pending_order_time);
      if (bars_passed < 0)
      {
         Print("WARNING: [RSIFibEA] Pending order age cannot be determined. Cancelling defensively.");
         CancelPendingOrder();
         return;
      }
      if (bars_passed >= InpPendingOrderBars)
      {
         PrintFormat("INFO: [RSIFibEA] Pending order expired (%d bars passed >= max %d). Cancelling order.",
                     bars_passed, InpPendingOrderBars);
         CancelPendingOrder();
         return;
      }

      // Check opposite RSI signal
      double rsi_1 = 0.0, rsi_2 = 0.0;
      if (GetClosedRSIPair(rsi_1, rsi_2))
      {
         bool buy_signal  = (rsi_2 <= InpOversoldLevel && rsi_1 > InpOversoldLevel);
         bool sell_signal = (rsi_2 >= InpOverboughtLevel && rsi_1 < InpOverboughtLevel);

         if ((m_setup.dir == SIGNAL_BUY && sell_signal) || (m_setup.dir == SIGNAL_SELL && buy_signal))
         {
            Print("INFO: [RSIFibEA] Opposite RSI signal confirmed! Cancelling pending order.");
            CancelPendingOrder();
            return;
         }
      }
   }
}

//--- State: IN_POSITION -> Position monitoring
void ProcessStateInPosition(bool is_new_bar)
{
   if (InpUseFibTrailingStop)
      CheckAndApplyFibTrailingStop();
   else if (InpUseBreakEven)
      CheckAndApplyBreakEven();

   // Managed automatically by MT5 broker SL/TP orders attached to position.
   // Additional risk guards if required:
   if (is_new_bar && !CheckRiskGuards())
   {
      // Note: optional emergency exit if risk limits breached
      if (InpVerboseLog)
         Print("INFO: [RSIFibEA] Position active while daily risk limits reached. Letting SL/TP manage position.");
   }
}

//+------------------------------------------------------------------+
//| HELPER CALCULATION & EXECUTION FUNCTIONS                         |
//+------------------------------------------------------------------+

bool ComputeBuyAnchorLevels(int start_shift, int end_shift)
{
   if (start_shift < 1 || end_shift < start_shift)
      return false;

   double highest_high = iHigh(_Symbol, m_timeframe, start_shift);
   double retracement_low = iLow(_Symbol, m_timeframe, 1);
   if (highest_high <= 0.0 || retracement_low <= 0.0 ||
       !MathIsValidNumber(highest_high) || !MathIsValidNumber(retracement_low))
      return false;

   for (int s = start_shift; s <= end_shift; s++)
   {
      double h = iHigh(_Symbol, m_timeframe, s);
      if (h <= 0.0 || !MathIsValidNumber(h))
         return false;
      if (h > highest_high)
         highest_high = h;
   }
   m_setup.P1 = highest_high;
   m_setup.P0 = retracement_low;
   m_setup.range = m_setup.P1 - m_setup.P0;
   return (m_setup.range > 0.0 && MathIsValidNumber(m_setup.range));
}

bool ComputeSellAnchorLevels(int start_shift, int end_shift)
{
   if (start_shift < 1 || end_shift < start_shift)
      return false;

   double lowest_low = iLow(_Symbol, m_timeframe, start_shift);
   double retracement_high = iHigh(_Symbol, m_timeframe, 1);
   if (lowest_low <= 0.0 || retracement_high <= 0.0 ||
       !MathIsValidNumber(lowest_low) || !MathIsValidNumber(retracement_high))
      return false;

   for (int s = start_shift; s <= end_shift; s++)
   {
      double l = iLow(_Symbol, m_timeframe, s);
      if (l <= 0.0 || !MathIsValidNumber(l))
         return false;
      if (l < lowest_low)
         lowest_low = l;
   }
   m_setup.P1 = lowest_low;
   m_setup.P0 = retracement_high;
   m_setup.range = m_setup.P0 - m_setup.P1;
   return (m_setup.range > 0.0 && MathIsValidNumber(m_setup.range));
}

bool ComputeFibPrices()
{
   double raw_entry = 0.0;
   double raw_stop = 0.0;
   double raw_target = 0.0;
   double raw_visual_target = 0.0;

   if (m_setup.dir == SIGNAL_BUY)
   {
      raw_entry         = m_setup.P0 + InpEntryRatio * m_setup.range;
      raw_stop          = m_setup.P0 + InpStopRatio * m_setup.range;
      raw_target        = m_setup.P0 + InpTargetRatio * m_setup.range;
      raw_visual_target = m_setup.P0 + InpVisualTargetRatio * m_setup.range;

      m_setup.entry_price         = NormalizePriceDirectional(raw_entry, -1);
      m_setup.stop_price          = NormalizePriceDirectional(raw_stop, -1);
      m_setup.target_price        = NormalizePriceDirectional(raw_target, -1);
      m_setup.visual_target_price = NormalizePriceDirectional(raw_visual_target, 0);
   }
   else if (m_setup.dir == SIGNAL_SELL)
   {
      raw_entry         = m_setup.P0 - InpEntryRatio * m_setup.range;
      raw_stop          = m_setup.P0 - InpStopRatio * m_setup.range;
      raw_target        = m_setup.P0 - InpTargetRatio * m_setup.range;
      raw_visual_target = m_setup.P0 - InpVisualTargetRatio * m_setup.range;

      m_setup.entry_price         = NormalizePriceDirectional(raw_entry, 1);
      m_setup.stop_price          = NormalizePriceDirectional(raw_stop, 1);
      m_setup.target_price        = NormalizePriceDirectional(raw_target, 1);
      m_setup.visual_target_price = NormalizePriceDirectional(raw_visual_target, 0);
   }
   else
      return false;

   if (!MathIsValidNumber(m_setup.entry_price) || !MathIsValidNumber(m_setup.stop_price) ||
       !MathIsValidNumber(m_setup.target_price) || !MathIsValidNumber(m_setup.visual_target_price) ||
       m_setup.entry_price <= 0.0 || m_setup.stop_price <= 0.0 ||
       m_setup.target_price <= 0.0 || m_setup.visual_target_price <= 0.0)
      return false;

   if (m_setup.dir == SIGNAL_BUY)
      return (m_setup.stop_price < m_setup.entry_price &&
              m_setup.entry_price < m_setup.P0 && m_setup.P0 < m_setup.P1 &&
              m_setup.P1 < m_setup.target_price &&
              m_setup.target_price <= m_setup.visual_target_price);

   return (m_setup.visual_target_price <= m_setup.target_price &&
           m_setup.target_price < m_setup.P1 && m_setup.P1 < m_setup.P0 &&
           m_setup.P0 < m_setup.entry_price && m_setup.entry_price < m_setup.stop_price);
}

//+------------------------------------------------------------------+
//| ADAPTIVE GEOMETRY — SL/TP depend on chart volatility (ATR)       |
//+------------------------------------------------------------------+
bool AdaptSLTPToVolatility()
{
   if (!InpUseAdaptiveSL && !InpUseAdaptiveTP)
      return true;

   // ATR handle is required for adaptive geometry
   if (m_atr_handle == INVALID_HANDLE)
   {
      Print("ERROR: [RSIFibEA] Adaptive geometry requires ATR handle but it is invalid.");
      return false;
   }

   double atr_buf[1];
   if (CopyBuffer(m_atr_handle, 0, 1, 1, atr_buf) != 1)
   {
      Print("WARNING: [RSIFibEA] Cannot read ATR for adaptive geometry.");
      return false;
   }

   double atr = atr_buf[0];
   if (atr == EMPTY_VALUE || !MathIsValidNumber(atr) || atr <= 0.0)
   {
      Print("WARNING: [RSIFibEA] ATR value is invalid for adaptive geometry.");
      return false;
   }

   double current_sl_distance = MathAbs(m_setup.entry_price - m_setup.stop_price);

   // --- Adaptive SL: widen stop if it is closer than MinSLATRMultiple × ATR ---
   if (InpUseAdaptiveSL)
   {
      double min_sl_distance = InpMinSLATRMultiple * atr;

      if (current_sl_distance < min_sl_distance)
      {
         if (m_setup.dir == SIGNAL_BUY)
         {
            double new_stop = m_setup.entry_price - min_sl_distance;
            m_setup.stop_price = NormalizePriceDirectional(new_stop, -1);
         }
         else if (m_setup.dir == SIGNAL_SELL)
         {
            double new_stop = m_setup.entry_price + min_sl_distance;
            m_setup.stop_price = NormalizePriceDirectional(new_stop, 1);
         }

         current_sl_distance = MathAbs(m_setup.entry_price - m_setup.stop_price);

         if (InpVerboseLog)
            PrintFormat("ADAPT: [RSIFibEA] SL widened to %.5f (ATR=%.5f, floor=%.2f x ATR=%.5f, actual SL dist=%.5f)",
                        m_setup.stop_price, atr, InpMinSLATRMultiple, min_sl_distance, current_sl_distance);
      }
      else
      {
         if (InpVerboseLog)
            PrintFormat("ADAPT: [RSIFibEA] SL distance %.5f already >= ATR floor %.5f. No widening needed.",
                        current_sl_distance, min_sl_distance);
      }
   }

   // --- Adaptive TP: set TP at a fixed R:R multiple of the actual SL distance ---
   if (InpUseAdaptiveTP)
   {
      double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if (tick_size <= 0.0)
         return false;

      double new_tp_distance = current_sl_distance * InpTPRiskMultiple;

      if (m_setup.dir == SIGNAL_BUY)
      {
         m_setup.target_price        = NormalizePriceDirectional(m_setup.entry_price + new_tp_distance, -1);
         m_setup.visual_target_price  = NormalizePriceDirectional(m_setup.entry_price + new_tp_distance + tick_size, 0);
      }
      else if (m_setup.dir == SIGNAL_SELL)
      {
         m_setup.target_price        = NormalizePriceDirectional(m_setup.entry_price - new_tp_distance, 1);
         m_setup.visual_target_price  = NormalizePriceDirectional(m_setup.entry_price - new_tp_distance - tick_size, 0);
      }

      if (InpVerboseLog)
         PrintFormat("ADAPT: [RSIFibEA] TP adjusted to %.5f (SL dist=%.5f x %.1fR = TP dist=%.5f)",
                     m_setup.target_price, current_sl_distance, InpTPRiskMultiple, new_tp_distance);
   }

   // --- Final validation of adapted geometry ---
   if (!MathIsValidNumber(m_setup.stop_price) || !MathIsValidNumber(m_setup.target_price) ||
       !MathIsValidNumber(m_setup.visual_target_price) ||
       m_setup.stop_price <= 0.0 || m_setup.target_price <= 0.0 || m_setup.visual_target_price <= 0.0)
      return false;

   if (m_setup.dir == SIGNAL_BUY)
      return (m_setup.stop_price < m_setup.entry_price && m_setup.entry_price < m_setup.target_price &&
              m_setup.target_price <= m_setup.visual_target_price);

   return (m_setup.visual_target_price <= m_setup.target_price &&
           m_setup.target_price < m_setup.entry_price && m_setup.entry_price < m_setup.stop_price);
}

bool IsSetupInvalidatedByPrice()
{
   double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if (ask <= 0.0 || bid <= 0.0)
      return true;

   if (m_setup.dir == SIGNAL_BUY)
   {
      // Long SL and TP are executable on Bid.
      if (bid <= m_setup.stop_price)
         return true;
      if (bid >= m_setup.target_price)
         return true;
   }
   else if (m_setup.dir == SIGNAL_SELL)
   {
      // Short SL and TP are executable on Ask.
      if (ask >= m_setup.stop_price)
         return true;
      if (ask <= m_setup.target_price)
         return true;
   }
   return false;
}

bool GetContractEntryCutoff(datetime &contract_expiration, datetime &entry_cutoff)
{
   long expiration_value = 0;
   ResetLastError();
   if (!SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_TIME, expiration_value) ||
       expiration_value < 0)
   {
      PrintFormat("ERROR: [RSIFibEA] SYMBOL_EXPIRATION_TIME is unavailable or invalid (Error: %d).",
                  GetLastError());
      contract_expiration = 0;
      entry_cutoff = 0;
      return false;
   }

   contract_expiration = (datetime)expiration_value;
   entry_cutoff = 0;

   // A zero expiration is normal for spot/CFD symbols.
   if (contract_expiration <= 0)
      return true;

   long horizon_seconds = (long)InpMinDaysToContractExpiry * 86400L;
   long cutoff_value = (long)contract_expiration - horizon_seconds;
   if (horizon_seconds <= 0 || cutoff_value <= 0)
      return false;

   entry_cutoff = (datetime)cutoff_value;
   return true;
}

bool BuildPendingLifetime(ENUM_ORDER_TYPE_TIME &lifetime_type,
                          datetime &broker_expiration)
{
   lifetime_type = ORDER_TIME_GTC;
   broker_expiration = 0;

   datetime now = TimeCurrent();
   long timeframe_seconds = (long)PeriodSeconds(m_timeframe);
   long requested_seconds = timeframe_seconds * (long)InpPendingOrderBars;
   long requested_expiration = (long)now + requested_seconds;
   if (timeframe_seconds <= 0 || requested_seconds <= 0 ||
       requested_expiration <= (long)now)
   {
      Print("ERROR: [RSIFibEA] Pending-order lifetime cannot be represented safely.");
      return false;
   }

   datetime contract_expiration = 0;
   datetime entry_cutoff = 0;
   if (!GetContractEntryCutoff(contract_expiration, entry_cutoff))
   {
      Print("ERROR: [RSIFibEA] Contract entry cutoff cannot be represented safely.");
      return false;
   }

   // Never shorten the strategy silently: the complete planned pending
   // lifetime must fit strictly before the no-new-exposure cutoff.
   if (entry_cutoff > 0 && requested_expiration >= (long)entry_cutoff)
   {
      Print("GUARD REJECT: Planned pending-order lifetime would reach the contract cutoff.");
      return false;
   }
   long safe_expiration = requested_expiration;

   long expiration_modes = 0;
   ResetLastError();
   if (!SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE, expiration_modes) ||
       expiration_modes <= 0)
   {
      PrintFormat("ERROR: [RSIFibEA] Pending-order expiration modes are unavailable (Error: %d).",
                  GetLastError());
      return false;
   }

   // Prefer an exact finite lifetime. Less precise finite day modes precede
   // GTC so a supported server-side expiry is never discarded for infinity.
   if ((expiration_modes & (long)SYMBOL_EXPIRATION_SPECIFIED) != 0)
   {
      lifetime_type = ORDER_TIME_SPECIFIED;
      broker_expiration = (datetime)safe_expiration;
      return true;
   }

   MqlDateTime day_parts;
   if (!TimeToStruct(now, day_parts))
   {
      Print("ERROR: [RSIFibEA] Broker day boundary could not be calculated safely.");
      return false;
   }
   day_parts.hour = 23;
   day_parts.min = 59;
   day_parts.sec = 59;
   datetime broker_day_end = StructToTime(day_parts);
   bool day_mode_is_safe = (broker_day_end > now &&
                            (entry_cutoff <= 0 || broker_day_end < entry_cutoff));

   if ((expiration_modes & (long)SYMBOL_EXPIRATION_DAY) != 0 && day_mode_is_safe)
   {
      lifetime_type = ORDER_TIME_DAY;
      return true;
   }
   if ((expiration_modes & (long)SYMBOL_EXPIRATION_SPECIFIED_DAY) != 0 &&
       day_mode_is_safe)
   {
      lifetime_type = ORDER_TIME_SPECIFIED_DAY;
      broker_expiration = broker_day_end;
      return true;
   }

   // GTC is acceptable only for a non-expiring instrument. For a future it
   // could survive the cutoff while the terminal is offline.
   if ((expiration_modes & (long)SYMBOL_EXPIRATION_GTC) != 0 &&
       contract_expiration <= 0)
   {
      lifetime_type = ORDER_TIME_GTC;
      return true;
   }

   Print("ERROR: [RSIFibEA] Symbol exposes no expiration mode that stays inside the safe pending-order window.");
   return false;
}

void ExecutePendingOrder(ENUM_ORDER_TYPE order_type, double vol)
{
   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard blocked pending-order placement");
      return;
   }

   if (!CheckRiskGuards() || !CheckSpread() || !CheckSetupSpread() ||
       !CheckSession() || !CheckContractLifecycle())
   {
      Print("GUARD REJECT: Conditions changed immediately before pending-order send.");
      ResetSetupToIdle();
      return;
   }

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   string comment = "RSIFibEA_" + IntegerToString((long)InpMagicNumber);

   ENUM_ORDER_TYPE_TIME lifetime_type = ORDER_TIME_GTC;
   datetime broker_expiration = 0;
   if (!BuildPendingLifetime(lifetime_type, broker_expiration))
   {
      ResetSetupToIdle();
      return;
   }

   bool res = false;
   if (order_type == ORDER_TYPE_BUY_LIMIT)
      res = m_trade.BuyLimit(vol, m_setup.entry_price, _Symbol, m_setup.stop_price, m_setup.target_price,
                             lifetime_type, broker_expiration, comment);
   else if (order_type == ORDER_TYPE_SELL_LIMIT)
      res = m_trade.SellLimit(vol, m_setup.entry_price, _Symbol, m_setup.stop_price, m_setup.target_price,
                              lifetime_type, broker_expiration, comment);

   uint retcode = m_trade.ResultRetcode();
   if (res && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_PLACED))
   {
      m_setup.pending_ticket = m_trade.ResultOrder();
      m_setup.pending_order_time = TimeCurrent();

      if (m_setup.pending_ticket == 0)
      {
         ulong deal_ticket = m_trade.ResultDeal();
         if (deal_ticket > 0 && HistoryDealSelect(deal_ticket))
         {
            ulong order_id = (ulong)HistoryDealGetInteger(deal_ticket, DEAL_ORDER);
            if (order_id > 0)
               m_setup.pending_ticket = order_id;
         }
      }

      // A pending order can theoretically fill immediately between validation and send.
      // Re-sync when the server does not return an active order ticket.
      if (m_setup.pending_ticket > 0)
         m_state = STATE_PENDING_ORDER;
      else
         SyncState();

      if (m_state != STATE_PENDING_ORDER && m_state != STATE_IN_POSITION)
      {
         PrintFormat("ERROR: [RSIFibEA] Server accepted request but no active order/position was found. Retcode: %u (%s)",
                     retcode, m_trade.ResultRetcodeDescription());
         ResetSetupToIdle();
         return;
      }

      DrawSetupObjects();

      string volume_text = DoubleToString(vol, VolumeDigits(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP)));
      PrintFormat("SUCCESS: [RSIFibEA] Placed %s ticket #%llu, Vol: %s, Entry: %.5f, SL: %.5f, TP: %.5f",
                  EnumToString(order_type), m_setup.pending_ticket, volume_text,
                  m_setup.entry_price, m_setup.stop_price, m_setup.target_price);
   }
   else
   {
      PrintFormat("ERROR: [RSIFibEA] Failed to place %s. Retcode: %u (%s), Comment: %s",
                  EnumToString(order_type), retcode, m_trade.ResultRetcodeDescription(), m_trade.ResultComment());
      // Crucial requirement: No state mutation on broker failure!
      ResetSetupToIdle();
   }
}

bool CancelPendingOrder()
{
   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard blocked pending-order cancellation");
      return false;
   }

   ulong ticket = m_setup.pending_ticket;
   if (ticket == 0)
   {
      SyncState();
      return (m_state != STATE_PENDING_ORDER);
   }

   if (m_last_cancel_attempt != 0 && TimeCurrent() - m_last_cancel_attempt < 1)
      return false;
   m_last_cancel_attempt = TimeCurrent();

   if (!OrderSelect(ticket))
   {
      // It may have filled, expired, or been deleted externally between ticks.
      SyncState();
      return (m_state != STATE_PENDING_ORDER);
   }

   ResetLastError();
   bool deleted = m_trade.OrderDelete(ticket);
   uint retcode = m_trade.ResultRetcode();
   if (deleted && retcode == TRADE_RETCODE_DONE)
   {
      PrintFormat("INFO: [RSIFibEA] Cancelled pending order #%llu", ticket);
      ResetSetupToIdle();
      return true;
   }

   PrintFormat("ERROR: [RSIFibEA] Could not cancel pending order #%llu. Retcode: %u (%s), Error: %d. Will retry.",
               ticket, retcode, m_trade.ResultRetcodeDescription(), GetLastError());
   m_state = STATE_PENDING_ORDER;
   return false;
}

bool CloseManagedPositionForContractCutoff(const ulong ticket)
{
   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard blocked contract-cutoff position close");
      return false;
   }

   if (ticket == 0)
      return false;

   if (!PositionSelectByTicket(ticket))
   {
      m_sync_required = true;
      return true;
   }

   if (PositionGetString(POSITION_SYMBOL) != _Symbol ||
       PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
   {
      EnterFault(StringFormat("Contract-cutoff close refused foreign position #%llu", ticket));
      return false;
   }

   if (m_last_lifecycle_close_attempt != 0 &&
       TimeCurrent() - m_last_lifecycle_close_attempt < 10)
      return false;
   m_last_lifecycle_close_attempt = TimeCurrent();

   bool closed = m_safety_trade.PositionClose(ticket);
   uint retcode = m_safety_trade.ResultRetcode();
   if (closed && (retcode == TRADE_RETCODE_DONE ||
                  retcode == TRADE_RETCODE_DONE_PARTIAL))
   {
      m_sync_required = true;
      PrintFormat("SAFETY: [RSIFibEA] Contract-cutoff close sent for position #%llu.", ticket);
      return true;
   }

   PrintFormat("CRITICAL: [RSIFibEA] Contract-cutoff close failed for #%llu. Retcode: %u (%s). Will retry.",
               ticket, retcode, m_safety_trade.ResultRetcodeDescription());
   return false;
}

bool EnforceContractCutoffExposure()
{
   datetime contract_expiration = 0;
   datetime entry_cutoff = 0;
   if (!GetContractEntryCutoff(contract_expiration, entry_cutoff))
   {
      m_last_status = "invalid contract lifecycle properties";
      return false;
   }

   if (entry_cutoff <= 0 || TimeCurrent() < entry_cutoff)
      return true;

   m_last_status = "contract cutoff: flattening managed exposure";

   BrokerSnapshot snapshot;
   CaptureBrokerSnapshot(snapshot);
   if (snapshot.managed_positions > 1 || snapshot.managed_orders > 1 ||
       snapshot.managed_unsupported > 0)
   {
      EnterFault(StringFormat("Contract-cutoff snapshot is ambiguous: positions=%d orders=%d unsupported=%d",
                              snapshot.managed_positions, snapshot.managed_orders,
                              snapshot.managed_unsupported));
      return false;
   }

   if (snapshot.managed_orders == 1)
   {
      m_setup.pending_ticket = snapshot.limit_ticket;
      CancelPendingOrder();
   }

   if (snapshot.managed_positions == 1)
      CloseManagedPositionForContractCutoff(snapshot.position_ticket);

   // The cutoff is an absorbing no-entry state. Mutations that fail remain in
   // broker state and are retried on later ticks; never reset them optimistically.
   return false;
}

void ResetSetupToIdle()
{
   m_setup.Reset();
   m_state = STATE_IDLE;
   m_fault_reason = "";
   m_protection_status = "N/A";
   m_residual_order_ticket = 0;
   m_empty_broker_confirmations = 0;
   m_last_break_even_attempt = 0;
   m_last_emergency_close_attempt = 0;
   m_last_lifecycle_close_attempt = 0;
   RemoveChartObjects();
}

//+------------------------------------------------------------------+
//| RISK, SPREAD, SESSION & SYSTEM GUARDS                            |
//+------------------------------------------------------------------+

bool ValidateInputs()
{
   if (!InpDemoOnly)
   {
      Print("VALIDATION ERROR: InpDemoOnly is mandatory and cannot be disabled.");
      return false;
   }
   if (InpMagicNumber == 0)
   {
      Print("VALIDATION ERROR: InpMagicNumber must be greater than zero.");
      return false;
   }
   if (InpStateWatchdogMs < 250 || InpStateWatchdogMs > 60000)
   {
      Print("VALIDATION ERROR: InpStateWatchdogMs must be between 250 and 60000 ms.");
      return false;
   }
   if (InpRSI_Period < 2 || InpRSI_Period > 100000 ||
       InpATR_Period < 1 || InpATR_Period > 100000)
   {
      Print("VALIDATION ERROR: RSI/ATR periods are outside safe bounds.");
      return false;
   }
   if (!MathIsValidNumber(InpOversoldLevel) || !MathIsValidNumber(InpOverboughtLevel) ||
       !MathIsValidNumber(InpEntryRatio) || !MathIsValidNumber(InpStopRatio) ||
       !MathIsValidNumber(InpTargetRatio) || !MathIsValidNumber(InpVisualTargetRatio))
   {
      Print("VALIDATION ERROR: Indicator levels and Fib ratios must be finite numbers.");
      return false;
   }
   if (InpOversoldLevel >= InpOverboughtLevel)
   {
      Print("VALIDATION ERROR: InpOversoldLevel must be strictly less than InpOverboughtLevel.");
      return false;
   }
   if (InpOversoldLevel <= 0.0 || InpOverboughtLevel >= 100.0)
   {
      Print("VALIDATION ERROR: RSI levels must be between 0 and 100.");
      return false;
   }
   if (InpEntryRatio >= 0.0)
   {
      Print("VALIDATION ERROR: InpEntryRatio must be strictly negative (< 0.0).");
      return false;
   }
   if (InpStopRatio >= InpEntryRatio)
   {
      Print("VALIDATION ERROR: InpStopRatio must be strictly less than InpEntryRatio (< InpEntryRatio).");
      return false;
   }
   if (InpTargetRatio < 1.0)
   {
      Print("VALIDATION ERROR: InpTargetRatio must be >= 1.0.");
      return false;
   }
   if (InpVisualTargetRatio < InpTargetRatio)
   {
      Print("VALIDATION ERROR: InpVisualTargetRatio must be >= InpTargetRatio.");
      return false;
   }
   if (InpMinImpulseBars < 1 || InpMinImpulseBars > 10000)
   {
      Print("VALIDATION ERROR: InpMinImpulseBars must be between 1 and 10000.");
      return false;
   }
   if (InpAnchorWaitBars < InpMinImpulseBars || InpAnchorWaitBars > 10000)
   {
      Print("VALIDATION ERROR: InpAnchorWaitBars must be >= impulse bars and <= 10000.");
      return false;
   }
   if (InpPendingOrderBars < 1 || InpPendingOrderBars > 10000)
   {
      Print("VALIDATION ERROR: InpPendingOrderBars must be between 1 and 10000.");
      return false;
   }
   if (!MathIsValidNumber(InpRiskPercent) || InpRiskPercent <= 0.0 || InpRiskPercent > 2.00)
   {
      Print("VALIDATION ERROR: InpRiskPercent must be positive and cannot exceed 2.00%.");
      return false;
   }
   if (!InpCostModelVerified)
   {
      Print("VALIDATION ERROR: The broker cost model must be explicitly verified.");
      return false;
   }
   if (!MathIsValidNumber(InpEstimatedRoundTurnCostPerLot) ||
       InpEstimatedRoundTurnCostPerLot < 0.0)
   {
      Print("VALIDATION ERROR: Verified round-turn cost per lot must be finite and non-negative.");
      return false;
   }
   if (InpAdverseEntrySlippageTicks < 1 || InpAdverseEntrySlippageTicks > 10000 ||
       InpAdverseStopSlippageTicks < 1 || InpAdverseStopSlippageTicks > 10000 ||
       !MathIsValidNumber(InpMaxFreeMarginUsagePct) ||
       InpMaxFreeMarginUsagePct <= 0.0 || InpMaxFreeMarginUsagePct > 100.0 ||
       InpMinDaysToContractExpiry < 1 || InpMinDaysToContractExpiry > 365)
   {
      Print("VALIDATION ERROR: Cost, slippage, margin, or contract-expiry guards are invalid.");
      return false;
   }
   if (!MathIsValidNumber(InpMaxDailyLossPct) || InpMaxDailyLossPct < 0.0 || InpMaxDailyLossPct > 100.0 ||
       InpMaxDailyTrades < 0 || InpMaxConsecutiveLosses < 0)
   {
      Print("VALIDATION ERROR: Daily guard parameters are outside their valid ranges.");
      return false;
   }
   if (InpMaxSpreadPoints < 0 || !MathIsValidNumber(InpMaxSpreadRiskPct) || InpMaxSpreadRiskPct < 0.0)
   {
      Print("VALIDATION ERROR: Spread limits cannot be negative.");
      return false;
   }
   if (InpStartHour < 0 || InpStartHour > 23 || InpEndHour < 0 || InpEndHour > 23)
   {
      Print("VALIDATION ERROR: Session hours must be between 0 and 23.");
      return false;
   }
   if (!MathIsValidNumber(InpMinRangeATR) || !MathIsValidNumber(InpMaxRangeATR) ||
       InpMinRangeATR < 0.0 || InpMaxRangeATR < 0.0 ||
       (InpMinRangeATR > 0.0 && InpMaxRangeATR > 0.0 && InpMinRangeATR > InpMaxRangeATR))
   {
      Print("VALIDATION ERROR: ATR range bounds are invalid.");
      return false;
   }
   if (InpRSIMinBarsInZone < 1 || InpRSIMinBarsInZone > 10000)
   {
      Print("VALIDATION ERROR: InpRSIMinBarsInZone must be between 1 and 10000.");
      return false;
   }
   if (!MathIsValidNumber(InpRSIMinExitDelta) || InpRSIMinExitDelta < 0.0)
   {
      Print("VALIDATION ERROR: InpRSIMinExitDelta must be a finite non-negative number.");
      return false;
   }
   if (InpMTFEMAPeriod < 1 || InpMTFEMAPeriod > 100000)
   {
      Print("VALIDATION ERROR: InpMTFEMAPeriod is outside safe bounds.");
      return false;
   }
   ENUM_TIMEFRAMES resolved_signal_tf = (InpSignalTimeframe == PERIOD_CURRENT)
                                         ? (ENUM_TIMEFRAMES)_Period
                                         : InpSignalTimeframe;
   if (InpUseMTFTrendFilter && InpMTFTimeframe != PERIOD_CURRENT &&
       PeriodSeconds(InpMTFTimeframe) < PeriodSeconds(resolved_signal_tf))
   {
      Print("VALIDATION ERROR: InpMTFTimeframe must be equal to or higher than the signal timeframe.");
      return false;
   }
   if (InpMTFRSIPeriod < 2 || InpMTFRSIPeriod > 100000)
   {
      Print("VALIDATION ERROR: InpMTFRSIPeriod is outside safe bounds.");
      return false;
   }
   if (!MathIsValidNumber(InpMTFRSIMidline) || InpMTFRSIMidline <= 0.0 || InpMTFRSIMidline >= 100.0)
   {
      Print("VALIDATION ERROR: InpMTFRSIMidline must be between 0 and 100.");
      return false;
   }
   if (InpVolFastATRPeriod < 1 || InpVolFastATRPeriod > 100000 ||
       InpVolSlowATRPeriod < 1 || InpVolSlowATRPeriod > 100000)
   {
      Print("VALIDATION ERROR: Fast and Slow ATR periods are outside safe bounds.");
      return false;
   }
   if (InpVolFastATRPeriod >= InpVolSlowATRPeriod)
   {
      Print("VALIDATION ERROR: InpVolFastATRPeriod must be strictly less than InpVolSlowATRPeriod.");
      return false;
   }
   if (!MathIsValidNumber(InpVolMinRatio) || !MathIsValidNumber(InpVolMaxRatio) ||
       InpVolMinRatio <= 0.0 || InpVolMaxRatio < InpVolMinRatio)
   {
      Print("VALIDATION ERROR: Volatility ratio bounds are invalid.");
      return false;
   }
   if (!MathIsValidNumber(InpBETriggerFibRatio) || InpBETriggerFibRatio < 0.0 ||
       InpBETriggerFibRatio > InpTargetRatio || InpBEOffsetTicks < 0)
   {
      Print("VALIDATION ERROR: Break-even trigger/offset values are invalid.");
      return false;
   }
   if (!MathIsValidNumber(InpMinSLATRMultiple) || InpMinSLATRMultiple <= 0.0 || InpMinSLATRMultiple > 100.0)
   {
      Print("VALIDATION ERROR: InpMinSLATRMultiple must be a positive finite number (<= 100).");
      return false;
   }
   if (!MathIsValidNumber(InpTPRiskMultiple) || InpTPRiskMultiple <= 0.0 || InpTPRiskMultiple > 100.0)
   {
      Print("VALIDATION ERROR: InpTPRiskMultiple must be a positive finite number (<= 100).");
      return false;
   }
   if (InpTesterMinTrades < 1 || InpTesterTargetTrades < InpTesterMinTrades ||
       !MathIsValidNumber(InpTesterMaxDDPct) || InpTesterMaxDDPct <= 0.0 ||
       InpTesterMaxDDPct > 100.0 ||
       !MathIsValidNumber(InpTesterPFCap) || InpTesterPFCap <= 1.0 ||
       !MathIsValidNumber(InpTesterSharpeCap) || InpTesterSharpeCap <= 0.0)
   {
      Print("VALIDATION ERROR: Strategy Tester fitness parameters are invalid.");
      return false;
   }
   return true;
}

bool IsStrictDemoContext()
{
   if (!InpDemoOnly)
      return false;
   if (MQLInfoInteger(MQL_TESTER))
      return true;
   return ((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE) ==
           ACCOUNT_TRADE_MODE_DEMO);
}

bool IsTradeAllowed()
{
   if (!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
      return false;
   if (!MQLInfoInteger(MQL_TRADE_ALLOWED))
      return false;
   if (!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))
      return false;
   if (!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
      return false;

   ENUM_SYMBOL_TRADE_MODE trade_mode = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if (trade_mode == SYMBOL_TRADE_MODE_DISABLED || trade_mode == SYMBOL_TRADE_MODE_CLOSEONLY)
      return false;

   return true;
}

bool IsDirectionAllowed(ENUM_SIGNAL_DIR dir)
{
   ENUM_SYMBOL_TRADE_MODE trade_mode = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE);
   if (trade_mode == SYMBOL_TRADE_MODE_FULL)
      return true;
   if (dir == SIGNAL_BUY && trade_mode == SYMBOL_TRADE_MODE_LONGONLY)
      return true;
   if (dir == SIGNAL_SELL && trade_mode == SYMBOL_TRADE_MODE_SHORTONLY)
      return true;
   return false;
}

bool CheckSpread()
{
   if (InpMaxSpreadPoints <= 0)
      return true;

   MqlTick tick;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if (!SymbolInfoTick(_Symbol, tick) || point <= 0.0 || tick.ask <= 0.0 || tick.bid <= 0.0)
      return false;

   double spread_points = (tick.ask - tick.bid) / point;
   if (spread_points > (double)InpMaxSpreadPoints)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Current spread (%.1f pts) exceeds max allowed (%d pts)",
                     spread_points, InpMaxSpreadPoints);
      return false;
   }
   return true;
}

bool CheckSetupSpread()
{
   if (InpMaxSpreadRiskPct <= 0.0)
      return true;

   MqlTick tick;
   if (!SymbolInfoTick(_Symbol, tick) || tick.ask <= 0.0 || tick.bid <= 0.0)
      return false;

   double risk_distance = MathAbs(m_setup.entry_price - m_setup.stop_price);
   double spread = tick.ask - tick.bid;
   if (risk_distance <= 0.0 || spread < 0.0)
      return false;

   double spread_risk_pct = 100.0 * spread / risk_distance;
   if (spread_risk_pct > InpMaxSpreadRiskPct)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Spread consumes %.2f%% of Entry-to-SL distance (max %.2f%%).",
                     spread_risk_pct, InpMaxSpreadRiskPct);
      return false;
   }
   return true;
}

bool HasAnySymbolExposure()
{
   for (int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if (ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
   }

   for (int i = 0; i < OrdersTotal(); i++)
   {
      ulong ticket = OrderGetTicket(i);
      if (ticket > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol)
         return true;
   }

   return false;
}

bool CheckSession()
{
   if (!InpUseSessionFilter)
      return true;

   MqlDateTime dt;
   TimeCurrent(dt);
   if (InpStartHour <= InpEndHour)
   {
      if (dt.hour < InpStartHour || dt.hour >= InpEndHour)
         return false;
   }
   else
   {
      // Overnight session (e.g. 22:00 to 06:00)
      if (dt.hour < InpStartHour && dt.hour >= InpEndHour)
         return false;
   }
   return true;
}

bool CheckContractLifecycle()
{
   datetime now = TimeCurrent();
   long start_value = 0;
   ResetLastError();
   if (!SymbolInfoInteger(_Symbol, SYMBOL_START_TIME, start_value) ||
       start_value < 0)
   {
      PrintFormat("GUARD REJECT: SYMBOL_START_TIME is unavailable or invalid (Error: %d).",
                  GetLastError());
      return false;
   }
   datetime start_time = (datetime)start_value;

   if (start_time > 0 && now < start_time)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Contract has not started trading yet (start %s).",
                     TimeToString(start_time, TIME_DATE | TIME_MINUTES));
      return false;
   }

   datetime expiration_time = 0;
   datetime entry_cutoff = 0;
   if (!GetContractEntryCutoff(expiration_time, entry_cutoff))
   {
      Print("GUARD REJECT: Contract lifecycle properties cannot produce a safe entry cutoff.");
      return false;
   }

   if (entry_cutoff > 0 && now >= entry_cutoff)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Contract entry cutoff reached (%s; expiry %s; horizon %d days).",
                     TimeToString(entry_cutoff, TIME_DATE | TIME_SECONDS),
                     TimeToString(expiration_time, TIME_DATE | TIME_MINUTES),
                     InpMinDaysToContractExpiry);
      return false;
   }
   return true;
}

bool CheckDailyLimits()
{
   int daily_trades = 0;
   double daily_pnl = 0.0;
   int consec_losses = 0;

   if (!UpdateDailyStats(daily_trades, daily_pnl, consec_losses))
   {
      Print("GUARD REJECT: Daily history could not be read. Trading is disabled until statistics are available.");
      return false;
   }

   // Max Daily Trades Limit
   if (InpMaxDailyTrades > 0 && daily_trades >= InpMaxDailyTrades)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Daily trade count limit reached (%d >= %d)", daily_trades, InpMaxDailyTrades);
      return false;
   }

   // Consecutive Losses Limit
   if (InpMaxConsecutiveLosses > 0 && consec_losses >= InpMaxConsecutiveLosses)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Max consecutive losses limit reached (%d >= %d)", consec_losses, InpMaxConsecutiveLosses);
      return false;
   }

   // Max Daily Drawdown / Loss Limit, including this EA's floating PnL.
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double floating_pnl = CurrentEAFloatingPnL();
   double equity_pnl_today = daily_pnl + floating_pnl;
   double estimated_day_start_equity = equity - equity_pnl_today;
   if (estimated_day_start_equity <= 0.0)
      estimated_day_start_equity = AccountInfoDouble(ACCOUNT_BALANCE) - daily_pnl;

   if (equity > 0.0 && estimated_day_start_equity > 0.0 && InpMaxDailyLossPct > 0.0)
   {
      double max_loss_money = estimated_day_start_equity * (InpMaxDailyLossPct / 100.0);
      if (equity_pnl_today <= -max_loss_money)
      {
         if (InpVerboseLog)
            PrintFormat("GUARD REJECT: Max daily equity loss reached (realized %.2f, floating %.2f, limit %.2f)",
                        daily_pnl, floating_pnl, -max_loss_money);
         return false;
      }
   }

   return true;
}

bool CheckRiskGuards()
{
   return CheckDailyLimits();
}

bool UpdateDailyStats(int &daily_trades, double &daily_pnl, int &consec_losses)
{
   daily_trades = 0;
   daily_pnl = 0.0;
   consec_losses = 0;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   datetime midnight_today = StructToTime(dt);

   if (!m_daily_stats_dirty && m_daily_cache_day == midnight_today)
   {
      daily_trades = m_daily_cache_trades;
      daily_pnl = m_daily_cache_pnl;
      consec_losses = m_daily_cache_consecutive_losses;
      return true;
   }

   ResetLastError();
   if (!HistorySelect(midnight_today, TimeCurrent() + 1))
   {
      PrintFormat("ERROR: [RSIFibEA] HistorySelect failed (Error: %d)", GetLastError());
      return false;
   }

   int total_deals = HistoryDealsTotal();
   DailyPositionStat groups[];
   int group_count = 0;

   for (int i = 0; i < total_deals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if (ticket == 0) continue;

      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
      ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY);

      if (magic == (long)InpMagicNumber && symbol == _Symbol)
      {
         double profit     = HistoryDealGetDouble(ticket, DEAL_PROFIT);
         double commission = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         double swap       = HistoryDealGetDouble(ticket, DEAL_SWAP);
         double fee        = HistoryDealGetDouble(ticket, DEAL_FEE);
         double net_pnl    = profit + commission + swap + fee;

         daily_pnl += net_pnl;

         long position_id = HistoryDealGetInteger(ticket, DEAL_POSITION_ID);
         if (position_id <= 0)
         {
            PrintFormat("ERROR: [RSIFibEA] Deal #%llu has no valid position identifier.", ticket);
            return false;
         }

         int group_index = -1;
         for (int g = 0; g < group_count; g++)
         {
            if (groups[g].identifier == position_id)
            {
               group_index = g;
               break;
            }
         }

         if (group_index < 0)
         {
            group_index = group_count;
            if (ArrayResize(groups, group_count + 1, 64) != group_count + 1)
               return false;
            groups[group_index].identifier = position_id;
            groups[group_index].pnl = 0.0;
            groups[group_index].last_exit_msc = 0;
            groups[group_index].has_entry = false;
            groups[group_index].has_exit = false;
            group_count++;
         }

         groups[group_index].pnl += net_pnl;
         if (entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT)
            groups[group_index].has_entry = true;

         if (entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY || entry == DEAL_ENTRY_INOUT)
         {
            groups[group_index].has_exit = true;
            long exit_msc = HistoryDealGetInteger(ticket, DEAL_TIME_MSC);
            if (exit_msc > groups[group_index].last_exit_msc)
               groups[group_index].last_exit_msc = exit_msc;
         }
      }
   }

   for (int g = 0; g < group_count; g++)
   {
      if (groups[g].has_entry)
         daily_trades++;
   }

   // Daily PnL intentionally contains only today's deals. Consecutive-loss
   // classification is different: a position closed today must include every
   // deal attached to that position, including an entry commission charged
   // before midnight. HistorySelectByPosition keeps that accounting exact
   // without widening the daily-PnL window.
   for (int g = 0; g < group_count; g++)
   {
      if (!groups[g].has_exit || IsPositionIdentifierOpen(groups[g].identifier))
         continue;

      ResetLastError();
      if (!HistorySelectByPosition((ulong)groups[g].identifier))
      {
         PrintFormat("ERROR: [RSIFibEA] HistorySelectByPosition failed for #%I64d (Error: %d)",
                     groups[g].identifier, GetLastError());
         return false;
      }

      double complete_position_pnl = 0.0;
      bool found_managed_deal = false;
      int position_deals = HistoryDealsTotal();
      for (int d = 0; d < position_deals; d++)
      {
         ulong deal_ticket = HistoryDealGetTicket(d);
         if (deal_ticket == 0 ||
             HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID) != groups[g].identifier ||
             HistoryDealGetInteger(deal_ticket, DEAL_MAGIC) != (long)InpMagicNumber ||
             HistoryDealGetString(deal_ticket, DEAL_SYMBOL) != _Symbol)
            continue;

         complete_position_pnl += HistoryDealGetDouble(deal_ticket, DEAL_PROFIT)
                                  + HistoryDealGetDouble(deal_ticket, DEAL_COMMISSION)
                                  + HistoryDealGetDouble(deal_ticket, DEAL_SWAP)
                                  + HistoryDealGetDouble(deal_ticket, DEAL_FEE);
         found_managed_deal = true;
      }

      if (!found_managed_deal || !MathIsValidNumber(complete_position_pnl))
      {
         PrintFormat("ERROR: [RSIFibEA] Complete deal history unavailable for position #%I64d.",
                     groups[g].identifier);
         return false;
      }
      groups[g].pnl = complete_position_pnl;
   }

   // Aggregate partial fills by position identifier, then inspect closed positions newest-first.
   bool processed[];
   if (ArrayResize(processed, group_count) != group_count)
      return false;
   for (int g = 0; g < group_count; g++)
      processed[g] = false;

   while (true)
   {
      int latest_index = -1;
      long latest_exit_msc = -1;
      for (int g = 0; g < group_count; g++)
      {
         if (processed[g] || !groups[g].has_exit || IsPositionIdentifierOpen(groups[g].identifier))
            continue;
         if (groups[g].last_exit_msc > latest_exit_msc)
         {
            latest_exit_msc = groups[g].last_exit_msc;
            latest_index = g;
         }
      }

      if (latest_index < 0)
         break;

      processed[latest_index] = true;
      if (groups[latest_index].pnl < 0.0)
         consec_losses++;
      else
         break;
   }
   m_daily_cache_day = midnight_today;
   m_daily_cache_trades = daily_trades;
   m_daily_cache_pnl = daily_pnl;
   m_daily_cache_consecutive_losses = consec_losses;
   m_daily_stats_dirty = false;
   return true;
}

bool IsPositionIdentifierOpen(long identifier)
{
   for (int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if (ticket > 0 && PositionGetInteger(POSITION_IDENTIFIER) == identifier)
         return true;
   }
   return false;
}

double CurrentEAFloatingPnL()
{
   double pnl = 0.0;
   for (int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0)
         continue;
      if (PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber ||
          PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      pnl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
   }
   return pnl;
}

bool CheckATRRangeFilter(double range)
{
   if (InpMinRangeATR <= 0.0 && InpMaxRangeATR <= 0.0)
      return true;

   double atr_val = 0.0;
   if (!GetATR(1, atr_val) || atr_val <= 0.0)
   {
      Print("GUARD REJECT: ATR filter is enabled but ATR data is unavailable or invalid.");
      return false;
   }

   if (InpMinRangeATR > 0.0 && range < InpMinRangeATR * atr_val)
      return false;

   if (InpMaxRangeATR > 0.0 && range > InpMaxRangeATR * atr_val)
      return false;

   return true;
}

bool CheckRSIQualityFilter(ENUM_SIGNAL_DIR dir, double rsi_1, double rsi_2)
{
   if (!InpUseRSIQualityFilter)
      return true;

   if (dir == SIGNAL_BUY)
   {
      double delta = rsi_1 - rsi_2;
      if (!MathIsValidNumber(delta) || delta < InpRSIMinExitDelta)
         return false;

      if (rsi_2 > InpOversoldLevel)
         return false;
      for (int s = 3; s <= 1 + InpRSIMinBarsInZone; s++)
      {
         double rsi_s = 0.0;
         if (!GetRSI(s, rsi_s) || rsi_s > InpOversoldLevel)
            return false;
      }
   }
   else if (dir == SIGNAL_SELL)
   {
      double delta = rsi_2 - rsi_1;
      if (!MathIsValidNumber(delta) || delta < InpRSIMinExitDelta)
         return false;

      if (rsi_2 < InpOverboughtLevel)
         return false;
      for (int s = 3; s <= 1 + InpRSIMinBarsInZone; s++)
      {
         double rsi_s = 0.0;
         if (!GetRSI(s, rsi_s) || rsi_s < InpOverboughtLevel)
            return false;
      }
   }
   else
      return false;

   return true;
}

bool CheckMTFTrendFilter(ENUM_SIGNAL_DIR dir)
{
   if (!InpUseMTFTrendFilter)
      return true;

   if (m_mtf_ema_handle == INVALID_HANDLE)
      return false;

   ENUM_TIMEFRAMES eval_tf = (InpMTFTimeframe == PERIOD_CURRENT) ? m_timeframe : InpMTFTimeframe;
   double htf_close = iClose(_Symbol, eval_tf, 1);
   if (htf_close <= 0.0 || !MathIsValidNumber(htf_close))
      return false;

   double ema_buf[1];
   if (CopyBuffer(m_mtf_ema_handle, 0, 1, 1, ema_buf) != 1)
      return false;

   double htf_ema = ema_buf[0];
   if (htf_ema == EMPTY_VALUE || !MathIsValidNumber(htf_ema) || htf_ema <= 0.0)
      return false;

   if (InpMTFUseRSIConfirm)
   {
      if (m_mtf_rsi_handle == INVALID_HANDLE)
         return false;

      double rsi_buf[1];
      if (CopyBuffer(m_mtf_rsi_handle, 0, 1, 1, rsi_buf) != 1)
         return false;

      double htf_rsi = rsi_buf[0];
      if (htf_rsi == EMPTY_VALUE || !MathIsValidNumber(htf_rsi) || htf_rsi < 0.0 || htf_rsi > 100.0)
         return false;

      if (dir == SIGNAL_BUY)
      {
         if (htf_close <= htf_ema || htf_rsi <= InpMTFRSIMidline)
            return false;
      }
      else if (dir == SIGNAL_SELL)
      {
         if (htf_close >= htf_ema || htf_rsi >= InpMTFRSIMidline)
            return false;
      }
      else
         return false;
   }
   else
   {
      if (dir == SIGNAL_BUY)
      {
         if (htf_close <= htf_ema)
            return false;
      }
      else if (dir == SIGNAL_SELL)
      {
         if (htf_close >= htf_ema)
            return false;
      }
      else
         return false;
   }

   return true;
}

bool CheckVolatilityRegimeFilter()
{
   if (!InpUseVolatilityRegime)
      return true;

   if (m_vol_fast_atr_handle == INVALID_HANDLE || m_vol_slow_atr_handle == INVALID_HANDLE)
      return false;

   double fast_buf[1];
   if (CopyBuffer(m_vol_fast_atr_handle, 0, 1, 1, fast_buf) != 1)
      return false;

   double slow_buf[1];
   if (CopyBuffer(m_vol_slow_atr_handle, 0, 1, 1, slow_buf) != 1)
      return false;

   double fast_atr = fast_buf[0];
   double slow_atr = slow_buf[0];

   if (fast_atr == EMPTY_VALUE || slow_atr == EMPTY_VALUE ||
       !MathIsValidNumber(fast_atr) || !MathIsValidNumber(slow_atr) ||
       fast_atr <= 0.0 || slow_atr <= 0.0)
      return false;

   double vol_ratio = fast_atr / slow_atr;
   if (!MathIsValidNumber(vol_ratio))
      return false;

   if (vol_ratio < InpVolMinRatio || vol_ratio > InpVolMaxRatio)
      return false;

   return true;
}

bool CheckStopsLevel(double entry, double stop, double target)
{
   long stops_level_pts = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double min_dist = stops_level_pts * point;

   if (min_dist <= 0.0)
      return true;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if (m_setup.dir == SIGNAL_BUY)
   {
      if ((ask - entry) < min_dist) return false;
      if ((entry - stop) < min_dist) return false;
      if ((target - entry) < min_dist) return false;
   }
   else if (m_setup.dir == SIGNAL_SELL)
   {
      if ((entry - bid) < min_dist) return false;
      if ((stop - entry) < min_dist) return false;
      if ((entry - target) < min_dist) return false;
   }

   return true;
}

bool GetClosedRSIPair(double &rsi_1, double &rsi_2)
{
   rsi_1 = 0.0;
   rsi_2 = 0.0;
   if (m_rsi_handle == INVALID_HANDLE)
      return false;

   double values[2];
   if (CopyBuffer(m_rsi_handle, 0, 1, 2, values) != 2)
   {
      if (InpVerboseLog)
         PrintFormat("WARNING: CopyBuffer iRSI pair failed (Error: %d)", GetLastError());
      return false;
   }

   // CopyBuffer stores the oldest requested value first: [0]=shift 2, [1]=shift 1.
   rsi_2 = values[0];
   rsi_1 = values[1];
   return (rsi_1 != EMPTY_VALUE && rsi_2 != EMPTY_VALUE &&
           MathIsValidNumber(rsi_1) && MathIsValidNumber(rsi_2) &&
           rsi_1 >= 0.0 && rsi_1 <= 100.0 && rsi_2 >= 0.0 && rsi_2 <= 100.0);
}

bool GetRSI(int shift, double &val)
{
   if (m_rsi_handle == INVALID_HANDLE) return false;
   double buf[1];
   if (CopyBuffer(m_rsi_handle, 0, shift, 1, buf) != 1)
   {
      if (InpVerboseLog)
         PrintFormat("WARNING: CopyBuffer iRSI failed at shift %d (Error: %d)", shift, GetLastError());
      return false;
   }
   val = buf[0];
   return (val != EMPTY_VALUE && MathIsValidNumber(val) && val >= 0.0 && val <= 100.0);
}

bool GetATR(int shift, double &val)
{
   if (m_atr_handle == INVALID_HANDLE) return false;
   double buf[1];
   if (CopyBuffer(m_atr_handle, 0, shift, 1, buf) != 1)
   {
      if (InpVerboseLog)
         PrintFormat("WARNING: CopyBuffer iATR failed at shift %d (Error: %d)", shift, GetLastError());
      return false;
   }
   val = buf[0];
   return (val != EMPTY_VALUE && MathIsValidNumber(val) && val > 0.0);
}

double NormalizePriceDirectional(double price, int direction)
{
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if (tick_size <= 0.0 || digits < 0 || !MathIsValidNumber(price))
      return 0.0;

   double scaled = price / tick_size;
   if (!MathIsValidNumber(scaled))
      return 0.0;
   double steps = MathRound(scaled);
   if (direction < 0)
      steps = MathFloor(scaled + 1e-9);
   else if (direction > 0)
      steps = MathCeil(scaled - 1e-9);

   return NormalizeDouble(steps * tick_size, digits);
}

int VolumeDigits(double step_vol)
{
   for (int digits = 0; digits <= 8; digits++)
   {
      if (MathAbs(NormalizeDouble(step_vol, digits) - step_vol) < 1e-12)
         return digits;
   }
   return 8;
}

double NormalizeVolume(double raw_vol)
{
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double min_vol  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_vol  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if (step_vol <= 0.0 || raw_vol < min_vol)
      return 0.0;

   int vol_digits = VolumeDigits(step_vol);
   double steps = MathFloor(raw_vol / step_vol);
   double vol = NormalizeDouble(steps * step_vol, vol_digits);

   // NormalizeDouble must never turn a floor operation into risk overshoot.
   if (vol > raw_vol)
      vol = NormalizeDouble(vol - step_vol, vol_digits);

   if (vol < min_vol) return 0.0;
   if (vol > max_vol)
   {
      double max_steps = MathFloor(max_vol / step_vol);
      vol = NormalizeDouble(max_steps * step_vol, vol_digits);
   }

   return vol;
}

bool CalculatePositionSize(double entry, double sl, ENUM_ORDER_TYPE order_type, double &out_vol)
{
   out_vol = 0.0;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if (equity <= 0.0 || InpRiskPercent <= 0.0)
      return false;

   double risk_money = equity * (InpRiskPercent / 100.0);

   ENUM_ORDER_TYPE calc_type;
   if (order_type == ORDER_TYPE_BUY_LIMIT)
      calc_type = ORDER_TYPE_BUY;
   else if (order_type == ORDER_TYPE_SELL_LIMIT)
      calc_type = ORDER_TYPE_SELL;
   else
      return false;

   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double min_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if (tick_size <= 0.0 || min_vol <= 0.0 || max_vol < min_vol)
      return false;

   double reference_vol = MathMin(1.0, max_vol);
   if (reference_vol < min_vol)
      reference_vol = min_vol;

   double adverse_entry = entry;
   double adverse_stop = sl;
   double entry_slippage = (double)InpAdverseEntrySlippageTicks * tick_size;
   double stop_slippage = (double)InpAdverseStopSlippageTicks * tick_size;
   if (calc_type == ORDER_TYPE_BUY)
   {
      adverse_entry += entry_slippage;
      adverse_stop -= stop_slippage;
   }
   else
   {
      adverse_entry -= entry_slippage;
      adverse_stop += stop_slippage;
   }

   double profit_reference = 0.0;
   if (!OrderCalcProfit(calc_type, _Symbol, reference_vol,
                        adverse_entry, adverse_stop, profit_reference))
   {
      if (InpVerboseLog)
         PrintFormat("WARNING: OrderCalcProfit failed for reference volume %.8f. Error: %d",
                     reference_vol, GetLastError());
      return false;
   }

   if (!MathIsValidNumber(profit_reference) || profit_reference >= 0.0)
   {
      if (InpVerboseLog)
         PrintFormat("WARNING: OrderCalcProfit did not return a valid adverse loss: %.2f",
                     profit_reference);
      return false;
   }

   double loss_per_lot = (-profit_reference / reference_vol) +
                         InpEstimatedRoundTurnCostPerLot;
   if (!MathIsValidNumber(loss_per_lot) || loss_per_lot <= 0.0)
      return false;

   double raw_vol = risk_money / loss_per_lot;
   out_vol = NormalizeVolume(raw_vol);

   if (out_vol < min_vol)
      return false;

   // Recalculate the exact normalized volume and reject even a rounding-cent
   // overshoot. Costs are explicitly included in the same account currency.
   double exact_profit = 0.0;
   if (!OrderCalcProfit(calc_type, _Symbol, out_vol,
                        adverse_entry, adverse_stop, exact_profit) ||
       !MathIsValidNumber(exact_profit) || exact_profit >= 0.0)
      return false;
   double exact_worst_loss = -exact_profit +
                             InpEstimatedRoundTurnCostPerLot * out_vol;
   if (!MathIsValidNumber(exact_worst_loss) || exact_worst_loss > risk_money + 0.005)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Normalized volume worst loss %.2f exceeds budget %.2f.",
                     exact_worst_loss, risk_money);
      out_vol = 0.0;
      return false;
   }

   double required_margin = 0.0;
   ResetLastError();
   if (!OrderCalcMargin(calc_type, _Symbol, out_vol, adverse_entry, required_margin) ||
       !MathIsValidNumber(required_margin) || required_margin <= 0.0)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: OrderCalcMargin failed or returned invalid margin. Error: %d",
                     GetLastError());
      out_vol = 0.0;
      return false;
   }

   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double allowed_margin = free_margin * InpMaxFreeMarginUsagePct / 100.0;
   if (!MathIsValidNumber(free_margin) || free_margin <= 0.0 ||
       required_margin > allowed_margin)
   {
      if (InpVerboseLog)
         PrintFormat("GUARD REJECT: Required margin %.2f exceeds %.2f%% of free margin (limit %.2f).",
                     required_margin, InpMaxFreeMarginUsagePct, allowed_margin);
      out_vol = 0.0;
      return false;
   }

   return true;
}

bool FindOriginalLimitGeometry(const long position_identifier,
                               const datetime position_time,
                               double &requested_entry,
                               double &original_stop,
                               double &original_target)
{
   requested_entry = 0.0;
   original_stop = 0.0;
   original_target = 0.0;
   if (position_identifier <= 0 || position_time <= 0)
      return false;

   long lookback_seconds = 86400;
   int timeframe_seconds = PeriodSeconds(m_timeframe);
   if (timeframe_seconds > 0)
   {
      long setup_window = (long)timeframe_seconds * (long)(InpPendingOrderBars + 2);
      if (setup_window > lookback_seconds)
         lookback_seconds = setup_window;
   }
   datetime history_from = (position_time > lookback_seconds)
                           ? position_time - (datetime)lookback_seconds : 0;
   if (!HistorySelect(history_from, TimeCurrent()))
      return false;

   int deals_total = HistoryDealsTotal();
   for (int i = 0; i < deals_total; i++)
   {
      ulong deal_ticket = HistoryDealGetTicket(i);
      if (deal_ticket == 0 ||
          HistoryDealGetInteger(deal_ticket, DEAL_POSITION_ID) != position_identifier ||
          HistoryDealGetInteger(deal_ticket, DEAL_MAGIC) != (long)InpMagicNumber ||
          HistoryDealGetString(deal_ticket, DEAL_SYMBOL) != _Symbol)
         continue;

      ENUM_DEAL_ENTRY deal_entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal_ticket, DEAL_ENTRY);
      if (deal_entry != DEAL_ENTRY_IN && deal_entry != DEAL_ENTRY_INOUT)
         continue;

      ulong order_ticket = (ulong)HistoryDealGetInteger(deal_ticket, DEAL_ORDER);
      if (order_ticket == 0)
         continue;
      ENUM_ORDER_TYPE order_type = (ENUM_ORDER_TYPE)HistoryOrderGetInteger(order_ticket, ORDER_TYPE);
      if (order_type != ORDER_TYPE_BUY_LIMIT && order_type != ORDER_TYPE_SELL_LIMIT)
         continue;

      double order_price = HistoryOrderGetDouble(order_ticket, ORDER_PRICE_OPEN);
      double order_stop = HistoryOrderGetDouble(order_ticket, ORDER_SL);
      double order_target = HistoryOrderGetDouble(order_ticket, ORDER_TP);
      if (order_price > 0.0 && order_stop > 0.0 && order_target > 0.0 &&
          MathIsValidNumber(order_price) && MathIsValidNumber(order_stop) &&
          MathIsValidNumber(order_target))
      {
         requested_entry = order_price;
         original_stop = order_stop;
         original_target = order_target;
         return true;
      }
   }
   return false;
}

bool RestoreSetupGeometry(ENUM_SIGNAL_DIR dir, double entry, double stop, double target, datetime setup_time)
{
   if (dir == SIGNAL_NONE || entry <= 0.0 || stop <= 0.0 || target <= 0.0)
      return false;

   // Restore from immutable entry/TP geometry. The live SL may already have moved
   // to break-even and therefore must never define the original strategy range.
   double ratio_distance = InpTargetRatio - InpEntryRatio;
   if (ratio_distance <= 0.0)
      return false;

   double restored_range = (dir == SIGNAL_BUY)
                           ? (target - entry) / ratio_distance
                           : (entry - target) / ratio_distance;
   if (restored_range <= 0.0 || !MathIsValidNumber(restored_range))
      return false;

   double restored_p0 = (dir == SIGNAL_BUY)
                        ? entry - InpEntryRatio * restored_range
                        : entry + InpEntryRatio * restored_range;
   double original_stop = (dir == SIGNAL_BUY)
                          ? NormalizePriceDirectional(restored_p0 + InpStopRatio * restored_range, -1)
                          : NormalizePriceDirectional(restored_p0 - InpStopRatio * restored_range, 1);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tolerance = MathMax(tick_size, SymbolInfoDouble(_Symbol, SYMBOL_POINT)) * 2.0;
   if (original_stop <= 0.0 || tolerance <= 0.0)
      return false;

   // A moved SL is valid only when it is at least as protective as the original.
   if (dir == SIGNAL_BUY && (stop < original_stop - tolerance || stop >= target))
      return false;
   if (dir == SIGNAL_SELL && (stop > original_stop + tolerance || stop <= target))
      return false;

   m_setup.dir = dir;
   m_setup.signal_time = setup_time;
   m_setup.anchor_time = setup_time;
   m_setup.pending_order_time = setup_time;
   m_setup.range = restored_range;
   m_setup.entry_price = entry;
   m_setup.stop_price = original_stop;
   m_setup.target_price = target;

   if (dir == SIGNAL_BUY)
   {
      m_setup.P0 = restored_p0;
      m_setup.P1 = m_setup.P0 + restored_range;
      m_setup.visual_target_price = NormalizePriceDirectional(m_setup.P0 + InpVisualTargetRatio * restored_range, 0);
   }
   else
   {
      m_setup.P0 = restored_p0;
      m_setup.P1 = m_setup.P0 - restored_range;
      m_setup.visual_target_price = NormalizePriceDirectional(m_setup.P0 - InpVisualTargetRatio * restored_range, 0);
   }

   return true;
}

bool CheckAndApplyBreakEven()
{
   if (!InpUseBreakEven || m_setup.position_ticket == 0)
      return true;

   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard blocked break-even modification");
      return false;
   }

   datetime now = TimeCurrent();
   if (m_last_break_even_attempt != 0 && now - m_last_break_even_attempt < 1)
      return true;

   if (!PositionSelectByTicket(m_setup.position_ticket))
   {
      m_sync_required = true;
      return false;
   }
   if (PositionGetString(POSITION_SYMBOL) != _Symbol ||
       PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
      return false;

   ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   ENUM_SIGNAL_DIR dir = (pos_type == POSITION_TYPE_BUY) ? SIGNAL_BUY : SIGNAL_SELL;
   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double current_sl = PositionGetDouble(POSITION_SL);
   double current_tp = PositionGetDouble(POSITION_TP);
   if (entry <= 0.0 || current_sl <= 0.0 || current_tp <= 0.0 ||
       m_setup.range <= 0.0 || m_setup.dir != dir)
      return false;

   MqlTick tick;
   if (!SymbolInfoTick(_Symbol, tick) || tick.bid <= 0.0 || tick.ask <= 0.0)
      return false;

   double trigger = (dir == SIGNAL_BUY)
                    ? m_setup.P0 + InpBETriggerFibRatio * m_setup.range
                    : m_setup.P0 - InpBETriggerFibRatio * m_setup.range;
   if ((dir == SIGNAL_BUY && tick.bid < trigger) ||
       (dir == SIGNAL_SELL && tick.ask > trigger))
      return true;

   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if (tick_size <= 0.0 || point <= 0.0)
      return false;

   double desired_sl = (dir == SIGNAL_BUY)
                       ? NormalizePriceDirectional(entry + InpBEOffsetTicks * tick_size, -1)
                       : NormalizePriceDirectional(entry - InpBEOffsetTicks * tick_size, 1);
   double tolerance = 0.5 * tick_size;
   if (desired_sl <= 0.0)
      return false;

   // Idempotence and monotonicity: never make an existing stop less protective.
   if ((dir == SIGNAL_BUY && current_sl >= desired_sl - tolerance) ||
       (dir == SIGNAL_SELL && current_sl <= desired_sl + tolerance))
      return true;

   long stops_points = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freeze_points = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double min_distance = (double)MathMax(stops_points, freeze_points) * point;
   if ((dir == SIGNAL_BUY && tick.bid - desired_sl < min_distance) ||
       (dir == SIGNAL_SELL && desired_sl - tick.ask < min_distance))
      return true;

   m_last_break_even_attempt = now;
   bool modified = m_safety_trade.PositionModify(m_setup.position_ticket, desired_sl, current_tp);
   uint retcode = m_safety_trade.ResultRetcode();
   if (modified && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_NO_CHANGES))
   {
      m_sync_required = true;
      m_last_status = "break-even active";
      PrintFormat("MANAGEMENT: [RSIFibEA] Position #%llu SL moved to %.5f at Fib %.2f.",
                  m_setup.position_ticket, desired_sl, InpBETriggerFibRatio);
      return true;
   }

   m_last_status = "break-even retry pending";
   PrintFormat("WARNING: [RSIFibEA] Break-even modify failed for #%llu. Retcode: %u (%s).",
               m_setup.position_ticket, retcode, m_safety_trade.ResultRetcodeDescription());
   return false;
}

bool CheckAndApplyFibTrailingStop()
{
   if (!InpUseFibTrailingStop || m_setup.position_ticket == 0)
      return true;

   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard blocked trailing-stop modification");
      return false;
   }

   datetime now = TimeCurrent();
   if (m_last_break_even_attempt != 0 && now - m_last_break_even_attempt < 1)
      return true;

   if (!PositionSelectByTicket(m_setup.position_ticket))
   {
      m_sync_required = true;
      return false;
   }
   if (PositionGetString(POSITION_SYMBOL) != _Symbol ||
       PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
      return false;

   ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   ENUM_SIGNAL_DIR dir = (pos_type == POSITION_TYPE_BUY) ? SIGNAL_BUY : SIGNAL_SELL;
   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double current_sl = PositionGetDouble(POSITION_SL);
   double current_tp = PositionGetDouble(POSITION_TP);
   if (entry <= 0.0 || current_sl <= 0.0 || current_tp <= 0.0 ||
       m_setup.range <= 0.0 || m_setup.dir != dir)
      return false;

   MqlTick tick;
   if (!SymbolInfoTick(_Symbol, tick) || tick.bid <= 0.0 || tick.ask <= 0.0)
      return false;

   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if (tick_size <= 0.0 || point <= 0.0)
      return false;

   // Multi-tier Fibonacci trailing stop levels:
   // Tier 5: Fib 2.000 reached -> lock Fib 1.618
   // Tier 4: Fib 1.618 reached -> lock Fib 1.000
   // Tier 3: Fib 1.000 reached -> lock Fib 0.382
   // Tier 2: Fib 0.618 reached -> lock Fib 0.000 (P0)
   // Tier 1: Fib 0.382 reached -> lock Break-Even (entry + offset)
   double desired_sl = 0.0;
   string tier_desc = "";

   if (dir == SIGNAL_BUY)
   {
      double p_bid = tick.bid;
      if (p_bid >= m_setup.P0 + 2.000 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(m_setup.P0 + 1.618 * m_setup.range, -1);
         tier_desc = "Fib 2.00 -> lock 1.618";
      }
      else if (p_bid >= m_setup.P0 + 1.618 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(m_setup.P0 + 1.000 * m_setup.range, -1);
         tier_desc = "Fib 1.618 -> lock 1.000";
      }
      else if (p_bid >= m_setup.P0 + 1.272 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(m_setup.P0 + 0.618 * m_setup.range, -1);
         tier_desc = "Fib 1.272 -> lock 0.618";
      }
      else if (p_bid >= m_setup.P0 + 0.618 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(entry + InpBEOffsetTicks * tick_size, -1);
         tier_desc = "Fib 0.618 -> lock BE";
      }
   }
   else
   {
      double p_ask = tick.ask;
      if (p_ask <= m_setup.P0 - 2.000 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(m_setup.P0 - 1.618 * m_setup.range, 1);
         tier_desc = "Fib 2.00 -> lock 1.618";
      }
      else if (p_ask <= m_setup.P0 - 1.618 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(m_setup.P0 - 1.000 * m_setup.range, 1);
         tier_desc = "Fib 1.618 -> lock 1.000";
      }
      else if (p_ask <= m_setup.P0 - 1.272 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(m_setup.P0 - 0.618 * m_setup.range, 1);
         tier_desc = "Fib 1.272 -> lock 0.618";
      }
      else if (p_ask <= m_setup.P0 - 0.618 * m_setup.range)
      {
         desired_sl = NormalizePriceDirectional(entry - InpBEOffsetTicks * tick_size, 1);
         tier_desc = "Fib 0.618 -> lock BE";
      }
   }

   if (desired_sl <= 0.0)
      return true;

   double tolerance = 0.5 * tick_size;

   // Idempotence and monotonicity: never make an existing stop less protective.
   if ((dir == SIGNAL_BUY && current_sl >= desired_sl - tolerance) ||
       (dir == SIGNAL_SELL && current_sl <= desired_sl + tolerance))
      return true;

   long stops_points = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   long freeze_points = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double min_distance = (double)MathMax(stops_points, freeze_points) * point;
   if ((dir == SIGNAL_BUY && tick.bid - desired_sl < min_distance) ||
       (dir == SIGNAL_SELL && desired_sl - tick.ask < min_distance))
      return true;

   m_last_break_even_attempt = now;
   bool modified = m_safety_trade.PositionModify(m_setup.position_ticket, desired_sl, current_tp);
   uint retcode = m_safety_trade.ResultRetcode();
   if (modified && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_NO_CHANGES))
   {
      m_sync_required = true;
      m_last_status = "trailing-stop active";
      PrintFormat("MANAGEMENT: [RSIFibEA] Position #%llu SL trailed to %.5f (%s).",
                  m_setup.position_ticket, desired_sl, tier_desc);
      return true;
   }

   m_last_status = "trailing-stop retry pending";
   PrintFormat("WARNING: [RSIFibEA] Trailing stop modify failed for #%llu. Retcode: %u (%s).",
               m_setup.position_ticket, retcode, m_safety_trade.ResultRetcodeDescription());
   return false;
}

bool DeleteResidualOrder(ulong ticket)
{
   if (!IsStrictDemoContext())
   {
      EnterFault("Strict demo/tester guard blocked residual-order deletion");
      return false;
   }

   if (ticket == 0 || !OrderSelect(ticket))
      return true;

   if (m_last_cancel_attempt != 0 && TimeCurrent() - m_last_cancel_attempt < 1)
      return false;
   m_last_cancel_attempt = TimeCurrent();

   bool deleted = m_trade.OrderDelete(ticket);
   uint retcode = m_trade.ResultRetcode();
   if (deleted && retcode == TRADE_RETCODE_DONE)
   {
      m_sync_required = true;
      PrintFormat("WARNING: [RSIFibEA] Deleted residual pending volume #%llu after position fill.", ticket);
      return true;
   }

   PrintFormat("ERROR: [RSIFibEA] Residual pending order #%llu could not be deleted. Retcode: %u (%s).",
               ticket, retcode, m_trade.ResultRetcodeDescription());
   return false;
}

void EnterFault(const string reason)
{
   if (m_state != STATE_FAULT || m_fault_reason != reason)
      PrintFormat("CRITICAL: [RSIFibEA] FAULT: %s", reason);

   m_fault_reason = reason;
   m_last_status = reason;
   m_state = STATE_FAULT;
}

void CaptureBrokerSnapshot(BrokerSnapshot &snapshot)
{
   snapshot.Reset();

   int positions_total = PositionsTotal();
   for (int i = 0; i < positions_total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;

      snapshot.symbol_positions++;
      if (PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
         continue;

      snapshot.managed_positions++;
      if (snapshot.position_ticket == 0)
         snapshot.position_ticket = ticket;
   }

   int orders_total = OrdersTotal();
   for (int i = 0; i < orders_total; i++)
   {
      ulong ticket = OrderGetTicket(i);
      if (ticket == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;

      snapshot.symbol_orders++;
      if (OrderGetInteger(ORDER_MAGIC) != (long)InpMagicNumber)
         continue;

      snapshot.managed_orders++;
      ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      if (type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT)
      {
         snapshot.managed_limits++;
         if (snapshot.limit_ticket == 0)
            snapshot.limit_ticket = ticket;
      }
      else
         snapshot.managed_unsupported++;
   }
}

ENUM_PROTECTION_STATUS ValidatePositionProtection(const ulong ticket)
{
   if (ticket == 0 || !PositionSelectByTicket(ticket))
      return PROTECTION_NOT_FOUND;
   if (PositionGetString(POSITION_SYMBOL) != _Symbol ||
       PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
      return PROTECTION_NOT_FOUND;

   double entry = PositionGetDouble(POSITION_PRICE_OPEN);
   double stop = PositionGetDouble(POSITION_SL);
   double target = PositionGetDouble(POSITION_TP);
   if (entry <= 0.0 || stop <= 0.0 || target <= 0.0 ||
       !MathIsValidNumber(entry) || !MathIsValidNumber(stop) || !MathIsValidNumber(target))
      return PROTECTION_INVALID;

   ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   if (type == POSITION_TYPE_BUY && (target <= entry || stop >= target))
      return PROTECTION_INVALID;
   if (type == POSITION_TYPE_SELL && (target >= entry || stop <= target))
      return PROTECTION_INVALID;

   return PROTECTION_OK;
}

void ServiceUnprotectedPosition(const ulong active_pos)
{
   m_protection_status = "INVALID";
   EnterFault(StringFormat("Position #%llu missing/invalid SL or TP", active_pos));
   if (!InpCloseUnprotectedPosition)
      return;

   if (!IsStrictDemoContext())
   {
      Print("CRITICAL: [RSIFibEA] Strict demo/tester guard blocked emergency position mutation.");
      return;
   }

   if (m_last_emergency_close_attempt != 0 && TimeCurrent() - m_last_emergency_close_attempt < 10)
      return;
   m_last_emergency_close_attempt = TimeCurrent();

   bool closed = m_safety_trade.PositionClose(active_pos);
   uint retcode = m_safety_trade.ResultRetcode();
   if (closed && (retcode == TRADE_RETCODE_DONE || retcode == TRADE_RETCODE_DONE_PARTIAL))
   {
      m_sync_required = true;
      PrintFormat("SAFETY: [RSIFibEA] Emergency close sent for unprotected position #%llu.", active_pos);
   }
   else
      PrintFormat("CRITICAL: [RSIFibEA] Emergency close failed for #%llu. Retcode: %u (%s).",
                  active_pos, retcode, m_safety_trade.ResultRetcodeDescription());
}

void MaybeSyncState(const bool force)
{
   ulong now_ms = GetTickCount64();
   bool watchdog_due = !MQLInfoInteger(MQL_TESTER) &&
                       (m_last_broker_scan_ms == 0 ||
                        now_ms - m_last_broker_scan_ms >= (ulong)InpStateWatchdogMs);
   if (force || m_sync_required || watchdog_due)
      SyncState();
}

bool PreflightManagedPositionProtection()
{
   int positions_total = PositionsTotal();
   for (int i = 0; i < positions_total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if (ticket == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol ||
          PositionGetInteger(POSITION_MAGIC) != (long)InpMagicNumber)
         continue;

      ENUM_PROTECTION_STATUS protection = ValidatePositionProtection(ticket);
      if (protection == PROTECTION_NOT_FOUND)
      {
         m_sync_required = true;
         return false;
      }
      if (protection == PROTECTION_INVALID)
      {
         ServiceUnprotectedPosition(ticket);
         return false;
      }
   }
   return true;
}

void SyncState()
{
   BrokerSnapshot snapshot;
   CaptureBrokerSnapshot(snapshot);
   m_sync_required = false;
   m_last_broker_scan_ms = GetTickCount64();

   // Protection has priority even when the overall snapshot is ambiguous.
   if (!PreflightManagedPositionProtection())
      return;

   if (snapshot.managed_positions > 1 || snapshot.managed_orders > 1 ||
       snapshot.managed_unsupported > 0 ||
       snapshot.managed_limits != snapshot.managed_orders)
   {
      EnterFault(StringFormat("Ambiguous snapshot: positions=%d orders=%d unsupported=%d",
                              snapshot.managed_positions, snapshot.managed_orders,
                              snapshot.managed_unsupported));
      return;
   }

   if ((snapshot.managed_positions > 0 || snapshot.managed_orders > 0) &&
       (snapshot.symbol_positions > snapshot.managed_positions ||
        snapshot.symbol_orders > snapshot.managed_orders))
   {
      EnterFault("Foreign exposure mixed with managed exposure on this symbol");
      return;
   }

   if (snapshot.managed_positions == 1)
   {
      m_empty_broker_confirmations = 0;
      ENUM_PROTECTION_STATUS protection = ValidatePositionProtection(snapshot.position_ticket);
      if (protection == PROTECTION_NOT_FOUND)
      {
         m_sync_required = true;
         return;
      }
      if (protection == PROTECTION_INVALID)
      {
         ServiceUnprotectedPosition(snapshot.position_ticket);
         return;
      }
      m_protection_status = "OK";

      if (!PositionSelectByTicket(snapshot.position_ticket))
      {
         m_sync_required = true;
         return;
      }

      bool position_changed = (m_setup.position_ticket != snapshot.position_ticket ||
                               m_setup.dir == SIGNAL_NONE);
      ENUM_POSITION_TYPE pos_type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      ENUM_SIGNAL_DIR dir = (pos_type == POSITION_TYPE_BUY) ? SIGNAL_BUY : SIGNAL_SELL;
      double entry = PositionGetDouble(POSITION_PRICE_OPEN);
      double stop = PositionGetDouble(POSITION_SL);
      double target = PositionGetDouble(POSITION_TP);
      datetime setup_time = (datetime)PositionGetInteger(POSITION_TIME);
      long position_identifier = PositionGetInteger(POSITION_IDENTIFIER);
      ulong known_pending = m_setup.pending_ticket;

      bool has_live_geometry = (m_setup.dir == dir && m_setup.range > 0.0 &&
                                m_setup.P0 > 0.0 && m_setup.stop_price > 0.0 &&
                                m_setup.target_price > 0.0);
      if (has_live_geometry)
      {
         double tolerance = MathMax(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE),
                                    SymbolInfoDouble(_Symbol, SYMBOL_POINT)) * 2.0;
         bool target_matches = (tolerance > 0.0 &&
                                MathAbs(target - m_setup.target_price) <= tolerance);
         bool stop_protective = (dir == SIGNAL_BUY)
                                ? (stop >= m_setup.stop_price - tolerance && stop < target)
                                : (stop <= m_setup.stop_price + tolerance && stop > target);
         if (!stop_protective)
         {
            ServiceUnprotectedPosition(snapshot.position_ticket);
            return;
         }
         if (!target_matches)
         {
            EnterFault(StringFormat("Position #%llu protection differs from original setup",
                                    snapshot.position_ticket));
            return;
         }
         // Preserve original P0/range/SL while using the actual fill for break-even.
         m_setup.entry_price = entry;
         m_setup.target_price = target;
         m_setup.position_ticket = snapshot.position_ticket;
      }
      else
      {
         double geometry_entry = entry;
         double historical_entry = 0.0;
         double historical_stop = 0.0;
         double historical_target = 0.0;
         bool has_history = FindOriginalLimitGeometry(position_identifier, setup_time,
                                                      historical_entry, historical_stop,
                                                      historical_target);
         if (has_history)
         {
            geometry_entry = historical_entry;
            double history_tolerance = MathMax(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE),
                                               SymbolInfoDouble(_Symbol, SYMBOL_POINT)) * 2.0;
            bool stop_widened = (dir == SIGNAL_BUY)
                                ? (stop < historical_stop - history_tolerance)
                                : (stop > historical_stop + history_tolerance);
            if (stop_widened)
            {
               ServiceUnprotectedPosition(snapshot.position_ticket);
               return;
            }
            if (history_tolerance <= 0.0 ||
                MathAbs(target - historical_target) > history_tolerance)
            {
               EnterFault(StringFormat("Position #%llu TP differs from historical setup",
                                       snapshot.position_ticket));
               return;
            }
         }
         if (!RestoreSetupGeometry(dir, geometry_entry, stop, target, setup_time))
         {
            // With no trustworthy geometry we cannot prove that the live stop
            // still respects the originally sized risk. Treat the position as
            // unprotected so the configured emergency-close policy applies.
            PrintFormat("CRITICAL: [RSIFibEA] Position #%llu geometry cannot be restored safely.",
                        snapshot.position_ticket);
            ServiceUnprotectedPosition(snapshot.position_ticket);
            return;
         }
         // The historical limit reconstructs P0/range; BE uses the actual fill.
         m_setup.entry_price = entry;
      }
      m_setup.position_ticket = snapshot.position_ticket;

      if (snapshot.managed_orders == 1)
      {
         if (known_pending == 0 || snapshot.limit_ticket != known_pending)
         {
            PrintFormat("WARNING: [RSIFibEA] Adopting residual order #%llu beside active position #%llu for safe deletion.",
                        snapshot.limit_ticket, snapshot.position_ticket);
         }
         m_setup.pending_ticket = snapshot.limit_ticket;
         m_residual_order_ticket = snapshot.limit_ticket;
         if (DeleteResidualOrder(snapshot.limit_ticket))
            m_sync_required = true;
      }
      else
      {
         m_setup.pending_ticket = 0;
         m_residual_order_ticket = 0;
      }

      m_fault_reason = "";
      m_last_status = "position synchronized";
      m_state = STATE_IN_POSITION;
      if (position_changed)
         DrawSetupObjects();
      return;
   }

   if (snapshot.managed_orders == 1)
   {
      m_empty_broker_confirmations = 0;
      if (!OrderSelect(snapshot.limit_ticket))
      {
         m_sync_required = true;
         return;
      }

      bool order_changed = (m_setup.pending_ticket != snapshot.limit_ticket ||
                            m_setup.dir == SIGNAL_NONE || m_setup.pending_order_time == 0);
      ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
      ENUM_SIGNAL_DIR dir = (type == ORDER_TYPE_BUY_LIMIT) ? SIGNAL_BUY : SIGNAL_SELL;
      datetime setup_time = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      double entry = OrderGetDouble(ORDER_PRICE_OPEN);
      double stop = OrderGetDouble(ORDER_SL);
      double target = OrderGetDouble(ORDER_TP);

      if (!RestoreSetupGeometry(dir, entry, stop, target, setup_time))
      {
         EnterFault(StringFormat("Pending order #%llu geometry cannot be restored",
                                 snapshot.limit_ticket));
         return;
      }
      m_setup.pending_ticket = snapshot.limit_ticket;
      m_setup.position_ticket = 0;
      m_fault_reason = "";
      m_protection_status = "PENDING";
      m_last_status = "pending order synchronized";
      m_state = STATE_PENDING_ORDER;
      if (order_changed)
      {
         PrintFormat("INFO: [RSIFibEA] Restored pending order #%llu.", snapshot.limit_ticket);
         DrawSetupObjects();
      }
      return;
   }

   if (snapshot.symbol_positions > 0 || snapshot.symbol_orders > 0)
   {
      if (m_state == STATE_PENDING_ORDER || m_state == STATE_IN_POSITION || m_state == STATE_FAULT)
         EnterFault("Only foreign exposure remains on the managed symbol");
      return;
   }

   if (m_state == STATE_PENDING_ORDER || m_state == STATE_IN_POSITION || m_state == STATE_FAULT)
   {
      m_empty_broker_confirmations++;
      if (m_empty_broker_confirmations < 2)
      {
         m_sync_required = true;
         return;
      }
      ResetSetupToIdle();
      m_last_status = "flat";
   }
   else
      m_empty_broker_confirmations = 0;
}

//+------------------------------------------------------------------+
//| CHART VISUALIZATION HELPERS                                      |
//+------------------------------------------------------------------+

void UpdateDashboard()
{
   if (!InpShowDashboard || (MQLInfoInteger(MQL_TESTER) && !InpDashboardInTester))
      return;

   ulong now_ms = GetTickCount64();
   if (m_last_dashboard_ms != 0 && now_ms - m_last_dashboard_ms < 1000)
      return;
   m_last_dashboard_ms = now_ms;

   MqlTick tick;
   double spread_points = 0.0;
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if (point > 0.0 && SymbolInfoTick(_Symbol, tick) && tick.ask >= tick.bid)
      spread_points = (tick.ask - tick.bid) / point;

   string direction = (m_setup.dir == SIGNAL_BUY) ? "BUY" :
                      (m_setup.dir == SIGNAL_SELL) ? "SELL" : "NONE";
   string filters = StringFormat("RSIQ:%s  MTF:%s  VOL:%s  BE:%s",
                                 InpUseRSIQualityFilter ? "ON" : "OFF",
                                 InpUseMTFTrendFilter ? "ON" : "OFF",
                                 InpUseVolatilityRegime ? "ON" : "OFF",
                                 InpUseBreakEven ? "ON" : "OFF");
   string status = (m_state == STATE_FAULT && m_fault_reason != "")
                   ? m_fault_reason : m_last_status;

   Comment(StringFormat("RSI Fib EA v2.00 | DEMO GUARD: %s\n"
                        "State: %s | Direction: %s | Protection: %s\n"
                        "Spread: %.1f pts | Order: %llu | Position: %llu\n"
                        "P0 %.5f | P1 %.5f | Entry %.5f | SL %.5f | TP %.5f\n"
                        "%s\nStatus: %s",
                        InpDemoOnly ? "ON" : "OFF", EnumToString(m_state), direction,
                        m_protection_status, spread_points, m_setup.pending_ticket,
                        m_setup.position_ticket, m_setup.P0, m_setup.P1,
                        m_setup.entry_price, m_setup.stop_price, m_setup.target_price,
                        filters, status));
}

void DrawSetupObjects()
{
   if (!InpDrawChartObjects) return;

   RemoveChartObjects();

   color col_p0      = clrGray;
   color col_p1      = clrDarkGray;
   color col_entry   = clrBlue;
   color col_stop    = clrRed;
   color col_target  = clrGreen;
   color col_vtarget = clrDarkGreen;

   CreateHLine(m_obj_prefix + "P0", m_setup.P0, col_p0, STYLE_DOT, 1, "P0 (0.00)");
   CreateHLine(m_obj_prefix + "P1", m_setup.P1, col_p1, STYLE_DOT, 1, "P1 (1.00)");
   CreateHLine(m_obj_prefix + "Entry", m_setup.entry_price, col_entry, STYLE_SOLID, 2, StringFormat("Entry (%.2f)", InpEntryRatio));
   CreateHLine(m_obj_prefix + "Stop", m_setup.stop_price, col_stop, STYLE_SOLID, 2, StringFormat("Stop (%.2f)", InpStopRatio));
   CreateHLine(m_obj_prefix + "Target", m_setup.target_price, col_target, STYLE_SOLID, 2, StringFormat("Target (%.2f)", InpTargetRatio));
   CreateHLine(m_obj_prefix + "VisualTarget", m_setup.visual_target_price, col_vtarget, STYLE_DASH, 1, StringFormat("Visual Target (%.2f)", InpVisualTargetRatio));
}

void CreateHLine(string name, double price, color col, ENUM_LINE_STYLE style, int width, string text)
{
   if (ObjectFind(0, name) >= 0)
      ObjectDelete(0, name);

   if (ObjectCreate(0, name, OBJ_HLINE, 0, 0, price))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, col);
      ObjectSetInteger(0, name, OBJPROP_STYLE, style);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, name, OBJPROP_TEXT, text);
   }
}

void RemoveChartObjects()
{
   string suffixes[6] = {"P0", "P1", "Entry", "Stop", "Target", "VisualTarget"};
   for (int i = 0; i < 6; i++)
      ObjectDelete(0, m_obj_prefix + suffixes[i]);
}
//+------------------------------------------------------------------+
