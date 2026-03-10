"""Parameter optimization framework for scalping strategies.

Runs all parameter combinations for a given strategy and returns results
ranked by profit factor, then net PnL.
"""

import sys
import json
import argparse
import importlib.util
from pathlib import Path
from datetime import datetime
from itertools import product
from copy import deepcopy

import pandas as pd

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import backtest modules dynamically

import importlib.util
spec_001 = importlib.util.spec_from_file_location("backtest_001",
    Path(__file__).resolve().parents[1] / 'strategies' / '001_delta_absorption_breakout' / 'backtest.py')
s001_backtest = importlib.util.module_from_spec(spec_001)
spec_001.loader.exec_module(s001_backtest)

spec_002 = importlib.util.spec_from_file_location("backtest_002",
    Path(__file__).resolve().parents[1] / 'strategies' / '002_volume_profile_fvg' / 'backtest.py')
s002_backtest = importlib.util.module_from_spec(spec_002)
spec_002.loader.exec_module(s002_backtest)

spec_003 = importlib.util.spec_from_file_location("backtest_003",
    Path(__file__).resolve().parents[1] / 'strategies' / '003_cvd_divergence' / 'backtest.py')
s003_backtest = importlib.util.module_from_spec(spec_003)
spec_003.loader.exec_module(s003_backtest)

spec_004 = importlib.util.spec_from_file_location("backtest_004",
    Path(__file__).resolve().parents[1] / 'strategies' / '004_bid_ask_imbalance' / 'backtest.py')
s004_backtest = importlib.util.module_from_spec(spec_004)
spec_004.loader.exec_module(s004_backtest)

spec_005 = importlib.util.spec_from_file_location("backtest_005",
    Path(__file__).resolve().parents[1] / 'strategies' / '005_large_print_momentum' / 'backtest.py')
s005_backtest = importlib.util.module_from_spec(spec_005)
spec_005.loader.exec_module(s005_backtest)

spec_006 = importlib.util.spec_from_file_location("backtest_006",
    Path(__file__).resolve().parents[1] / 'strategies' / '006_tape_streak' / 'backtest.py')
s006_backtest = importlib.util.module_from_spec(spec_006)
spec_006.loader.exec_module(s006_backtest)

spec_007 = importlib.util.spec_from_file_location("backtest_007",
    Path(__file__).resolve().parents[1] / 'strategies' / '007_sweep_fade' / 'backtest.py')
s007_backtest = importlib.util.module_from_spec(spec_007)
spec_007.loader.exec_module(s007_backtest)

spec_008 = importlib.util.spec_from_file_location("backtest_008",
    Path(__file__).resolve().parents[1] / 'strategies' / '008_stacked_book_breakout' / 'backtest.py')
s008_backtest = importlib.util.module_from_spec(spec_008)
spec_008.loader.exec_module(s008_backtest)

spec_009 = importlib.util.spec_from_file_location("backtest_009",
    Path(__file__).resolve().parents[1] / 'strategies' / '009_absorption' / 'backtest.py')
s009_backtest = importlib.util.module_from_spec(spec_009)
spec_009.loader.exec_module(s009_backtest)

spec_010 = importlib.util.spec_from_file_location("backtest_010",
    Path(__file__).resolve().parents[1] / 'strategies' / '010_initiative_auction' / 'backtest.py')
s010_backtest = importlib.util.module_from_spec(spec_010)
spec_010.loader.exec_module(s010_backtest)

spec_011 = importlib.util.spec_from_file_location("backtest_011",
    Path(__file__).resolve().parents[1] / 'strategies' / '011_exhaustion_reversal' / 'backtest.py')
s011_backtest = importlib.util.module_from_spec(spec_011)
spec_011.loader.exec_module(s011_backtest)

spec_012 = importlib.util.spec_from_file_location("backtest_012",
    Path(__file__).resolve().parents[1] / 'strategies' / '012_lvn_rebalance' / 'backtest.py')
s012_backtest = importlib.util.module_from_spec(spec_012)
spec_012.loader.exec_module(s012_backtest)

spec_013 = importlib.util.spec_from_file_location("backtest_013",
    Path(__file__).resolve().parents[1] / 'strategies' / '013_value_area_rejection' / 'backtest.py')
s013_backtest = importlib.util.module_from_spec(spec_013)
spec_013.loader.exec_module(s013_backtest)

spec_014 = importlib.util.spec_from_file_location("backtest_014",
    Path(__file__).resolve().parents[1] / 'strategies' / '014_failed_auction_hook' / 'backtest.py')
s014_backtest = importlib.util.module_from_spec(spec_014)
spec_014.loader.exec_module(s014_backtest)

SESSION_VARIATIONS = {
    "var_A": {
        "name": "All sessions",
        "sessions": None,
    },
    "var_B": {
        "name": "RTH only",
        "sessions": ["NYOpen", "MidDay", "PowerHour", "Close"],
    },
    "var_C": {
        "name": "London + LondonNY",
        "sessions": ["London", "LondonNY"],
    },
    "var_D": {
        "name": "Overnight",
        "sessions": ["Asia", "London", "LondonNY", "PreNY"],
    },
}


STRATEGIES = {
    '001': {
        'name': 'Delta Absorption Breakout',
        'backtest': s001_backtest,
        'variations': {
            1: {
                'name': '4pt Range',
                'params': {
                    'delta_threshold': 100,
                    'range_window': 10,
                    'max_range_pts': 4.0,
                    'absorption_bars': 2,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': '6pt Range',
                'params': {
                    'delta_threshold': 100,
                    'range_window': 10,
                    'max_range_pts': 6.0,
                    'absorption_bars': 2,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 12,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': '8pt Range',
                'params': {
                    'delta_threshold': 100,
                    'range_window': 10,
                    'max_range_pts': 8.0,
                    'absorption_bars': 2,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': '10pt Range',
                'params': {
                    'delta_threshold': 100,
                    'range_window': 10,
                    'max_range_pts': 10.0,
                    'absorption_bars': 2,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': '6pt Scalp',
                'params': {
                    'delta_threshold': 100,
                    'range_window': 8,
                    'max_range_pts': 6.0,
                    'absorption_bars': 2,
                    'price_move_max_ticks': 4,
                    'take_profit_ticks': 4,
                    'stop_loss_ticks': 3,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '002': {
        'name': 'Volume Profile FVG',
        'backtest': s002_backtest,
        'variations': {
            1: {
                'name': 'Tight Swings',
                'params': {
                    'swing_lookback': 10,
                    'min_leg_size_ticks': 8,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'max_retrace_bars': 30,
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'swing_lookback': 10,
                    'min_leg_size_ticks': 8,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'max_retrace_bars': 30,
                }
            },
            3: {
                'name': 'Wide Swings',
                'params': {
                    'swing_lookback': 15,
                    'min_leg_size_ticks': 12,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 10,
                    'max_retrace_bars': 30,
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'swing_lookback': 8,
                    'min_leg_size_ticks': 8,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 20,
                    'stop_loss_ticks': 8,
                    'max_retrace_bars': 30,
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'swing_lookback': 10,
                    'min_leg_size_ticks': 8,
                    'value_area_pct': 0.70,
                    'entry_zone_ticks': 2,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'max_retrace_bars': 30,
                }
            },
        }
    },
    '003': {
        'name': 'CVD Divergence',
        'backtest': s003_backtest,
        'variations': {
            1: {
                'name': 'Sensitive',
                'params': {
                    'divergence_window': 3,
                    'min_cvd_move': 50,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'divergence_window': 5,
                    'min_cvd_move': 75,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Strict',
                'params': {
                    'divergence_window': 7,
                    'min_cvd_move': 100,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Momentum',
                'params': {
                    'divergence_window': 4,
                    'min_cvd_move': 60,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'divergence_window': 3,
                    'min_cvd_move': 50,
                    'confirmation_bars': 1,
                    'price_tolerance_ticks': 10,
                    'take_profit_ticks': 5,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '004': {
        'name': 'Bid/Ask Imbalance',
        'backtest': s004_backtest,
        'variations': {
            1: {
                'name': 'Tight Threshold',
                'params': {
                    'imbalance_ratio_threshold': 2.0,
                    'consecutive_bars': 2,
                    'min_size_contracts': 200,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'imbalance_ratio_threshold': 3.0,
                    'consecutive_bars': 2,
                    'min_size_contracts': 100,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Aggressive',
                'params': {
                    'imbalance_ratio_threshold': 3.5,
                    'consecutive_bars': 1,
                    'min_size_contracts': 150,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Scalp',
                'params': {
                    'imbalance_ratio_threshold': 2.5,
                    'consecutive_bars': 1,
                    'min_size_contracts': 80,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Extreme',
                'params': {
                    'imbalance_ratio_threshold': 4.0,
                    'consecutive_bars': 2,
                    'min_size_contracts': 200,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 10,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '005': {
        'name': 'Large Print Momentum',
        'backtest': s005_backtest,
        'variations': {
            1: {
                'name': 'Sensitive',
                'params': {
                    'lookback_bars': 30,
                    'std_dev_threshold': 1.5,
                    'min_trade_size': 500,
                    'signal_cooldown_bars': 3,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'lookback_bars': 50,
                    'std_dev_threshold': 2.0,
                    'min_trade_size': 1000,
                    'signal_cooldown_bars': 5,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Strict',
                'params': {
                    'lookback_bars': 80,
                    'std_dev_threshold': 2.5,
                    'min_trade_size': 1500,
                    'signal_cooldown_bars': 10,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'lookback_bars': 25,
                    'std_dev_threshold': 1.5,
                    'min_trade_size': 750,
                    'signal_cooldown_bars': 2,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'lookback_bars': 20,
                    'std_dev_threshold': 1.8,
                    'min_trade_size': 600,
                    'signal_cooldown_bars': 1,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '006': {
        'name': 'Aggressive Tape Streak',
        'backtest': s006_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'min_consecutive_trades': 3,
                    'lookback_bars': 2,
                    'min_total_volume': 0,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'min_consecutive_trades': 5,
                    'lookback_bars': 3,
                    'min_total_volume': 0,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Strict',
                'params': {
                    'min_consecutive_trades': 7,
                    'lookback_bars': 5,
                    'min_total_volume': 0,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'min_consecutive_trades': 4,
                    'lookback_bars': 2,
                    'min_total_volume': 0,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'min_consecutive_trades': 3,
                    'lookback_bars': 1,
                    'min_total_volume': 0,
                    'take_profit_ticks': 5,
                    'stop_loss_ticks': 3,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '007': {
        'name': 'Sweep & Fade',
        'backtest': s007_backtest,
        'variations': {
            1: {
                'name': 'Sensitive',
                'params': {
                    'sweep_tick_threshold': 5,
                    'sweep_time_seconds': 30,
                    'take_profit_ticks': 5,
                    'stop_loss_ticks': 8,
                    'retracement_min_ticks': 0.5,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'sweep_tick_threshold': 8,
                    'sweep_time_seconds': 30,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 10,
                    'retracement_min_ticks': 1,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Strict',
                'params': {
                    'sweep_tick_threshold': 12,
                    'sweep_time_seconds': 30,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 12,
                    'retracement_min_ticks': 2,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'sweep_tick_threshold': 6,
                    'sweep_time_seconds': 30,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 10,
                    'retracement_min_ticks': 0.5,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'sweep_tick_threshold': 4,
                    'sweep_time_seconds': 30,
                    'take_profit_ticks': 3,
                    'stop_loss_ticks': 5,
                    'retracement_min_ticks': 0.25,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '008': {
        'name': 'Stacked Book Breakout',
        'backtest': s008_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'stack_threshold': 2.0,
                    'stack_lookback_bars': 5,
                    'breakout_min_ticks': 1,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'stack_threshold': 3.0,
                    'stack_lookback_bars': 10,
                    'breakout_min_ticks': 1,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Strict',
                'params': {
                    'stack_threshold': 4.0,
                    'stack_lookback_bars': 15,
                    'breakout_min_ticks': 2,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'stack_threshold': 2.5,
                    'stack_lookback_bars': 8,
                    'breakout_min_ticks': 1,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'stack_threshold': 2.0,
                    'stack_lookback_bars': 5,
                    'breakout_min_ticks': 0.5,
                    'entry_offset_ticks': 1,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '009': {
        'name': 'Absorption',
        'backtest': s009_backtest,
        'variations': {
            1: {
                'name': 'Default',
                'params': {
                    'delta_threshold': 250,
                    'close_move_required_ticks': 1,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '010': {
        'name': 'Initiative Auction',
        'backtest': s010_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'delta_threshold': 250,
                    'volume_avg_period': 20,
                    'volume_multiplier': 1.8,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'delta_threshold': 300,
                    'volume_avg_period': 20,
                    'volume_multiplier': 1.5,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Wide',
                'params': {
                    'delta_threshold': 350,
                    'volume_avg_period': 20,
                    'volume_multiplier': 1.2,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 10,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'delta_threshold': 250,
                    'volume_avg_period': 20,
                    'volume_multiplier': 1.3,
                    'take_profit_ticks': 16,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'delta_threshold': 200,
                    'volume_avg_period': 20,
                    'volume_multiplier': 1.8,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 4,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '011': {
        'name': 'Exhaustion Reversal',
        'backtest': s011_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'lookback_bars': 3,
                    'volume_avg_period': 20,
                    'min_volume_ratio': 0.7,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'lookback_bars': 4,
                    'volume_avg_period': 20,
                    'min_volume_ratio': 0.6,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 10,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Wide',
                'params': {
                    'lookback_bars': 5,
                    'volume_avg_period': 20,
                    'min_volume_ratio': 0.5,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 12,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'lookback_bars': 3,
                    'volume_avg_period': 20,
                    'min_volume_ratio': 0.5,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'lookback_bars': 4,
                    'volume_avg_period': 20,
                    'min_volume_ratio': 0.7,
                    'take_profit_ticks': 5,
                    'stop_loss_ticks': 5,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '012': {
        'name': 'LVN Rebalance',
        'backtest': s012_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'volume_profile_bars': 40,
                    'lvn_threshold_ratio': 0.35,
                    'value_area_pct': 0.70,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'volume_profile_bars': 50,
                    'lvn_threshold_ratio': 0.30,
                    'value_area_pct': 0.70,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 12,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Wide',
                'params': {
                    'volume_profile_bars': 60,
                    'lvn_threshold_ratio': 0.25,
                    'value_area_pct': 0.70,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 14,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'volume_profile_bars': 40,
                    'lvn_threshold_ratio': 0.25,
                    'value_area_pct': 0.70,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 10,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'volume_profile_bars': 50,
                    'lvn_threshold_ratio': 0.35,
                    'value_area_pct': 0.70,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '013': {
        'name': 'Value Area Rejection',
        'backtest': s013_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'volume_profile_bars': 40,
                    'value_area_pct': 0.65,
                    'boundary_touch_ticks': 1,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'volume_profile_bars': 50,
                    'value_area_pct': 0.70,
                    'boundary_touch_ticks': 2,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Wide',
                'params': {
                    'volume_profile_bars': 60,
                    'value_area_pct': 0.75,
                    'boundary_touch_ticks': 3,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 10,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'volume_profile_bars': 40,
                    'value_area_pct': 0.70,
                    'boundary_touch_ticks': 1,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'volume_profile_bars': 50,
                    'value_area_pct': 0.65,
                    'boundary_touch_ticks': 2,
                    'take_profit_ticks': 6,
                    'stop_loss_ticks': 5,
                    'session_filter': 'RTH',
                }
            },
        }
    },
    '014': {
        'name': 'Failed Auction Hook',
        'backtest': s014_backtest,
        'variations': {
            1: {
                'name': 'Tight',
                'params': {
                    'volume_profile_bars': 40,
                    'value_area_pct': 0.65,
                    'breakout_threshold_ticks': 2,
                    'reentry_tolerance_ticks': 1,
                    'take_profit_ticks': 10,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            2: {
                'name': 'Default',
                'params': {
                    'volume_profile_bars': 50,
                    'value_area_pct': 0.70,
                    'breakout_threshold_ticks': 3,
                    'reentry_tolerance_ticks': 2,
                    'take_profit_ticks': 12,
                    'stop_loss_ticks': 10,
                    'session_filter': 'RTH',
                }
            },
            3: {
                'name': 'Wide',
                'params': {
                    'volume_profile_bars': 60,
                    'value_area_pct': 0.75,
                    'breakout_threshold_ticks': 4,
                    'reentry_tolerance_ticks': 3,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 12,
                    'session_filter': 'RTH',
                }
            },
            4: {
                'name': 'Aggressive',
                'params': {
                    'volume_profile_bars': 40,
                    'value_area_pct': 0.70,
                    'breakout_threshold_ticks': 2,
                    'reentry_tolerance_ticks': 1,
                    'take_profit_ticks': 14,
                    'stop_loss_ticks': 8,
                    'session_filter': 'RTH',
                }
            },
            5: {
                'name': 'Scalp',
                'params': {
                    'volume_profile_bars': 50,
                    'value_area_pct': 0.65,
                    'breakout_threshold_ticks': 3,
                    'reentry_tolerance_ticks': 2,
                    'take_profit_ticks': 8,
                    'stop_loss_ticks': 6,
                    'session_filter': 'RTH',
                }
            },
        }
    }
}


def _expand_session_variations(variations):
    """Build the 4 required session variations from the strategy default/base params."""
    # Prefer variation named "Default", otherwise use the first variation.
    default_key = None
    for k, v in sorted(variations.items()):
        if v.get('name', '').lower() == 'default':
            default_key = k
            break
    if default_key is None:
        default_key = sorted(variations.keys())[0]

    base_spec = variations[default_key]
    expanded = []
    for session_var_id, session_var in SESSION_VARIATIONS.items():
        params = deepcopy(base_spec['params'])
        params['session_filter'] = session_var['sessions']
        expanded.append({
            'base_variation': default_key,
            'session_variation': session_var_id,
            'name': f"{session_var_id}: {session_var['name']}",
            'params': params,
        })
    return expanded


def run_variation(strategy_id, variation_num, variation_spec):
    """Run a single parameter variation and return results."""
    try:
        print(f"  [{variation_num}] {variation_spec['name']}...", end=" ", flush=True)

        module = STRATEGIES[strategy_id]['backtest']
        runner = getattr(module, 'run_backtest', None) or getattr(module, 'run')
        result = runner(variation_spec['params'])

        metrics = result['metrics']
        result['variation'] = variation_num
        result['variation_name'] = variation_spec['name']

        # Flag high potential configs
        potential = "🚀 HIGH POTENTIAL" if (
            metrics['profit_factor'] > 2.0 and metrics['total_trades'] > 5
        ) else ""

        status = "✓" if metrics['profit_factor'] > 1.5 else "·"
        print(f"{status} PF={metrics['profit_factor']:.2f} PnL=${metrics['net_pnl_usd']:.0f} {potential}")

        return result
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return None


def run_optimization(strategy_id):
    """Run all variations for a strategy and return ranked results."""
    if strategy_id not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_id}")

    strat = STRATEGIES[strategy_id]
    print(f"\n{'='*70}")
    print(f"Strategy {strategy_id}: {strat['name']}")
    print(f"{'='*70}")

    results = []
    expanded_variations = _expand_session_variations(strat['variations'])
    for var_spec in expanded_variations:
        var_num = var_spec['session_variation']
        result = run_variation(strategy_id, var_num, var_spec)
        if result:
            result['base_variation'] = var_spec['base_variation']
            result['session_variation'] = var_spec['session_variation']
            result['session_filter'] = var_spec['params']['session_filter']
            results.append(result)

    # Sort by profit factor (desc), then net_pnl (desc)
    results.sort(
        key=lambda r: (
            -r['metrics']['profit_factor'],
            -r['metrics']['net_pnl_usd'],
        )
    )

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d')
    out_dir = Path(__file__).resolve().parents[1] / 'data' / 'results'
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{strategy_id}_optimization_{timestamp}.json"
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✓ Results saved to {out_file}")
    print(f"\nTop 3 Variations (by Profit Factor):")
    for i, r in enumerate(results[:3], 1):
        m = r['metrics']
        print(f"  {i}. {r['variation_name']}: PF={m['profit_factor']:.2f}, "
              f"PnL=${m['net_pnl_usd']:.0f}, Trades={m['total_trades']}")

    return results


def main():
    parser = argparse.ArgumentParser(description='Optimize strategy parameters')
    parser.add_argument('--strategy-id', type=str, choices=['001', '002', '003', '004', '005', '006', '007', '008', '009', '010', '011', '012', '013', '014', 'all'],
                        default='all', help='Strategy ID to optimize')
    args = parser.parse_args()

    if args.strategy_id == 'all':
        all_results = {}
        for sid in ['001', '002', '003', '004', '005', '006', '007', '008', '009', '010', '011', '012', '013', '014']:
            all_results[sid] = run_optimization(sid)
        return all_results
    else:
        return run_optimization(args.strategy_id)


if __name__ == '__main__':
    main()
