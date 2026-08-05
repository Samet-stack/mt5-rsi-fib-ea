//+------------------------------------------------------------------+
//|                                      RSIFibSymbolProbeEA.mq5     |
//| Read-only Strategy Tester probe. It never sends a trade request. |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property version   "1.00"
#property description "Read-only MT5 symbol specification probe (tester only)"
#property strict

input string InpProbeRelativePath = "RSIFibEA\\symbol_probe.json";

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   StringReplace(value, "\t", "\\t");
   return value;
}

string JsonString(const string value)
{
   return "\"" + JsonEscape(value) + "\"";
}

string JsonDouble(const double value, const int digits = 10)
{
   if (!MathIsValidNumber(value))
      return "null";
   return DoubleToString(value, digits);
}

void AppendJsonField(string &json,
                     const string key,
                     const string value,
                     bool &first)
{
   if (!first)
      json += ",";
   json += "\n  " + JsonString(key) + ": " + value;
   first = false;
}

string BuildTradeSessionsJson()
{
   string result = "[";
   bool first = true;
   for (int day = 0; day <= 6; day++)
   {
      for (uint session = 0; session < 32; session++)
      {
         datetime from_time = 0;
         datetime to_time = 0;
         if (!SymbolInfoSessionTrade(_Symbol, (ENUM_DAY_OF_WEEK)day, session,
                                     from_time, to_time))
            break;
         if (!first)
            result += ",";
         result += "{\"day\":" + IntegerToString(day) +
                   ",\"index\":" + IntegerToString((long)session) +
                   ",\"from\":" + JsonString(TimeToString(from_time, TIME_MINUTES)) +
                   ",\"to\":" + JsonString(TimeToString(to_time, TIME_MINUTES)) + "}";
         first = false;
      }
   }
   result += "]";
   return result;
}

int OnInit()
{
   // This utility is intentionally impossible to attach to a live chart.
   if (!MQLInfoInteger(MQL_TESTER))
   {
      Print("CRITICAL: [RSIFibSymbolProbe] Strategy Tester context is mandatory.");
      return INIT_FAILED;
   }

   if (StringLen(InpProbeRelativePath) < 6 ||
       StringFind(InpProbeRelativePath, "..") >= 0 ||
       StringFind(InpProbeRelativePath, ":") >= 0)
   {
      Print("CRITICAL: [RSIFibSymbolProbe] Unsafe probe output path.");
      return INIT_PARAMETERS_INCORRECT;
   }

   MqlTick tick;
   bool has_tick = SymbolInfoTick(_Symbol, tick) && tick.bid > 0.0 && tick.ask > 0.0;
   double min_volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double margin_buy = 0.0;
   double margin_sell = 0.0;
   bool margin_buy_ok = has_tick && min_volume > 0.0 &&
                        OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, min_volume,
                                        tick.ask, margin_buy);
   bool margin_sell_ok = has_tick && min_volume > 0.0 &&
                         OrderCalcMargin(ORDER_TYPE_SELL, _Symbol, min_volume,
                                         tick.bid, margin_sell);

   double one_tick_buy_pnl = 0.0;
   double one_tick_sell_pnl = 0.0;
   bool one_tick_buy_ok = has_tick && min_volume > 0.0 && tick_size > 0.0 &&
                          OrderCalcProfit(ORDER_TYPE_BUY, _Symbol, min_volume,
                                          tick.ask, tick.ask - tick_size,
                                          one_tick_buy_pnl);
   bool one_tick_sell_ok = has_tick && min_volume > 0.0 && tick_size > 0.0 &&
                           OrderCalcProfit(ORDER_TYPE_SELL, _Symbol, min_volume,
                                           tick.bid, tick.bid + tick_size,
                                           one_tick_sell_pnl);

   string json = "{";
   bool first = true;
   AppendJsonField(json, "schema", JsonString("rsifib-mt5-symbol-probe/v1"), first);
   AppendJsonField(json, "generated_at", JsonString(TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS)), first);
   AppendJsonField(json, "tester_only", "true", first);
   AppendJsonField(json, "orders_sent", "0", first);
   AppendJsonField(json, "terminal_build", IntegerToString((long)TerminalInfoInteger(TERMINAL_BUILD)), first);
   AppendJsonField(json, "broker_company", JsonString(AccountInfoString(ACCOUNT_COMPANY)), first);
   AppendJsonField(json, "server", JsonString(AccountInfoString(ACCOUNT_SERVER)), first);
   AppendJsonField(json, "account_currency", JsonString(AccountInfoString(ACCOUNT_CURRENCY)), first);
   AppendJsonField(json, "account_trade_mode", IntegerToString(AccountInfoInteger(ACCOUNT_TRADE_MODE)), first);
   AppendJsonField(json, "account_margin_mode", IntegerToString(AccountInfoInteger(ACCOUNT_MARGIN_MODE)), first);
   AppendJsonField(json, "account_leverage", IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE)), first);
   AppendJsonField(json, "account_balance", JsonDouble(AccountInfoDouble(ACCOUNT_BALANCE), 2), first);
   AppendJsonField(json, "symbol", JsonString(_Symbol), first);
   AppendJsonField(json, "description", JsonString(SymbolInfoString(_Symbol, SYMBOL_DESCRIPTION)), first);
   AppendJsonField(json, "path", JsonString(SymbolInfoString(_Symbol, SYMBOL_PATH)), first);
   AppendJsonField(json, "basis", JsonString(SymbolInfoString(_Symbol, SYMBOL_BASIS)), first);
   AppendJsonField(json, "currency_base", JsonString(SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE)), first);
   AppendJsonField(json, "currency_profit", JsonString(SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT)), first);
   AppendJsonField(json, "currency_margin", JsonString(SymbolInfoString(_Symbol, SYMBOL_CURRENCY_MARGIN)), first);
   AppendJsonField(json, "digits", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)), first);
   AppendJsonField(json, "point", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_POINT), 10), first);
   AppendJsonField(json, "tick_size", JsonDouble(tick_size, 10), first);
   AppendJsonField(json, "tick_value", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), 10), first);
   AppendJsonField(json, "tick_value_profit", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_PROFIT), 10), first);
   AppendJsonField(json, "tick_value_loss", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS), 10), first);
   AppendJsonField(json, "contract_size", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE), 10), first);
   AppendJsonField(json, "volume_min", JsonDouble(min_volume, 10), first);
   AppendJsonField(json, "volume_max", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), 10), first);
   AppendJsonField(json, "volume_step", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), 10), first);
   AppendJsonField(json, "volume_limit", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_LIMIT), 10), first);
   AppendJsonField(json, "margin_initial", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_MARGIN_INITIAL), 10), first);
   AppendJsonField(json, "margin_maintenance", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_MARGIN_MAINTENANCE), 10), first);
   AppendJsonField(json, "margin_hedged", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_MARGIN_HEDGED), 10), first);
   AppendJsonField(json, "trade_calc_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_CALC_MODE)), first);
   AppendJsonField(json, "trade_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_MODE)), first);
   AppendJsonField(json, "execution_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_EXEMODE)), first);
   AppendJsonField(json, "filling_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE)), first);
   AppendJsonField(json, "order_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_ORDER_MODE)), first);
   AppendJsonField(json, "expiration_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE)), first);
   AppendJsonField(json, "stops_level", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)), first);
   AppendJsonField(json, "freeze_level", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)), first);
   AppendJsonField(json, "start_time", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_START_TIME)), first);
   AppendJsonField(json, "expiration_time", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_TIME)), first);
   AppendJsonField(json, "custom", (SymbolInfoInteger(_Symbol, SYMBOL_CUSTOM) ? "true" : "false"), first);
   AppendJsonField(json, "book_depth", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TICKS_BOOKDEPTH)), first);
   AppendJsonField(json, "swap_mode", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_SWAP_MODE)), first);
   AppendJsonField(json, "swap_rollover3days", IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_SWAP_ROLLOVER3DAYS)), first);
   AppendJsonField(json, "swap_long", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_SWAP_LONG), 10), first);
   AppendJsonField(json, "swap_short", JsonDouble(SymbolInfoDouble(_Symbol, SYMBOL_SWAP_SHORT), 10), first);
   AppendJsonField(json, "has_tick", (has_tick ? "true" : "false"), first);
   AppendJsonField(json, "bid", (has_tick ? JsonDouble(tick.bid, 10) : "null"), first);
   AppendJsonField(json, "ask", (has_tick ? JsonDouble(tick.ask, 10) : "null"), first);
   AppendJsonField(json, "spread", (has_tick ? JsonDouble(tick.ask - tick.bid, 10) : "null"), first);
   AppendJsonField(json, "min_volume_margin_buy_ok", (margin_buy_ok ? "true" : "false"), first);
   AppendJsonField(json, "min_volume_margin_buy", (margin_buy_ok ? JsonDouble(margin_buy, 10) : "null"), first);
   AppendJsonField(json, "min_volume_margin_sell_ok", (margin_sell_ok ? "true" : "false"), first);
   AppendJsonField(json, "min_volume_margin_sell", (margin_sell_ok ? JsonDouble(margin_sell, 10) : "null"), first);
   AppendJsonField(json, "min_volume_one_tick_buy_ok", (one_tick_buy_ok ? "true" : "false"), first);
   AppendJsonField(json, "min_volume_one_tick_buy_pnl", (one_tick_buy_ok ? JsonDouble(one_tick_buy_pnl, 10) : "null"), first);
   AppendJsonField(json, "min_volume_one_tick_sell_ok", (one_tick_sell_ok ? "true" : "false"), first);
   AppendJsonField(json, "min_volume_one_tick_sell_pnl", (one_tick_sell_ok ? JsonDouble(one_tick_sell_pnl, 10) : "null"), first);
   AppendJsonField(json, "trade_sessions", BuildTradeSessionsJson(), first);
   json += "\n}\n";

   ResetLastError();
   int handle = FileOpen(InpProbeRelativePath,
                         FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON,
                         0, CP_UTF8);
   if (handle == INVALID_HANDLE)
   {
      PrintFormat("CRITICAL: [RSIFibSymbolProbe] FileOpen failed. Error: %d", GetLastError());
      return INIT_FAILED;
   }
   uint written = FileWriteString(handle, json);
   FileFlush(handle);
   FileClose(handle);
   if (written != (uint)StringLen(json))
   {
      PrintFormat("CRITICAL: [RSIFibSymbolProbe] Incomplete output: %u/%d characters.",
                  written, StringLen(json));
      return INIT_FAILED;
   }

   PrintFormat("SUCCESS: [RSIFibSymbolProbe] Wrote read-only probe for %s to Common\\Files\\%s",
               _Symbol, InpProbeRelativePath);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   // Intentionally empty: this probe cannot place, modify or cancel orders.
}

double OnTester()
{
   return 0.0;
}
