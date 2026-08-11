//+------------------------------------------------------------------+
//|                                  RSIFibSymbolCatalogEA.mq5       |
//| Tester-only, read-only symbol discovery for research runners.    |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026"
#property version   "1.00"
#property description "Tester-only read-only catalog for RSIFib market discovery"
#property strict

bool IsResearchCandidate(const string symbol, const string description)
{
   // Do not match on path: thousands of individual equities can live below a
   // path named "NASDAQ" even though they are not the Nasdaq index/future.
   string text = symbol + " " + description;
   StringToLower(text);
   string terms[] = {"xau", "gold", "eurusd", "nasdaq", "nas100",
                     "ustec", "us100", "ndx", "micro e-mini nasdaq",
                     "e-mini nasdaq", "spx", "us500", "s&p 500",
                     "dow", "dax"};
   for (int i = 0; i < ArraySize(terms); i++)
   {
      if (StringFind(text, terms[i]) >= 0)
         return true;
   }
   return false;
}

int OnInit()
{
   if (!MQLInfoInteger(MQL_TESTER))
   {
      Print("CATALOG REFUSED: tester context is mandatory.");
      return INIT_FAILED;
   }

   int handle = FileOpen("RSIFibEA\\symbol_catalog.csv",
                         FILE_COMMON | FILE_WRITE | FILE_CSV | FILE_ANSI,
                         ';');
   if (handle == INVALID_HANDLE)
   {
      PrintFormat("CATALOG ERROR: FileOpen failed (%d).", GetLastError());
      return INIT_FAILED;
   }

   FileWrite(handle, "schema", "tester_only", "orders_sent", "symbol",
             "description", "path", "trade_mode", "calc_mode",
             "tick_size", "tick_value", "contract_size", "volume_min",
             "volume_step", "start_time", "expiration_time");

   int matches = 0;
   int total = SymbolsTotal(false);
   for (int i = 0; i < total; i++)
   {
      string symbol = SymbolName(i, false);
      if (StringLen(symbol) == 0)
         continue;
      string description = SymbolInfoString(symbol, SYMBOL_DESCRIPTION);
      string path = SymbolInfoString(symbol, SYMBOL_PATH);
      if (!IsResearchCandidate(symbol, description))
         continue;

      FileWrite(handle, "rsifib-mt5-symbol-catalog/v1", "true", "0", symbol,
                description, path,
                (long)SymbolInfoInteger(symbol, SYMBOL_TRADE_MODE),
                (long)SymbolInfoInteger(symbol, SYMBOL_TRADE_CALC_MODE),
                SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE),
                SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE),
                SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE),
                SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN),
                SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP),
                (long)SymbolInfoInteger(symbol, SYMBOL_START_TIME),
                (long)SymbolInfoInteger(symbol, SYMBOL_EXPIRATION_TIME));
      matches++;
   }
   FileClose(handle);
   PrintFormat("CATALOG COMPLETE: %d/%d matching symbols, orders_sent=0.",
               matches, total);
   return INIT_SUCCEEDED;
}

void OnTick()
{
   // Intentionally empty: this expert has no trading code.
}
