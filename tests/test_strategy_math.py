#!/usr/bin/env python3
"""
Unit tests for RSI Fibonacci Retracement Strategy Math and Rules.
Pure Python, standard library unittest only (no external dependencies).
"""

import unittest
import math


def is_finite_number(value):
    try:
        return math.isfinite(value)
    except (TypeError, ValueError):
        return False


def validate_inputs(entry_ratio, stop_ratio, target_ratio, visual_target_ratio,
                    oversold, overbought, min_impulse, max_anchor, max_pending, risk_pct):
    """
    Validates input parameters according to EA safety rules.
    Returns (is_valid, error_message).
    """
    if oversold >= overbought:
        return False, "Oversold level must be strictly less than Overbought level"
    if oversold <= 0 or overbought >= 100:
        return False, "RSI levels must be within (0, 100)"
    if entry_ratio >= 0.0:
        return False, "EntryRatio must be strictly negative (< 0.0)"
    if stop_ratio >= entry_ratio:
        return False, "StopRatio must be strictly less than EntryRatio (< EntryRatio)"
    if target_ratio < 1.0:
        return False, "TargetRatio must be greater than or equal to 1.0"
    if visual_target_ratio < target_ratio:
        return False, "VisualTargetRatio must be >= TargetRatio"
    if min_impulse < 1:
        return False, "MinImpulseBars must be >= 1"
    if max_anchor < min_impulse:
        return False, "AnchorWaitBars must be >= MinImpulseBars"
    if max_pending < 1:
        return False, "PendingOrderBars must be >= 1"
    if risk_pct <= 0.0 or risk_pct > 10.0:
        return False, "RiskPercent must be between 0 and 10%"
    return True, "OK"


def calculate_fib_levels(p0, p1, entry_ratio, stop_ratio, target_ratio, visual_target_ratio, is_buy):
    """
    Calculates Fibonacci expansion/retracement levels.
    Returns dict of levels or raises ValueError if invalid range.
    """
    if is_buy:
        range_r = p1 - p0
        if range_r <= 0:
            raise ValueError("Buy setup requires P1 > P0")
        entry = p0 + entry_ratio * range_r
        stop = p0 + stop_ratio * range_r
        target = p0 + target_ratio * range_r
        visual_target = p0 + visual_target_ratio * range_r
    else:
        range_r = p0 - p1
        if range_r <= 0:
            raise ValueError("Sell setup requires P0 > P1")
        entry = p0 - entry_ratio * range_r
        stop = p0 - stop_ratio * range_r
        target = p0 - target_ratio * range_r
        visual_target = p0 - visual_target_ratio * range_r

    return {
        "P0": p0,
        "P1": p1,
        "Range": range_r,
        "Entry": entry,
        "Stop": stop,
        "Target": target,
        "VisualTarget": visual_target
    }


def calculate_volume(equity, risk_pct, loss_per_lot, step_vol, min_vol, max_vol):
    """
    Calculates position volume rounded DOWN to step_vol to ensure risk is not exceeded.
    Returns 0.0 if volume is below min_vol or calculation invalid.
    """
    if equity <= 0 or risk_pct <= 0 or loss_per_lot <= 0:
        return 0.0
    risk_amount = equity * (risk_pct / 100.0)
    raw_vol = risk_amount / loss_per_lot
    if raw_vol < min_vol:
        return 0.0
    
    # Floor to nearest step_vol
    steps = math.floor(raw_vol / step_vol)
    vol = round(steps * step_vol, 8)
    
    if vol < min_vol:
        return 0.0
    if vol > max_vol:
        vol = max_vol
    return vol


def is_order_placement_allowed(entry, ask, bid, is_buy):
    """
    Checks if a Limit order can be placed:
    - Buy Limit requires Entry < Ask.
    - Sell Limit requires Entry > Bid.
    """
    if is_buy:
        return entry < ask
    else:
        return entry > bid


def is_setup_invalidated_by_price(ask, bid, high, low, entry, stop, is_buy):
    """
    Checks if price has touched/breached Stop or already passed Entry before order placement.
    """
    if is_buy:
        # If low/ask reached or fell below Stop, setup is dead.
        if ask <= stop or low <= stop:
            return True, "Price touched or fell below Stop Loss level"
    else:
        # If high/bid reached or rose above Stop, setup is dead.
        if bid >= stop or high >= stop:
            return True, "Price touched or rose above Stop Loss level"
    return False, "OK"


def restore_geometry(entry, stop, entry_ratio, stop_ratio, is_buy):
    """Reconstructs P0/P1 after a terminal restart from broker order prices."""
    ratio_distance = entry_ratio - stop_ratio
    if ratio_distance <= 0:
        raise ValueError("Invalid ratio distance")
    range_r = ((entry - stop) if is_buy else (stop - entry)) / ratio_distance
    if range_r <= 0:
        raise ValueError("Invalid restored range")
    if is_buy:
        p0 = entry - entry_ratio * range_r
        p1 = p0 + range_r
    else:
        p0 = entry + entry_ratio * range_r
        p1 = p0 - range_r
    return p0, p1, range_r


def spread_risk_percent(ask, bid, entry, stop):
    risk_distance = abs(entry - stop)
    if ask <= 0 or bid <= 0 or ask < bid or risk_distance <= 0:
        raise ValueError("Invalid prices")
    return 100.0 * (ask - bid) / risk_distance


def passes_rsi_quality(rsi_by_shift, is_buy, min_bars, min_exit_delta,
                       oversold=30.0, overbought=70.0):
    """Pure version of the closed-bar RSI excursion-quality filter."""
    if min_bars < 1 or min_exit_delta < 0.0:
        return False

    required_shifts = range(1, 2 + min_bars)
    if any(shift not in rsi_by_shift for shift in required_shifts):
        return False

    values = [rsi_by_shift[shift] for shift in required_shifts]
    if any(not is_finite_number(value) or value < 0.0 or value > 100.0
           for value in values):
        return False

    rsi_1 = rsi_by_shift[1]
    rsi_2 = rsi_by_shift[2]
    if is_buy:
        if rsi_1 - rsi_2 < min_exit_delta:
            return False
        return all(rsi_by_shift[shift] <= oversold
                   for shift in range(2, 2 + min_bars))

    if rsi_2 - rsi_1 < min_exit_delta:
        return False
    return all(rsi_by_shift[shift] >= overbought
               for shift in range(2, 2 + min_bars))


def passes_mtf_trend(close_htf, ema_htf, is_buy, use_rsi=False,
                     rsi_htf=None, rsi_midline=50.0):
    """Checks the strict trend relation on the last closed HTF candle."""
    if (not is_finite_number(close_htf) or not is_finite_number(ema_htf) or
            close_htf <= 0.0 or ema_htf <= 0.0):
        return False

    trend_ok = close_htf > ema_htf if is_buy else close_htf < ema_htf
    if not trend_ok:
        return False
    if not use_rsi:
        return True
    if (rsi_htf is None or not is_finite_number(rsi_htf) or
            rsi_htf < 0.0 or rsi_htf > 100.0):
        return False
    return rsi_htf > rsi_midline if is_buy else rsi_htf < rsi_midline


def passes_volatility_regime(fast_atr, slow_atr, min_ratio, max_ratio):
    """Returns True only for a finite, positive and inclusively bounded ratio."""
    if (not is_finite_number(fast_atr) or not is_finite_number(slow_atr) or
            fast_atr <= 0.0 or slow_atr <= 0.0 or
            not is_finite_number(min_ratio) or not is_finite_number(max_ratio) or
            min_ratio <= 0.0 or min_ratio > max_ratio):
        return False
    ratio = fast_atr / slow_atr
    return is_finite_number(ratio) and min_ratio <= ratio <= max_ratio


def restore_geometry_from_target(entry, target, entry_ratio, stop_ratio,
                                 target_ratio, is_buy):
    """Restores Fib geometry from entry+TP, independent of a modified broker SL."""
    ratio_distance = target_ratio - entry_ratio
    if ratio_distance <= 0.0:
        raise ValueError("Invalid target-to-entry ratio distance")
    range_r = ((target - entry) if is_buy else (entry - target)) / ratio_distance
    if not is_finite_number(range_r) or range_r <= 0.0:
        raise ValueError("Invalid restored range")

    if is_buy:
        p0 = entry - entry_ratio * range_r
        p1 = p0 + range_r
        original_stop = p0 + stop_ratio * range_r
    else:
        p0 = entry + entry_ratio * range_r
        p1 = p0 - range_r
        original_stop = p0 - stop_ratio * range_r
    return p0, p1, range_r, original_stop


def break_even_levels(p0, range_r, entry, trigger_ratio, offset_ticks,
                      tick_size, is_buy):
    """Calculates Fib trigger and directionally tick-aligned break-even SL."""
    if (not all(is_finite_number(value) for value in
                (p0, range_r, entry, trigger_ratio, tick_size)) or
            range_r <= 0.0 or tick_size <= 0.0 or offset_ticks < 0):
        raise ValueError("Invalid break-even inputs")

    if is_buy:
        trigger = p0 + trigger_ratio * range_r
        raw_sl = entry + offset_ticks * tick_size
        aligned_sl = math.floor((raw_sl / tick_size) + 1e-12) * tick_size
    else:
        trigger = p0 - trigger_ratio * range_r
        raw_sl = entry - offset_ticks * tick_size
        aligned_sl = math.ceil((raw_sl / tick_size) - 1e-12) * tick_size
    return trigger, aligned_sl


def tester_score(trades, net_profit, profit_factor, sharpe, equity_dd_pct,
                 min_trades=40, target_trades=120, max_dd_pct=30.0, pf_cap=5.0,
                 sharpe_cap=5.0):
    """Pure equivalent of the bounded V2 OnTester optimization criterion."""
    stats = (trades, net_profit, profit_factor, sharpe, equity_dd_pct,
             min_trades, target_trades, max_dd_pct, pf_cap, sharpe_cap)
    if any(not is_finite_number(value) for value in stats):
        return -1.0
    if (min_trades <= 0 or target_trades < min_trades or max_dd_pct <= 0.0 or pf_cap <= 0.0 or
            sharpe_cap <= 0.0 or trades < min_trades or net_profit <= 0.0 or
            profit_factor < 0.0 or sharpe <= 0.0 or equity_dd_pct < 0.0 or
            equity_dd_pct > max_dd_pct):
        return -1.0

    bounded_pf = min(max(profit_factor, 0.0), pf_cap)
    bounded_sharpe = min(max(sharpe, 0.0), sharpe_cap)
    trade_weight = min(1.0, math.sqrt(trades / target_trades))
    dd_weight = (1.0 - equity_dd_pct / max_dd_pct) ** 2
    return bounded_sharpe * math.sqrt(bounded_pf) * trade_weight * dd_weight


def aggregate_daily_position_fixture(deals, midnight):
    """Reference accounting for day PnL versus full closed-position PnL."""
    daily_pnl = 0.0
    entries_today = set()
    closed_today = set()
    complete_by_position = {}

    for deal in deals:
        net = sum(deal.get(field, 0.0) for field in
                  ("profit", "commission", "swap", "fee"))
        position_id = deal["position_id"]
        complete_by_position[position_id] = (
            complete_by_position.get(position_id, 0.0) + net)

        if deal["time"] < midnight:
            continue
        daily_pnl += net
        if deal["entry"] in ("IN", "INOUT"):
            entries_today.add(position_id)
        if deal["entry"] in ("OUT", "OUT_BY", "INOUT"):
            closed_today.add(position_id)

    closed_group_pnl = {
        position_id: complete_by_position[position_id]
        for position_id in closed_today
    }
    return daily_pnl, len(entries_today), closed_group_pnl


class TestStrategyMathBuy(unittest.TestCase):
    def setUp(self):
        self.p0 = 100.0
        self.p1 = 110.0
        self.entry_ratio = -0.21
        self.stop_ratio = -0.29
        self.target_ratio = 2.56
        self.visual_target_ratio = 2.64

    def test_buy_level_values(self):
        levels = calculate_fib_levels(
            self.p0, self.p1,
            self.entry_ratio, self.stop_ratio,
            self.target_ratio, self.visual_target_ratio,
            is_buy=True
        )
        self.assertAlmostEqual(levels["Range"], 10.0)
        self.assertAlmostEqual(levels["Entry"], 97.90)
        self.assertAlmostEqual(levels["Stop"], 97.10)
        self.assertAlmostEqual(levels["Target"], 125.60)
        self.assertAlmostEqual(levels["VisualTarget"], 126.40)

    def test_buy_relative_ordering(self):
        levels = calculate_fib_levels(
            self.p0, self.p1,
            self.entry_ratio, self.stop_ratio,
            self.target_ratio, self.visual_target_ratio,
            is_buy=True
        )
        # For BUY: Stop < Entry < P0 < P1 < Target < VisualTarget
        self.assertLess(levels["Stop"], levels["Entry"])
        self.assertLess(levels["Entry"], levels["P0"])
        self.assertLess(levels["P0"], levels["P1"])
        self.assertLess(levels["P1"], levels["Target"])
        self.assertLess(levels["Target"], levels["VisualTarget"])

    def test_buy_risk_reward_ratios(self):
        levels = calculate_fib_levels(
            self.p0, self.p1,
            self.entry_ratio, self.stop_ratio,
            self.target_ratio, self.visual_target_ratio,
            is_buy=True
        )
        risk = levels["Entry"] - levels["Stop"]
        reward = levels["Target"] - levels["Entry"]
        self.assertAlmostEqual(risk, 0.80)   # ( -0.21 - (-0.29) ) * 10 = 0.08 * 10 = 0.80
        self.assertAlmostEqual(reward, 27.70) # ( 2.56 - (-0.21) ) * 10 = 2.77 * 10 = 27.70
        rr_ratio = reward / risk
        self.assertAlmostEqual(rr_ratio, 34.625)


class TestStrategyMathSell(unittest.TestCase):
    def setUp(self):
        self.p0 = 100.0
        self.p1 = 90.0
        self.entry_ratio = -0.21
        self.stop_ratio = -0.29
        self.target_ratio = 2.56
        self.visual_target_ratio = 2.64

    def test_sell_level_values(self):
        levels = calculate_fib_levels(
            self.p0, self.p1,
            self.entry_ratio, self.stop_ratio,
            self.target_ratio, self.visual_target_ratio,
            is_buy=False
        )
        self.assertAlmostEqual(levels["Range"], 10.0)
        self.assertAlmostEqual(levels["Entry"], 102.10)
        self.assertAlmostEqual(levels["Stop"], 102.90)
        self.assertAlmostEqual(levels["Target"], 74.40)
        self.assertAlmostEqual(levels["VisualTarget"], 73.60)

    def test_sell_relative_ordering(self):
        levels = calculate_fib_levels(
            self.p0, self.p1,
            self.entry_ratio, self.stop_ratio,
            self.target_ratio, self.visual_target_ratio,
            is_buy=False
        )
        # For SELL: VisualTarget < Target < P1 < P0 < Entry < Stop
        self.assertLess(levels["VisualTarget"], levels["Target"])
        self.assertLess(levels["Target"], levels["P1"])
        self.assertLess(levels["P1"], levels["P0"])
        self.assertLess(levels["P0"], levels["Entry"])
        self.assertLess(levels["Entry"], levels["Stop"])

    def test_sell_risk_reward_ratios(self):
        levels = calculate_fib_levels(
            self.p0, self.p1,
            self.entry_ratio, self.stop_ratio,
            self.target_ratio, self.visual_target_ratio,
            is_buy=False
        )
        risk = levels["Stop"] - levels["Entry"]
        reward = levels["Entry"] - levels["Target"]
        self.assertAlmostEqual(risk, 0.80)
        self.assertAlmostEqual(reward, 27.70)
        rr_ratio = reward / risk
        self.assertAlmostEqual(rr_ratio, 34.625)


class TestInputValidation(unittest.TestCase):
    def test_valid_inputs(self):
        ok, msg = validate_inputs(-0.21, -0.29, 2.56, 2.64, 30.0, 70.0, 1, 8, 8, 0.25)
        self.assertTrue(ok)
        self.assertEqual(msg, "OK")

    def test_invalid_rsi_levels(self):
        ok, _ = validate_inputs(-0.21, -0.29, 2.56, 2.64, 70.0, 30.0, 1, 8, 8, 0.25)
        self.assertFalse(ok)

    def test_positive_entry_ratio(self):
        ok, _ = validate_inputs(0.10, -0.29, 2.56, 2.64, 30.0, 70.0, 1, 8, 8, 0.25)
        self.assertFalse(ok)

    def test_stop_ratio_above_entry_ratio(self):
        ok, _ = validate_inputs(-0.21, -0.15, 2.56, 2.64, 30.0, 70.0, 1, 8, 8, 0.25)
        self.assertFalse(ok)

    def test_target_ratio_too_low(self):
        ok, _ = validate_inputs(-0.21, -0.29, 0.80, 2.64, 30.0, 70.0, 1, 8, 8, 0.25)
        self.assertFalse(ok)


class TestEdgeCasesAndRisk(unittest.TestCase):
    def test_zero_or_negative_range(self):
        with self.assertRaises(ValueError):
            calculate_fib_levels(100.0, 100.0, -0.21, -0.29, 2.56, 2.64, is_buy=True)
        with self.assertRaises(ValueError):
            calculate_fib_levels(100.0, 90.0, -0.21, -0.29, 2.56, 2.64, is_buy=True)
        with self.assertRaises(ValueError):
            calculate_fib_levels(100.0, 110.0, -0.21, -0.29, 2.56, 2.64, is_buy=False)

    def test_volume_calculation_rounding_down(self):
        # Equity: 10,000 EUR, Risk: 0.25% => 25 EUR risk amount.
        # Loss per 1.0 lot: 1000 EUR.
        # Raw volume = 25 / 1000 = 0.025 lots.
        # Step: 0.01 lot => Rounded down to 0.02 lots.
        vol = calculate_volume(
            equity=10000.0, risk_pct=0.25, loss_per_lot=1000.0,
            step_vol=0.01, min_vol=0.01, max_vol=100.0
        )
        self.assertEqual(vol, 0.02)
        # Check actual monetary risk with 0.02 lots is <= 25 EUR.
        actual_risk = 0.02 * 1000.0
        self.assertLessEqual(actual_risk, 25.0)

    def test_volume_below_min_vol(self):
        # Equity: 1,000 EUR, Risk: 0.25% => 2.5 EUR risk amount.
        # Loss per 1.0 lot: 1000 EUR.
        # Raw volume = 0.0025 lots. Min vol: 0.01.
        # Expected: 0.0 (trade refused).
        vol = calculate_volume(
            equity=1000.0, risk_pct=0.25, loss_per_lot=1000.0,
            step_vol=0.01, min_vol=0.01, max_vol=100.0
        )
        self.assertEqual(vol, 0.0)

    def test_fractional_volume_step_never_rounds_up(self):
        vol = calculate_volume(
            equity=9000.0, risk_pct=0.10, loss_per_lot=1000.0,
            step_vol=0.001, min_vol=0.001, max_vol=100.0
        )
        self.assertEqual(vol, 0.009)
        self.assertLessEqual(vol * 1000.0, 9.0)

    def test_restore_buy_geometry(self):
        p0, p1, range_r = restore_geometry(97.9, 97.1, -0.21, -0.29, True)
        self.assertAlmostEqual(p0, 100.0)
        self.assertAlmostEqual(p1, 110.0)
        self.assertAlmostEqual(range_r, 10.0)

    def test_restore_sell_geometry(self):
        p0, p1, range_r = restore_geometry(102.1, 102.9, -0.21, -0.29, False)
        self.assertAlmostEqual(p0, 100.0)
        self.assertAlmostEqual(p1, 90.0)
        self.assertAlmostEqual(range_r, 10.0)

    def test_spread_relative_to_tight_stop(self):
        pct = spread_risk_percent(100.02, 100.00, 97.90, 97.10)
        self.assertAlmostEqual(pct, 2.5)
        self.assertLessEqual(pct, 25.0)

    def test_spread_guard_rejects_invalid_prices(self):
        with self.assertRaises(ValueError):
            spread_risk_percent(99.0, 100.0, 97.9, 97.1)

    def test_order_placement_allowed_buy(self):
        entry = 97.90
        # Buy limit allowed if Entry < Ask
        self.assertTrue(is_order_placement_allowed(entry, ask=99.00, bid=98.98, is_buy=True))
        # Buy limit rejected if Entry >= Ask
        self.assertFalse(is_order_placement_allowed(entry, ask=97.50, bid=97.48, is_buy=True))

    def test_order_placement_allowed_sell(self):
        entry = 102.10
        # Sell limit allowed if Entry > Bid
        self.assertTrue(is_order_placement_allowed(entry, ask=100.02, bid=100.00, is_buy=False))
        # Sell limit rejected if Entry <= Bid
        self.assertFalse(is_order_placement_allowed(entry, ask=103.02, bid=103.00, is_buy=False))

    def test_invalidation_checks(self):
        # Buy setup: Entry 97.90, Stop 97.10
        invalid, msg = is_setup_invalidated_by_price(ask=97.00, bid=96.98, high=99.0, low=97.0, entry=97.90, stop=97.10, is_buy=True)
        self.assertTrue(invalid)

        # Sell setup: Entry 102.10, Stop 102.90
        invalid, msg = is_setup_invalidated_by_price(ask=103.00, bid=103.00, high=103.10, low=101.0, entry=102.10, stop=102.90, is_buy=False)
        self.assertTrue(invalid)


class TestAdvancedSignalFilters(unittest.TestCase):
    def test_buy_rsi_quality_accepts_exact_boundaries(self):
        rsi = {1: 34.0, 2: 30.0, 3: 29.0}
        self.assertTrue(passes_rsi_quality(rsi, True, 2, 4.0))

    def test_buy_rsi_quality_rejects_weak_exit_and_short_excursion(self):
        self.assertFalse(passes_rsi_quality(
            {1: 33.9, 2: 30.0, 3: 29.0}, True, 2, 4.0))
        self.assertFalse(passes_rsi_quality(
            {1: 34.0, 2: 30.0, 3: 30.1}, True, 2, 4.0))

    def test_sell_rsi_quality_accepts_exact_boundaries(self):
        rsi = {1: 66.0, 2: 70.0, 3: 71.0}
        self.assertTrue(passes_rsi_quality(rsi, False, 2, 4.0))

    def test_sell_rsi_quality_rejects_weak_exit_and_short_excursion(self):
        self.assertFalse(passes_rsi_quality(
            {1: 66.1, 2: 70.0, 3: 71.0}, False, 2, 4.0))
        self.assertFalse(passes_rsi_quality(
            {1: 66.0, 2: 70.0, 3: 69.9}, False, 2, 4.0))

    def test_rsi_quality_fails_closed_on_missing_or_non_finite_data(self):
        self.assertFalse(passes_rsi_quality(
            {1: 34.0, 2: 30.0}, True, 2, 4.0))
        self.assertFalse(passes_rsi_quality(
            {1: 34.0, 2: math.nan, 3: 29.0}, True, 2, 4.0))
        self.assertFalse(passes_rsi_quality(
            {1: 34.0, 2: 30.0, 3: None}, True, 2, 4.0))

    def test_mtf_trend_is_strict_in_both_directions(self):
        self.assertTrue(passes_mtf_trend(101.0, 100.0, True))
        self.assertTrue(passes_mtf_trend(99.0, 100.0, False))
        self.assertFalse(passes_mtf_trend(100.0, 100.0, True))
        self.assertFalse(passes_mtf_trend(100.0, 100.0, False))

    def test_mtf_rsi_confirmation_is_strict_and_fails_closed(self):
        self.assertTrue(passes_mtf_trend(
            101.0, 100.0, True, use_rsi=True, rsi_htf=50.1))
        self.assertTrue(passes_mtf_trend(
            99.0, 100.0, False, use_rsi=True, rsi_htf=49.9))
        self.assertFalse(passes_mtf_trend(
            101.0, 100.0, True, use_rsi=True, rsi_htf=50.0))
        self.assertFalse(passes_mtf_trend(
            99.0, 100.0, False, use_rsi=True, rsi_htf=None))
        self.assertFalse(passes_mtf_trend(None, 100.0, True))

    def test_volatility_regime_accepts_inclusive_boundaries(self):
        self.assertTrue(passes_volatility_regime(0.8, 1.0, 0.8, 2.2))
        self.assertTrue(passes_volatility_regime(2.2, 1.0, 0.8, 2.2))

    def test_volatility_regime_rejects_outside_and_invalid_values(self):
        self.assertFalse(passes_volatility_regime(0.799, 1.0, 0.8, 2.2))
        self.assertFalse(passes_volatility_regime(2.201, 1.0, 0.8, 2.2))
        self.assertFalse(passes_volatility_regime(1.0, 0.0, 0.8, 2.2))
        self.assertFalse(passes_volatility_regime(math.inf, 1.0, 0.8, 2.2))
        self.assertFalse(passes_volatility_regime(None, 1.0, 0.8, 2.2))


class TestBreakEvenAndRestartGeometry(unittest.TestCase):
    def test_buy_restart_uses_entry_and_target_after_break_even(self):
        p0, p1, range_r, original_stop = restore_geometry_from_target(
            97.9, 125.6, -0.21, -0.29, 2.56, True)
        self.assertAlmostEqual(p0, 100.0)
        self.assertAlmostEqual(p1, 110.0)
        self.assertAlmostEqual(range_r, 10.0)
        self.assertAlmostEqual(original_stop, 97.1)
        # A broker SL moved to 97.91 is deliberately absent from reconstruction.

    def test_sell_restart_uses_entry_and_target_after_break_even(self):
        p0, p1, range_r, original_stop = restore_geometry_from_target(
            102.1, 74.4, -0.21, -0.29, 2.56, False)
        self.assertAlmostEqual(p0, 100.0)
        self.assertAlmostEqual(p1, 90.0)
        self.assertAlmostEqual(range_r, 10.0)
        self.assertAlmostEqual(original_stop, 102.9)

    def test_buy_break_even_fib_trigger_and_tick_offset(self):
        trigger, new_sl = break_even_levels(
            100.0, 10.0, 97.9, 1.0, 1, 0.01, True)
        self.assertAlmostEqual(trigger, 110.0)
        self.assertAlmostEqual(new_sl, 97.91)

    def test_sell_break_even_fib_trigger_and_tick_offset(self):
        trigger, new_sl = break_even_levels(
            100.0, 10.0, 102.1, 1.0, 1, 0.01, False)
        self.assertAlmostEqual(trigger, 90.0)
        self.assertAlmostEqual(new_sl, 102.09)


class TestDailyPositionAccounting(unittest.TestCase):
    def test_overnight_entry_cost_affects_closed_group_not_daily_pnl(self):
        midnight = 1_000
        deals = [
            {
                "position_id": 77,
                "time": 900,
                "entry": "IN",
                "profit": 0.0,
                "commission": -2.0,
                "swap": 0.0,
                "fee": -0.1,
            },
            {
                "position_id": 77,
                "time": 1_100,
                "entry": "OUT",
                "profit": 1.5,
                "commission": -0.2,
                "swap": 0.0,
                "fee": 0.0,
            },
        ]

        daily_pnl, daily_trades, closed_groups = (
            aggregate_daily_position_fixture(deals, midnight))

        # Today's PnL sees only today's closing deal.
        self.assertAlmostEqual(daily_pnl, 1.3)
        self.assertEqual(daily_trades, 0)
        # Loss classification sees the complete lifecycle, including the
        # previous day's entry commission and fee.
        self.assertAlmostEqual(closed_groups[77], -0.8)


class TestOnTesterScore(unittest.TestCase):
    def test_admissible_score_matches_specification(self):
        score = tester_score(40, 100.0, 4.0, 2.0, 15.0)
        # 2 Sharpe * sqrt(4 PF) * sqrt(40/120) * (1 - 15/30)^2.
        self.assertAlmostEqual(score, math.sqrt(1.0 / 3.0))

    def test_extreme_pf_and_sharpe_are_capped(self):
        capped = tester_score(120, 100.0, 50.0, 50.0, 0.0)
        expected = 5.0 * math.sqrt(5.0)
        self.assertAlmostEqual(capped, expected)

    def test_sample_weight_increases_until_target(self):
        score_40 = tester_score(40, 100.0, 2.0, 1.0, 0.0)
        score_80 = tester_score(80, 100.0, 2.0, 1.0, 0.0)
        score_120 = tester_score(120, 100.0, 2.0, 1.0, 0.0)
        score_200 = tester_score(200, 100.0, 2.0, 1.0, 0.0)
        self.assertLess(score_40, score_80)
        self.assertLess(score_80, score_120)
        self.assertAlmostEqual(score_120, score_200)

    def test_rejection_guards(self):
        self.assertEqual(tester_score(39, 100.0, 2.0, 1.0, 5.0), -1.0)
        self.assertEqual(tester_score(40, 0.0, 2.0, 1.0, 5.0), -1.0)
        self.assertEqual(tester_score(40, 100.0, 2.0, 0.0, 5.0), -1.0)
        self.assertEqual(tester_score(40, 100.0, 2.0, 1.0, 30.1), -1.0)
        self.assertEqual(tester_score(40, 100.0, math.nan, 1.0, 5.0), -1.0)

    def test_drawdown_at_cap_has_zero_score(self):
        self.assertEqual(tester_score(40, 100.0, 2.0, 1.0, 30.0), 0.0)


if __name__ == "__main__":
    unittest.main()
