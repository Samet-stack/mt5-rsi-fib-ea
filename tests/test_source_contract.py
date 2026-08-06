#!/usr/bin/env python3
"""Static safety contracts for MQL5 integration points not covered by math tests."""

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "MQL5" / "Experts" / "RSIFibRetracementEA.mq5"
PRESETS_DIR = PROJECT_ROOT / "presets"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")


def function_body(name):
    """Returns a top-level MQL function body using balanced braces."""
    match = re.search(
        rf"\b(?:void|bool|double|int)\s+{re.escape(name)}\s*\(", SOURCE)
    if match is None:
        raise AssertionError(f"MQL function {name} was not found")
    opening = SOURCE.find("{", match.end())
    if opening < 0:
        raise AssertionError(f"MQL function {name} has no body")
    depth = 0
    for index in range(opening, len(SOURCE)):
        if SOURCE[index] == "{":
            depth += 1
        elif SOURCE[index] == "}":
            depth -= 1
            if depth == 0:
                return SOURCE[opening + 1:index]
    raise AssertionError(f"MQL function {name} has unbalanced braces")


def block_after_token(text, token):
    """Returns the balanced code block immediately following ``token``."""
    token_index = text.find(token)
    if token_index < 0:
        raise AssertionError(f"MQL token was not found: {token}")
    opening = text.find("{", token_index + len(token))
    if opening < 0:
        raise AssertionError(f"MQL token has no following block: {token}")
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1:index]
    raise AssertionError(f"MQL block after {token} has unbalanced braces")


class TestMQL5SafetyContracts(unittest.TestCase):
    def test_every_preset_covers_each_input_exactly_once(self):
        input_names = re.findall(
            r"^\s*input\s+(?!group\b)[A-Za-z_][A-Za-z0-9_]*\s+"
            r"(Inp[A-Za-z0-9_]+)\s*=",
            SOURCE,
            flags=re.MULTILINE,
        )
        self.assertTrue(input_names)
        self.assertEqual(len(input_names), len(set(input_names)))

        preset_paths = sorted(PRESETS_DIR.glob("*.set"))
        self.assertTrue(preset_paths)
        for preset_path in preset_paths:
            with self.subTest(preset=preset_path.name):
                preset_names = []
                for raw_line in preset_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith(";"):
                        continue
                    name, separator, value = line.partition("=")
                    self.assertEqual(separator, "=", msg=f"Malformed line: {line}")
                    self.assertTrue(value, msg=f"Empty value: {line}")
                    preset_names.append(name.strip())

                self.assertEqual(len(preset_names), len(set(preset_names)))
                self.assertEqual(set(preset_names), set(input_names))

    def test_demo_guard_defaults_to_enabled(self):
        self.assertIn("input bool     InpDemoOnly              = true;", SOURCE)
        self.assertIn("ACCOUNT_TRADE_MODE_DEMO", SOURCE)
        self.assertIn("InpCloseUnprotectedPosition = true", SOURCE)

    def test_demo_guard_is_non_bypassable_and_precedes_mutations(self):
        validation_body = function_body("ValidateInputs")
        runtime_body = function_body("OnTick")
        self.assertIn("if (!InpDemoOnly)", validation_body)
        self.assertIn("IsStrictDemoContext()", runtime_body)
        self.assertLess(
            runtime_body.index("IsStrictDemoContext()"),
            runtime_body.index("MaybeSyncState("),
        )

        guarded_mutations = {
            "ExecutePendingOrder": "m_trade.BuyLimit",
            "CancelPendingOrder": "m_trade.OrderDelete",
            "CloseManagedPositionForContractCutoff": "m_safety_trade.PositionClose",
            "CheckAndApplyBreakEven": "m_safety_trade.PositionModify",
            "CheckAndApplyFibTrailingStop": "m_safety_trade.PositionModify",
            "DeleteResidualOrder": "m_trade.OrderDelete",
            "ServiceUnprotectedPosition": "m_safety_trade.PositionClose",
        }
        for function_name, mutation in guarded_mutations.items():
            with self.subTest(function=function_name):
                body = function_body(function_name)
                self.assertIn("IsStrictDemoContext()", body)
                self.assertLess(body.index("IsStrictDemoContext()"), body.index(mutation))

    def test_order_calc_profit_uses_market_direction(self):
        self.assertIn("calc_type = ORDER_TYPE_BUY;", SOURCE)
        self.assertIn("calc_type = ORDER_TYPE_SELL;", SOURCE)
        self.assertIn("OrderCalcProfit(calc_type", SOURCE)
        self.assertNotIn("OrderCalcProfit(order_type", SOURCE)

    def test_sizing_includes_verified_cost_slippage_and_margin(self):
        validation_body = function_body("ValidateInputs")
        sizing_body = function_body("CalculatePositionSize")
        self.assertIn("if (!InpCostModelVerified)", validation_body)
        self.assertIn("InpEstimatedRoundTurnCostPerLot < 0.0", validation_body)
        self.assertIn("InpRiskPercent > 0.25", validation_body)
        self.assertIn("InpAdverseEntrySlippageTicks", sizing_body)
        self.assertIn("InpAdverseStopSlippageTicks", sizing_body)
        self.assertIn("InpEstimatedRoundTurnCostPerLot * out_vol", sizing_body)
        self.assertIn("OrderCalcMargin(calc_type", sizing_body)
        self.assertIn("ACCOUNT_MARGIN_FREE", sizing_body)
        self.assertIn("InpMaxFreeMarginUsagePct", sizing_body)

    def test_pending_rechecks_market_conditions_on_every_tick(self):
        body = function_body("ProcessStatePendingOrder")
        guard_index = body.index("CheckSpread()")
        new_bar_index = body.index("if (is_new_bar)")
        self.assertLess(guard_index, new_bar_index)
        for guard in (
            "CheckRiskGuards()",
            "CheckSpread()",
            "CheckSetupSpread()",
            "CheckSession()",
            "CheckContractLifecycle()",
        ):
            self.assertIn(guard, body[:new_bar_index])
        self.assertIn("CancelPendingOrder()", body[:new_bar_index])

    def test_contract_lifecycle_rejects_near_expiry_futures(self):
        body = function_body("CheckContractLifecycle")
        cutoff_body = function_body("GetContractEntryCutoff")
        self.assertIn("SYMBOL_START_TIME", body)
        self.assertIn("GetContractEntryCutoff", body)
        self.assertIn("SYMBOL_EXPIRATION_TIME", cutoff_body)
        self.assertIn("InpMinDaysToContractExpiry", cutoff_body)
        self.assertIn("86400L", cutoff_body)
        self.assertIn("now >= entry_cutoff", body)
        self.assertIn("CheckContractLifecycle()", function_body("OnInit"))
        self.assertIn("CheckContractLifecycle()", function_body("ExecutePendingOrder"))

    def test_lifecycle_cutoff_does_not_abandon_existing_exposure_on_restart(self):
        init_body = function_body("OnInit")
        lifecycle_block = block_after_token(
            init_body, "if (!initial_lifecycle_ok)")
        self.assertNotIn("return INIT_FAILED", lifecycle_block)
        self.assertLess(
            init_body.index("CheckContractLifecycle()"),
            init_body.index("SyncState()"),
        )
        self.assertLess(
            init_body.index("SyncState()"),
            init_body.index("EnforceContractCutoffExposure()"),
        )

    def test_pending_expiration_cannot_reach_futures_cutoff(self):
        body = function_body("BuildPendingLifetime")
        self.assertIn("GetContractEntryCutoff", body)
        self.assertIn("requested_expiration >= (long)entry_cutoff", body)
        self.assertIn("would reach the contract cutoff", body)
        self.assertIn("broker_expiration = (datetime)safe_expiration", body)
        self.assertRegex(
            body,
            r"SYMBOL_EXPIRATION_GTC[\s\S]+contract_expiration\s*<=\s*0",
        )

    def test_pending_expiration_prefers_finite_modes_before_gtc(self):
        body = function_body("BuildPendingLifetime")
        mode_order = (
            "SYMBOL_EXPIRATION_SPECIFIED)",
            "SYMBOL_EXPIRATION_DAY)",
            "SYMBOL_EXPIRATION_SPECIFIED_DAY)",
            "SYMBOL_EXPIRATION_GTC)",
        )
        indices = [body.index(token) for token in mode_order]
        self.assertEqual(indices, sorted(indices))
        self.assertIn("day_mode_is_safe", body)

    def test_cutoff_enforcement_precedes_trade_permission_short_circuit(self):
        tick_body = function_body("OnTick")
        self.assertLess(
            tick_body.index("MaybeSyncState("),
            tick_body.index("EnforceContractCutoffExposure()"),
        )
        self.assertLess(
            tick_body.index("EnforceContractCutoffExposure()"),
            tick_body.index("IsTradeAllowed()"),
        )

    def test_cutoff_enforcement_flattens_managed_exposure_with_retry(self):
        enforcement_body = function_body("EnforceContractCutoffExposure")
        close_body = function_body("CloseManagedPositionForContractCutoff")
        self.assertIn("TimeCurrent() < entry_cutoff", enforcement_body)
        self.assertIn("CancelPendingOrder()", enforcement_body)
        self.assertIn("CloseManagedPositionForContractCutoff", enforcement_body)
        self.assertIn("m_safety_trade.PositionClose", close_body)
        self.assertIn("TRADE_RETCODE_DONE", close_body)
        self.assertIn("TRADE_RETCODE_DONE_PARTIAL", close_body)
        self.assertIn("Will retry", close_body)
        self.assertNotIn("ResetSetupToIdle", close_body)

    def test_volume_floor_is_not_hardcoded_to_two_decimals(self):
        self.assertIn("VolumeDigits(step_vol)", SOURCE)
        self.assertNotIn("NormalizeDouble(steps * step_vol, 2)", SOURCE)
        self.assertIn("if (vol > raw_vol)", SOURCE)

    def test_cancel_checks_server_result_before_reset(self):
        self.assertIn("if (deleted && retcode == TRADE_RETCODE_DONE)", SOURCE)
        self.assertIn("Will retry", SOURCE)

    def test_pending_order_is_rehydrated_after_restart(self):
        self.assertIn("ORDER_TIME_SETUP", SOURCE)
        self.assertIn("RestoreSetupGeometry", SOURCE)
        self.assertIn("m_setup.pending_order_time = setup_time;", SOURCE)

    def test_account_and_program_permissions_are_checked(self):
        for token in (
            "TERMINAL_TRADE_ALLOWED",
            "MQL_TRADE_ALLOWED",
            "ACCOUNT_TRADE_ALLOWED",
            "ACCOUNT_TRADE_EXPERT",
        ):
            self.assertIn(token, SOURCE)

    def test_pending_order_has_broker_side_expiration_when_supported(self):
        self.assertIn("SYMBOL_EXPIRATION_SPECIFIED", SOURCE)
        self.assertIn("ORDER_TIME_SPECIFIED", SOURCE)
        self.assertIn("ORDER_FILLING_RETURN", SOURCE)

    def test_daily_guard_counts_entries_and_includes_floating_pnl(self):
        self.assertIn("entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT", SOURCE)
        self.assertIn("CurrentEAFloatingPnL()", SOURCE)
        self.assertIn("DEAL_FEE", SOURCE)
        self.assertIn("DailyPositionStat groups[]", SOURCE)
        self.assertIn("DEAL_POSITION_ID", SOURCE)

    def test_daily_history_scan_is_cached_and_invalidated_by_deals(self):
        stats_body = function_body("UpdateDailyStats")
        transaction_body = function_body("OnTradeTransaction")
        self.assertIn("m_daily_stats_dirty", stats_body)
        self.assertIn("m_daily_cache_day == midnight_today", stats_body)
        self.assertIn("m_daily_stats_dirty = false", stats_body)
        self.assertIn("TRADE_TRANSACTION_DEAL_ADD", transaction_body)
        self.assertIn("m_daily_stats_dirty = true", transaction_body)

    def test_closed_today_group_uses_full_lifecycle_without_polluting_daily_pnl(self):
        """An overnight entry fee affects the closed trade, not today's equity PnL."""
        stats_body = function_body("UpdateDailyStats")

        # The day accumulator remains strictly scoped to deals selected since
        # broker midnight.
        self.assertIn("HistorySelect(midnight_today", stats_body)
        self.assertIn("daily_pnl += net_pnl", stats_body)

        # Closed-position classification performs a second lookup over the
        # position's complete lifecycle, including its pre-midnight entry.
        lifecycle_index = stats_body.find("HistorySelectByPosition(")
        self.assertGreater(lifecycle_index, stats_body.find("daily_pnl += net_pnl"))
        lifecycle_body = stats_body[lifecycle_index:]
        for field in (
            "DEAL_PROFIT",
            "DEAL_COMMISSION",
            "DEAL_SWAP",
            "DEAL_FEE",
        ):
            self.assertIn(field, lifecycle_body)
        self.assertIn("DEAL_MAGIC", lifecycle_body)
        self.assertIn("DEAL_SYMBOL", lifecycle_body)
        self.assertIn("groups[g].pnl = complete_position_pnl", lifecycle_body)
        self.assertIn("!groups[g].has_exit", stats_body[:lifecycle_index])
        # Full-lifecycle commission is used only for classification; after the
        # wider lookup begins, today's equity accumulator is never touched.
        self.assertNotIn("daily_pnl +=", lifecycle_body)

    def test_emergency_close_uses_separate_market_filling_policy(self):
        self.assertIn("CTrade      m_safety_trade;", SOURCE)
        self.assertIn("m_safety_trade.SetTypeFillingBySymbol(_Symbol)", SOURCE)
        self.assertIn("m_safety_trade.PositionClose(active_pos)", SOURCE)
        self.assertNotIn("m_trade.PositionClose(active_pos)", SOURCE)

    def test_v2_advanced_modules_are_opt_in(self):
        for declaration in (
            "InpUseRSIQualityFilter = false",
            "InpUseMTFTrendFilter   = false",
            "InpUseVolatilityRegime = false",
            "InpUseBreakEven",
            "InpUseFibTrailingStop",
        ):
            self.assertIn(declaration, SOURCE)
        self.assertRegex(SOURCE, r"InpUseBreakEven\s*=\s*false")
        self.assertRegex(SOURCE, r"InpUseFibTrailingStop\s*=\s*false")

    def test_advanced_indicator_handles_are_created_once_and_released(self):
        init_body = function_body("OnInit")
        deinit_body = function_body("ReleaseAllHandles") if "ReleaseAllHandles" in SOURCE else function_body("OnDeinit")
        creations = {
            "m_mtf_ema_handle": "iMA(",
            "m_mtf_rsi_handle": "iRSI(",
            "m_vol_fast_atr_handle": "iATR(",
            "m_vol_slow_atr_handle": "iATR(",
        }
        for handle, constructor in creations.items():
            self.assertIn(f"{handle} = {constructor}", init_body)
            self.assertIn(f"IndicatorRelease({handle})", deinit_body)
            # A handle must not be constructed in either tick or filter code.
            self.assertEqual(SOURCE.count(f"{handle} = {constructor}"), 1)

    def test_filters_use_only_closed_indicator_values_and_fail_closed(self):
        mtf_body = function_body("CheckMTFTrendFilter")
        vol_body = function_body("CheckVolatilityRegimeFilter")
        self.assertIn("iClose(_Symbol, InpMTFTimeframe, 1)", mtf_body)
        self.assertIn("CopyBuffer(m_mtf_ema_handle, 0, 1, 1", mtf_body)
        self.assertIn("CopyBuffer(m_mtf_rsi_handle, 0, 1, 1", mtf_body)
        self.assertIn("CopyBuffer(m_vol_fast_atr_handle, 0, 1, 1", vol_body)
        self.assertIn("CopyBuffer(m_vol_slow_atr_handle, 0, 1, 1", vol_body)
        self.assertIn("EMPTY_VALUE", mtf_body)
        self.assertIn("EMPTY_VALUE", vol_body)

    def test_closed_rsi_pair_is_copied_once_with_correct_buffer_order(self):
        body = function_body("GetClosedRSIPair")
        self.assertIn("CopyBuffer(m_rsi_handle, 0, 1, 2, values)", body)
        self.assertIn("rsi_2 = values[0]", body)
        self.assertIn("rsi_1 = values[1]", body)
        idle_body = function_body("ProcessStateIdle")
        self.assertIn("GetClosedRSIPair(rsi_1, rsi_2)", idle_body)
        self.assertNotIn("GetRSI(1", idle_body)

    def test_trade_transaction_handler_only_marks_sync_dirty(self):
        body = function_body("OnTradeTransaction")
        self.assertRegex(body, r"m_(?:sync_required|broker_dirty)\s*=\s*true;")
        for forbidden in (
            "SyncState(",
            "MaybeSyncState(",
            "PositionsTotal(",
            "OrdersTotal(",
            "HistorySelect(",
            "m_trade.",
            "m_safety_trade.",
        ):
            self.assertNotIn(forbidden, body)

    def test_state_sync_is_throttled_and_has_an_explicit_fault_state(self):
        self.assertIn("STATE_FAULT", SOURCE)
        self.assertRegex(SOURCE, r"\bm_(?:sync_required|broker_dirty)\b")
        sync_name = ("MaybeSyncState" if re.search(
            r"\b(?:void|bool)\s+MaybeSyncState\s*\(", SOURCE)
                     else "ServiceBrokerState")
        sync_body = function_body(sync_name)
        self.assertIn("SyncState();", sync_body)
        self.assertRegex(sync_body, r"1000|WATCHDOG|InpStateWatchdogMs")

    def test_position_protection_precedes_ambiguous_snapshot_faults(self):
        sync_body = function_body("SyncState")
        protection_call = sync_body.index("PreflightManagedPositionProtection()")
        ambiguity_guard = sync_body.index("snapshot.managed_positions > 1")
        self.assertLess(protection_call, ambiguity_guard)
        preflight_body = function_body("PreflightManagedPositionProtection")
        self.assertIn("ValidatePositionProtection(ticket)", preflight_body)
        self.assertIn("ServiceUnprotectedPosition(ticket)", preflight_body)

    def test_restart_geometry_uses_entry_and_tp_not_mutable_sl(self):
        body = function_body("RestoreSetupGeometry")
        self.assertIn("InpTargetRatio - InpEntryRatio", body)
        self.assertIn("target - entry", body)
        self.assertIn("entry - target", body)
        self.assertNotIn("(entry - stop) / ratio_distance", body)
        self.assertNotIn("(stop - entry) / ratio_distance", body)

    def test_position_restart_prefers_original_limit_price_from_history(self):
        body = function_body("FindOriginalLimitGeometry")
        self.assertIn("DEAL_POSITION_ID", body)
        self.assertIn("DEAL_ORDER", body)
        self.assertIn("HistoryOrderGetDouble(order_ticket, ORDER_PRICE_OPEN)", body)
        self.assertIn("HistoryOrderGetDouble(order_ticket, ORDER_SL)", body)
        self.assertIn("HistoryOrderGetDouble(order_ticket, ORDER_TP)", body)
        sync_body = function_body("SyncState")
        self.assertIn("POSITION_IDENTIFIER", sync_body)
        self.assertIn("FindOriginalLimitGeometry", sync_body)

    def test_widened_live_stop_uses_unprotected_position_guard(self):
        sync_body = function_body("SyncState")
        self.assertIn("if (!stop_protective)", sync_body)
        self.assertIn("ServiceUnprotectedPosition(snapshot.position_ticket)", sync_body)

    def test_restore_failure_routes_widened_stop_to_emergency_guard(self):
        """Unrestorable risk must not be downgraded to a passive STATE_FAULT."""
        sync_body = function_body("SyncState")
        failure_body = block_after_token(
            sync_body,
            "if (!RestoreSetupGeometry(dir, geometry_entry, stop, target, setup_time))")
        self.assertIn(
            "ServiceUnprotectedPosition(snapshot.position_ticket)", failure_body)
        self.assertNotIn("EnterFault(", failure_body)

    def test_break_even_modification_uses_safety_trade_and_retcode(self):
        body = function_body("CheckAndApplyBreakEven")
        self.assertIn("m_safety_trade.PositionModify", body)
        self.assertIn("m_safety_trade.ResultRetcode()", body)
        self.assertIn("SYMBOL_TRADE_STOPS_LEVEL", body)
        self.assertIn("SYMBOL_TRADE_FREEZE_LEVEL", body)
        self.assertNotIn("m_trade.PositionModify", body)

    def test_on_tester_uses_bounded_risk_adjusted_statistics(self):
        body = function_body("OnTester")
        for statistic in (
            "STAT_TRADES",
            "STAT_PROFIT",
            "STAT_PROFIT_FACTOR",
            "STAT_SHARPE_RATIO",
            "STAT_EQUITY_DDREL_PERCENT",
        ):
            self.assertIn(f"TesterStatistics({statistic})", body)
        self.assertIn("InpTesterMinTrades", body)
        self.assertIn("InpTesterTargetTrades", body)
        self.assertRegex(body, r"InpTesterMax(?:DDPct|DrawdownPct)")
        self.assertRegex(body, r"InpTester(?:PFCap|ProfitFactorCap)")
        self.assertIn("InpTesterSharpeCap", body)
        self.assertNotIn("profit_factor <= 1.0", body)
        self.assertNotIn("drawdown >=", body)


if __name__ == "__main__":
    unittest.main()
