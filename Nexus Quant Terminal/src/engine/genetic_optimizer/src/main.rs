use std::fs::File;
use std::env;
use std::error::Error;
use std::path::Path;
use serde::{Serialize, Deserialize};
use rand::Rng;
use rayon::prelude::*;

#[derive(Debug, Clone, Deserialize)]
struct RawCandle {
    #[serde(default, alias = "time")]
    open_time: Option<u64>,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    volume: f64,
}

#[derive(Debug, Clone, Serialize)]
struct Candle {
    time: u64,
    open: f64,
    high: f64,
    low: f64,
    close: f64,
    volume: f64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
struct Genome {
    rsi_period: usize,
    rsi_oversold: f64,
    rsi_overbought: f64,
    rsi_enabled: bool,

    bb_period: usize,
    bb_std: f64,
    bb_enabled: bool,

    ema_fast_period: usize,
    ema_slow_period: usize,
    ema_enabled: bool,

    htf_ema_period: usize,
    htf_ema_enabled: bool,

    rejection_filter_enabled: bool,
    pinbar_wick_ratio: f64,

    min_bb_width: f64,
    volatility_filter_enabled: bool,
}

impl Genome {
    fn random() -> Self {
        let mut rng = rand::thread_rng();
        let rsi_period = rng.gen_range(2..30);
        let rsi_oversold = rng.gen_range(15.0..42.0);
        let rsi_overbought = rng.gen_range(58.0..85.0);
        let rsi_enabled = rng.gen_bool(0.75);

        let bb_period = rng.gen_range(5..40);
        let bb_std = rng.gen_range(1.0..3.2);
        let bb_enabled = rng.gen_bool(0.75);

        let ema_fast_period = rng.gen_range(2..20);
        let ema_slow_period = rng.gen_range(10..80);
        let ema_slow_period = if ema_slow_period <= ema_fast_period {
            ema_fast_period + rng.gen_range(3..25)
        } else {
            ema_slow_period
        };
        let ema_enabled = rng.gen_bool(0.75);

        let htf_ema_period = rng.gen_range(50..200);
        let htf_ema_enabled = rng.gen_bool(0.80);

        let rejection_filter_enabled = rng.gen_bool(0.70);
        let pinbar_wick_ratio = rng.gen_range(0.20..0.55);

        let min_bb_width = rng.gen_range(0.001..0.012);
        let volatility_filter_enabled = rng.gen_bool(0.70);

        let mut g = Genome {
            rsi_period,
            rsi_oversold,
            rsi_overbought,
            rsi_enabled,
            bb_period,
            bb_std,
            bb_enabled,
            ema_fast_period,
            ema_slow_period,
            ema_enabled,
            htf_ema_period,
            htf_ema_enabled,
            rejection_filter_enabled,
            pinbar_wick_ratio,
            min_bb_width,
            volatility_filter_enabled,
        };
        g.ensure_confluence();
        g
    }

    fn ensure_confluence(&mut self) {
        if self.ema_slow_period <= self.ema_fast_period {
            self.ema_slow_period = self.ema_fast_period + 3;
        }
        let count = (self.rsi_enabled as usize) + (self.bb_enabled as usize) + (self.ema_enabled as usize);
        if count < 2 {
            let mut rng = rand::thread_rng();
            match rng.gen_range(0..3) {
                0 => { self.rsi_enabled = true; self.bb_enabled = true; },
                1 => { self.bb_enabled = true; self.ema_enabled = true; },
                _ => { self.rsi_enabled = true; self.ema_enabled = true; },
            }
        }
    }

    fn mutate(&mut self, rate: f64) {
        let mut rng = rand::thread_rng();
        if rng.gen_bool(rate) {
            self.rsi_period = (self.rsi_period as i32 + rng.gen_range(-3..=3)).max(2).min(80) as usize;
        }
        if rng.gen_bool(rate) {
            self.rsi_oversold = (self.rsi_oversold + rng.gen_range(-5.0..=5.0)).max(5.0).min(45.0);
        }
        if rng.gen_bool(rate) {
            self.rsi_overbought = (self.rsi_overbought + rng.gen_range(-5.0..=5.0)).max(55.0).min(95.0);
        }
        if rng.gen_bool(rate) {
            self.rsi_enabled = !self.rsi_enabled;
        }
        if rng.gen_bool(rate) {
            self.bb_period = (self.bb_period as i32 + rng.gen_range(-3..=3)).max(5).min(100) as usize;
        }
        if rng.gen_bool(rate) {
            self.bb_std = (self.bb_std + rng.gen_range(-0.3..=0.3)).max(0.6).min(4.5);
        }
        if rng.gen_bool(rate) {
            self.bb_enabled = !self.bb_enabled;
        }
        if rng.gen_bool(rate) {
            self.ema_fast_period = (self.ema_fast_period as i32 + rng.gen_range(-2..=2)).max(2).min(40) as usize;
        }
        if rng.gen_bool(rate) {
            self.ema_slow_period = (self.ema_slow_period as i32 + rng.gen_range(-3..=3)).max((self.ema_fast_period + 2) as i32).min(150) as usize;
        }
        if rng.gen_bool(rate) {
            self.ema_enabled = !self.ema_enabled;
        }
        if rng.gen_bool(rate) {
            self.htf_ema_period = (self.htf_ema_period as i32 + rng.gen_range(-10..=10)).max(40).min(250) as usize;
        }
        if rng.gen_bool(rate) {
            self.htf_ema_enabled = !self.htf_ema_enabled;
        }
        if rng.gen_bool(rate) {
            self.rejection_filter_enabled = !self.rejection_filter_enabled;
        }
        if rng.gen_bool(rate) {
            self.pinbar_wick_ratio = (self.pinbar_wick_ratio + rng.gen_range(-0.05..=0.05)).max(0.15).min(0.65);
        }
        if rng.gen_bool(rate) {
            self.min_bb_width = (self.min_bb_width + rng.gen_range(-0.001..=0.001)).max(0.0005).min(0.02);
        }
        if rng.gen_bool(rate) {
            self.volatility_filter_enabled = !self.volatility_filter_enabled;
        }
        self.ensure_confluence();
    }

    fn crossover(parent1: &Self, parent2: &Self) -> Self {
        let mut rng = rand::thread_rng();
        let mut child = Genome {
            rsi_period: if rng.gen_bool(0.5) { parent1.rsi_period } else { parent2.rsi_period },
            rsi_oversold: if rng.gen_bool(0.5) { parent1.rsi_oversold } else { parent2.rsi_oversold },
            rsi_overbought: if rng.gen_bool(0.5) { parent1.rsi_overbought } else { parent2.rsi_overbought },
            rsi_enabled: if rng.gen_bool(0.5) { parent1.rsi_enabled } else { parent2.rsi_enabled },
            bb_period: if rng.gen_bool(0.5) { parent1.bb_period } else { parent2.bb_period },
            bb_std: if rng.gen_bool(0.5) { parent1.bb_std } else { parent2.bb_std },
            bb_enabled: if rng.gen_bool(0.5) { parent1.bb_enabled } else { parent2.bb_enabled },
            ema_fast_period: if rng.gen_bool(0.5) { parent1.ema_fast_period } else { parent2.ema_fast_period },
            ema_slow_period: if rng.gen_bool(0.5) { parent1.ema_slow_period } else { parent2.ema_slow_period },
            ema_enabled: if rng.gen_bool(0.5) { parent1.ema_enabled } else { parent2.ema_enabled },
            htf_ema_period: if rng.gen_bool(0.5) { parent1.htf_ema_period } else { parent2.htf_ema_period },
            htf_ema_enabled: if rng.gen_bool(0.5) { parent1.htf_ema_enabled } else { parent2.htf_ema_enabled },
            rejection_filter_enabled: if rng.gen_bool(0.5) { parent1.rejection_filter_enabled } else { parent2.rejection_filter_enabled },
            pinbar_wick_ratio: if rng.gen_bool(0.5) { parent1.pinbar_wick_ratio } else { parent2.pinbar_wick_ratio },
            min_bb_width: if rng.gen_bool(0.5) { parent1.min_bb_width } else { parent2.min_bb_width },
            volatility_filter_enabled: if rng.gen_bool(0.5) { parent1.volatility_filter_enabled } else { parent2.volatility_filter_enabled },
        };
        child.ensure_confluence();
        child
    }
}

// Indicator Calculation Helper Functions
fn calculate_rsi(closes: &[f64], period: usize) -> Vec<f64> {
    let mut rsi = vec![f64::NAN; closes.len()];
    if closes.len() <= period {
        return rsi;
    }

    let mut gains = vec![0.0; closes.len()];
    let mut losses = vec![0.0; closes.len()];

    for i in 1..closes.len() {
        let diff = closes[i] - closes[i - 1];
        if diff > 0.0 {
            gains[i] = diff;
        } else {
            losses[i] = -diff;
        }
    }

    let mut avg_gain = gains[1..=period].iter().sum::<f64>() / period as f64;
    let mut avg_loss = losses[1..=period].iter().sum::<f64>() / period as f64;

    if avg_loss == 0.0 {
        rsi[period] = if avg_gain == 0.0 { 50.0 } else { 100.0 };
    } else {
        let rs = avg_gain / avg_loss;
        rsi[period] = 100.0 - (100.0 / (1.0 + rs));
    }

    for i in (period + 1)..closes.len() {
        avg_gain = (avg_gain * (period - 1) as f64 + gains[i]) / period as f64;
        avg_loss = (avg_loss * (period - 1) as f64 + losses[i]) / period as f64;

        if avg_loss == 0.0 {
            rsi[i] = if avg_gain == 0.0 { 50.0 } else { 100.0 };
        } else {
            let rs = avg_gain / avg_loss;
            rsi[i] = 100.0 - (100.0 / (1.0 + rs));
        }
    }

    rsi
}

fn calculate_bollinger(closes: &[f64], period: usize, std_dev: f64) -> (Vec<f64>, Vec<f64>) {
    let mut upper = vec![f64::NAN; closes.len()];
    let mut lower = vec![f64::NAN; closes.len()];
    if closes.len() < period {
        return (upper, lower);
    }

    let mut sum = 0.0;
    for i in 0..period {
        sum += closes[i];
    }

    for i in (period - 1)..closes.len() {
        if i >= period {
            sum = sum - closes[i - period] + closes[i];
        }
        let mean = sum / period as f64;
        let mut variance_sum = 0.0;
        for j in (i + 1 - period)..=i {
            let diff = closes[j] - mean;
            variance_sum += diff * diff;
        }
        let std = (variance_sum / period as f64).sqrt();
        upper[i] = mean + std * std_dev;
        lower[i] = mean - std * std_dev;
    }

    (upper, lower)
}

fn calculate_ema(closes: &[f64], period: usize) -> Vec<f64> {
    let mut ema = vec![f64::NAN; closes.len()];
    if closes.len() < period {
        return ema;
    }

    let k = 2.0 / (period + 1) as f64;
    let mut sum = 0.0;
    for i in 0..period {
        sum += closes[i];
    }
    let sma = sum / period as f64;
    ema[period - 1] = sma;

    for i in period..closes.len() {
        ema[i] = closes[i] * k + ema[i - 1] * (1.0 - k);
    }

    ema
}

#[allow(dead_code)]
struct SimulationResult {
    total_trades: usize,
    wins: usize,
    ties: usize,
    win_rate: f64,
    win_rate_gross: f64,
    win_rate_effective: f64,
}

fn run_simulation(
    candles: &[Candle],
    genome: &Genome,
    expiry: usize,
    slippage_pct: f64,
) -> SimulationResult {
    let closes: Vec<f64> = candles.iter().map(|c| c.close).collect();

    let rsi = if genome.rsi_enabled {
        calculate_rsi(&closes, genome.rsi_period)
    } else {
        vec![]
    };

    let (bb_upper, bb_lower) = if genome.bb_enabled {
        calculate_bollinger(&closes, genome.bb_period, genome.bb_std)
    } else {
        (vec![], vec![])
    };

    let ema_fast = if genome.ema_enabled {
        calculate_ema(&closes, genome.ema_fast_period)
    } else {
        vec![]
    };

    let ema_slow = if genome.ema_enabled {
        calculate_ema(&closes, genome.ema_slow_period)
    } else {
        vec![]
    };

    let htf_ema = if genome.htf_ema_enabled {
        calculate_ema(&closes, genome.htf_ema_period)
    } else {
        vec![]
    };

    let mut total_trades: usize = 0;
    let mut wins: usize = 0;
    let mut ties: usize = 0;
    let mut next_entry_idx = 0;
    let mut prev_call_cond = false;
    let mut prev_put_cond = false;

    let start_idx = genome.rsi_period
        .max(genome.bb_period)
        .max(genome.ema_slow_period)
        .max(if genome.htf_ema_enabled { genome.htf_ema_period } else { 1 }) + 1;

    if start_idx >= candles.len() || candles.len() <= expiry || start_idx >= candles.len() - expiry {
        return SimulationResult { total_trades: 0, wins: 0, ties: 0, win_rate: 0.0, win_rate_gross: 0.0, win_rate_effective: 0.0 };
    }

    for i in start_idx..(candles.len() - expiry) {
        let mut call_signals = vec![];
        let mut put_signals = vec![];

        // 1. RSI
        if genome.rsi_enabled {
            let rsi_val = rsi[i];
            let prev_rsi_val = rsi[i - 1];
            if !genome.bb_enabled && !genome.ema_enabled {
                call_signals.push(prev_rsi_val <= genome.rsi_oversold && rsi_val > prev_rsi_val);
                put_signals.push(prev_rsi_val >= genome.rsi_overbought && rsi_val < prev_rsi_val);
            } else {
                call_signals.push(rsi_val <= genome.rsi_oversold);
                put_signals.push(rsi_val >= genome.rsi_overbought);
            }
        }

        // 2. Bollinger Bands
        if genome.bb_enabled {
            let close_val = closes[i];
            let prev_close = closes[i - 1];
            let low_val = bb_lower[i];
            let prev_low = bb_lower[i - 1];
            let up_val = bb_upper[i];
            let prev_up = bb_upper[i - 1];

            if genome.volatility_filter_enabled && !genome.rsi_enabled {
                // Ruptura a favor del momentum (Breakout)
                call_signals.push(close_val > up_val && prev_close <= prev_up);
                put_signals.push(close_val < low_val && prev_close >= prev_low);
            } else {
                // Reversión a la media
                call_signals.push(prev_close >= prev_low && close_val < low_val);
                put_signals.push(prev_close <= prev_up && close_val > up_val);
            }
        }

        // 3. EMA Cross / Trend Pullback
        if genome.ema_enabled {
            let f_val = ema_fast[i];
            let s_val = ema_slow[i];
            let prev_f = ema_fast[i - 1];
            let prev_s = ema_slow[i - 1];

            if genome.rsi_enabled {
                // Tendencia EMA + Pullback RSI
                call_signals.push(f_val > s_val && rsi[i] <= genome.rsi_oversold);
                put_signals.push(f_val < s_val && rsi[i] >= genome.rsi_overbought);
            } else {
                // Cruce puro EMA
                call_signals.push(prev_f <= prev_s && f_val > s_val);
                put_signals.push(prev_f >= prev_s && f_val < s_val);
            }
        }

        // 4. HTF Trend Alignment Filter
        if genome.htf_ema_enabled {
            let htf_val = htf_ema[i];
            call_signals.push(!htf_val.is_nan() && closes[i] > htf_val);
            put_signals.push(!htf_val.is_nan() && closes[i] < htf_val);
        }

        // 5. Rejection Candle Action Filter
        if genome.rejection_filter_enabled {
            let candle = &candles[i];
            let range = candle.high - candle.low;
            if range > 0.0 {
                let open_p = candle.open;
                let close_p = candle.close;
                let lower_shadow = close_p.min(open_p) - candle.low;
                let upper_shadow = candle.high - close_p.max(open_p);

                call_signals.push((lower_shadow / range) >= genome.pinbar_wick_ratio);
                put_signals.push((upper_shadow / range) >= genome.pinbar_wick_ratio);
            } else {
                call_signals.push(false);
                put_signals.push(false);
            }
        }

        // 6. Volatility Squeeze Filter
        if genome.volatility_filter_enabled && genome.bb_enabled {
            let width = (bb_upper[i] - bb_lower[i]) / closes[i];
            let threshold = if genome.min_bb_width > 0.0 {
                genome.min_bb_width
            } else {
                let start_k = if i >= 100 { i - 99 } else { 0 };
                let mut window_widths: Vec<f64> = (start_k..=i).map(|k| (bb_upper[k] - bb_lower[k]) / closes[k]).collect();
                window_widths.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
                let q30_idx = ((window_widths.len() as f64) * 0.30) as usize;
                window_widths[q30_idx.min(window_widths.len() - 1)]
            };
            let squeeze_active = width <= threshold;
            if genome.bb_enabled && genome.rsi_enabled {
                call_signals.push(!squeeze_active);
                put_signals.push(!squeeze_active);
            } else {
                let prev_width = (bb_upper[i - 1] - bb_lower[i - 1]) / closes[i - 1];
                let prev_threshold = if genome.min_bb_width > 0.0 {
                    genome.min_bb_width
                } else {
                    let prev_i = i - 1;
                    let start_k = if prev_i >= 100 { prev_i - 99 } else { 0 };
                    let mut window_widths: Vec<f64> = (start_k..=prev_i).map(|k| (bb_upper[k] - bb_lower[k]) / closes[k]).collect();
                    window_widths.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
                    let q30_idx = ((window_widths.len() as f64) * 0.30) as usize;
                    window_widths[q30_idx.min(window_widths.len() - 1)]
                };
                let prev_squeeze = prev_width <= prev_threshold;
                call_signals.push(prev_squeeze && closes[i] > candles[i].open);
                put_signals.push(prev_squeeze && closes[i] < candles[i].open);
            }
        }

        let call_cond_raw = !call_signals.is_empty() && call_signals.iter().all(|&x| x);
        let put_cond_raw = !put_signals.is_empty() && put_signals.iter().all(|&x| x);

        // Edge Trigger (filtro de flanco equivalente a ~shift(1) en Python genetic_composite.py)
        let call_cond = call_cond_raw && !prev_call_cond;
        let put_cond = put_cond_raw && !prev_put_cond;

        prev_call_cond = call_cond_raw;
        prev_put_cond = put_cond_raw;

        if i < next_entry_idx {
            continue;
        }

        // Neutralizar señales contradictorias cuando CALL y PUT se activan a la vez
        let is_call = call_cond && !put_cond;
        let is_put = put_cond && !call_cond;

        if (is_call || is_put) && i + 1 < candles.len() {
            total_trades += 1;

            let entry_price_raw = candles[i + 1].open;
            let entry_price = if is_call {
                entry_price_raw * (1.0 + slippage_pct)
            } else {
                entry_price_raw * (1.0 - slippage_pct)
            };
            let exit_price = closes[i + expiry];

            let price_diff = exit_price - entry_price;
            let eps = 1e-8_f64;

            // Clasificación ternaria WIN / TIE / LOSS
            let is_tie = price_diff.abs() <= eps;
            let is_win = if is_tie {
                false  // Empate: no cuenta como ganancia
            } else if is_call {
                price_diff > 0.0
            } else {
                price_diff < 0.0
            };

            if is_tie {
                ties += 1;
            } else if is_win {
                wins += 1;
            }

            next_entry_idx = i + expiry;
        }
    }

    let decisive = total_trades.saturating_sub(ties);
    let win_rate_effective = if decisive > 0 {
        wins as f64 / decisive as f64
    } else {
        0.0
    };
    let win_rate_gross = if total_trades > 0 {
        wins as f64 / total_trades as f64
    } else {
        0.0
    };

    SimulationResult {
        total_trades,
        wins,
        ties,
        win_rate: win_rate_effective,
        win_rate_gross,
        win_rate_effective,
    }
}

// Calculate Fitness function multidimensional: Expectativa Matemática + Frecuencia + Anti-Overfitting
fn calculate_fitness(
    candles: &[Candle],
    genome: &Genome,
    expiry: usize,
    min_total_trades: f64,
    min_trades_per_day: f64,
    total_days: f64,
    slippage_pct: f64,
    payout: f64,
) -> f64 {
    let sim = run_simulation(candles, genome, expiry, slippage_pct);
    if sim.total_trades == 0 {
        return 0.0;
    }
    let total_trades = sim.total_trades as f64;
    let trades_per_day = total_trades / total_days.max(0.1);

    let freq_multiplier = if total_trades < min_total_trades {
        (total_trades / min_total_trades).powf(1.5)
    } else {
        1.0
    };

    let tpd_multiplier = if min_trades_per_day > 0.0 && trades_per_day < min_trades_per_day {
        (trades_per_day / min_trades_per_day).powf(2.0)
    } else {
        1.0
    };

    // Expectativa Matemática normalizada usando total_trades en el denominador (incluye empates con PnL = 0)
    let payout_proxy = payout;
    let p_win = sim.wins as f64 / total_trades;
    let p_loss = (sim.total_trades.saturating_sub(sim.wins + sim.ties)) as f64 / total_trades;
    let expected_value = (p_win * payout_proxy) - (p_loss * 1.0);

    if expected_value <= 0.0 {
        return 0.0;
    }

    let normalized_freq = (trades_per_day / min_trades_per_day.max(1.0)).min(3.0);
    let score = expected_value * normalized_freq.sqrt() * freq_multiplier * tpd_multiplier;

    score
}

// Robustness Neighbour Stability Evaluation
fn calculate_neighbour_stability(
    candles: &[Candle],
    genome: &Genome,
    expiry: usize,
    base_win_rate: f64,
    slippage_pct: f64,
) -> f64 {
    let mut neighbour_rates = vec![];
    let variations = vec![-1, 1];
    
    for v in variations {
        let mut test_genome = *genome;
        if genome.rsi_enabled && genome.rsi_period > 3 {
            test_genome.rsi_period = (test_genome.rsi_period as i32 + v) as usize;
        }
        if genome.bb_enabled && genome.bb_period > 6 {
            test_genome.bb_period = (test_genome.bb_period as i32 + v) as usize;
        }
        if genome.ema_enabled && test_genome.ema_slow_period > test_genome.ema_fast_period + 3 {
            test_genome.ema_slow_period = (test_genome.ema_slow_period as i32 + v * 2) as usize;
        }
        if genome.htf_ema_enabled && test_genome.htf_ema_period > 45 {
            test_genome.htf_ema_period = (test_genome.htf_ema_period as i32 + v * 5) as usize;
        }
        if genome.rejection_filter_enabled {
            test_genome.pinbar_wick_ratio = (test_genome.pinbar_wick_ratio + (v as f64) * 0.03).max(0.15).min(0.65);
        }
        
        let sim = run_simulation(candles, &test_genome, expiry, slippage_pct);
        if sim.total_trades > 0 {
            neighbour_rates.push(sim.win_rate);
        }
    }
    
    if neighbour_rates.is_empty() {
        return base_win_rate;
    }
    
    let min_neighbour = neighbour_rates.iter().cloned().fold(f64::INFINITY, f64::min);
    min_neighbour
}

#[derive(Serialize)]
struct OptimizationResult {
    in_sample_win_rate: f64,
    in_sample_win_rate_gross: f64,
    in_sample_win_rate_effective: f64,
    out_of_sample_win_rate: f64,
    out_of_sample_win_rate_gross: f64,
    out_of_sample_win_rate_effective: f64,
    in_sample_trades: usize,
    out_of_sample_trades: usize,
    trades_per_day: f64,
    neighbour_stability_is: f64,
    overfitting_degradation: f64,
    overfitting_status: String,
    parameters: Genome,
}

fn load_candles_from_csv(path: &str) -> Result<Vec<Candle>, Box<dyn Error>> {
    let file = File::open(path)?;
    let mut rdr = csv::ReaderBuilder::new()
        .has_headers(true)
        .flexible(true)
        .from_reader(file);
        
    let mut candles = Vec::new();
    
    for result in rdr.deserialize() {
        let record: RawCandle = result?;
        
        let time = match record.open_time {
            Some(t) => {
                if t > 2_u64.pow(32) {
                    t / 1000 // Convert milliseconds to seconds
                } else {
                    t
                }
            },
            None => 0
        };
        
        if time == 0 {
            continue;
        }
        
        candles.push(Candle {
            time,
            open: record.open,
            high: record.high,
            low: record.low,
            close: record.close,
            volume: record.volume,
        });
    }
    
    Ok(candles)
}

fn main() -> Result<(), Box<dyn Error>> {
    // Parse manual arguments
    let args: Vec<String> = env::args().collect();
    
    let mut csv_path = String::new();
    let mut expiry = 1;
    let mut min_total_trades = 5.0;
    let mut min_trades_per_day = 1.0;
    let mut generations = 50;
    let mut population_size = 250;
    let oos_split = 0.7; // 70% In-Sample, 30% Out-of-Sample
    let mut target_winrate = 0.80;
    let mut max_epochs = 5;
    
    let mut slippage_pct = 0.0;
    let mut payout = 0.85;
    
    for i in 1..args.len() {
        match args[i].as_str() {
            "--csv" => {
                if i + 1 < args.len() {
                    csv_path = args[i + 1].clone();
                }
            },
            "--expiry" => {
                if i + 1 < args.len() {
                    expiry = args[i + 1].parse().unwrap_or(1);
                }
            },
            "--min-trades" => {
                if i + 1 < args.len() {
                    min_total_trades = args[i + 1].parse().unwrap_or(5.0);
                }
            },
            "--min-trades-per-day" => {
                if i + 1 < args.len() {
                    min_trades_per_day = args[i + 1].parse().unwrap_or(1.0);
                }
            },
            "--generations" => {
                if i + 1 < args.len() {
                    generations = args[i + 1].parse().unwrap_or(50);
                }
            },
            "--population" => {
                if i + 1 < args.len() {
                    population_size = args[i + 1].parse().unwrap_or(250);
                }
            },
            "--target-winrate" => {
                if i + 1 < args.len() {
                    let val: f64 = args[i + 1].parse().unwrap_or(0.80);
                    target_winrate = if val > 1.0 { val / 100.0 } else { val };
                }
            },
            "--epochs" => {
                if i + 1 < args.len() {
                    max_epochs = args[i + 1].parse().unwrap_or(5);
                }
            },
            "--slippage" => {
                if i + 1 < args.len() {
                    slippage_pct = args[i + 1].parse().unwrap_or(0.0);
                }
            },
            "--payout" => {
                if i + 1 < args.len() {
                    payout = args[i + 1].parse().unwrap_or(0.85);
                }
            },
            _ => {}
        }
    }
    
    if csv_path.is_empty() || !Path::new(&csv_path).exists() {
        eprintln!("Error: Se requiere una ruta CSV valida mediante --csv.");
        std::process::exit(1);
    }
    
    let mut candles = load_candles_from_csv(&csv_path)?;
    if candles.is_empty() {
        eprintln!("Error: El archivo CSV no contiene datos.");
        std::process::exit(1);
    }
    
    // Ordenar velas cronológicamente
    candles.sort_by_key(|c| c.time);
    
    // Dividir en In-Sample y Out-of-Sample
    let split_idx = (candles.len() as f64 * oos_split) as usize;
    let (is_candles, oos_candles) = candles.split_at(split_idx);
    
    // Calcular días totales en In-Sample para medir frecuencia de trades
    let total_days_is = if is_candles.len() > 1 {
        (is_candles.last().unwrap().time - is_candles.first().unwrap().time) as f64 / 86400.0
    } else {
        1.0
    };
    
    // Inicializar población aleatoria con confluencias
    let mut population = Vec::with_capacity(population_size);
    for _ in 0..population_size {
        population.push(Genome::random());
    }
    
    let mutation_rate = 0.18;
    let elite_size = (population_size as f64 * 0.12) as usize; // 12% elite
    
    let mut target_achieved = false;
    let mut epoch = 0;
    
    // Bucle continuo por épocas hasta alcanzar target winrate o agotar épocas
    while epoch < max_epochs && !target_achieved {
        for g_idx in 0..generations {
            // Evaluar fitness de la población en paralelo usando Rayon
            let mut rated_population: Vec<(Genome, f64)> = population.par_iter()
                .map(|&genome| {
                    let fitness = calculate_fitness(is_candles, &genome, expiry, min_total_trades, min_trades_per_day, total_days_is, slippage_pct, payout);
                    (genome, fitness)
                })
                .collect();
                
            // Ordenar población por fitness descendente
            rated_population.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            
            // Verificar si el líder alcanzó el objetivo
            let top_genome = rated_population[0].0;
            let top_sim = run_simulation(is_candles, &top_genome, expiry, slippage_pct);
            let trades_per_day = top_sim.total_trades as f64 / total_days_is;
            if top_sim.win_rate >= target_winrate && top_sim.total_trades as f64 >= min_total_trades && trades_per_day >= min_trades_per_day {
                target_achieved = true;
            }
            
            // Crear siguiente generación
            let mut next_population = Vec::with_capacity(population_size);
            
            // Mantener elite
            for i in 0..elite_size {
                next_population.push(rated_population[i].0);
            }
            
            // Cruzamientos y mutaciones
            while next_population.len() < population_size {
                let p1_idx = tournament_select(&rated_population, 4);
                let p2_idx = tournament_select(&rated_population, 4);
                
                let parent1 = &rated_population[p1_idx].0;
                let parent2 = &rated_population[p2_idx].0;
                
                let mut child = Genome::crossover(parent1, parent2);
                child.mutate(mutation_rate);
                next_population.push(child);
            }
            
            population = next_population;
            
            let total_gens_overall = max_epochs * generations;
            let current_gen_overall = epoch * generations + (g_idx + 1);
            println!("PROGRESS: {}/{}", current_gen_overall, total_gens_overall);
            use std::io::Write;
            std::io::stdout().flush().unwrap();
        }
        
        if target_achieved {
            break;
        }
        
        // Si no se alcanzó el target en esta época, re-inyectar 70% de genomas aleatorios de alta confluencia
        for i in elite_size..population_size {
            population[i] = Genome::random();
        }
        epoch += 1;
    }

    // Evaluar la población final para extraer las mejores soluciones robustas
    let mut rated_final: Vec<(Genome, f64)> = population.par_iter()
        .map(|&genome| {
            let fitness = calculate_fitness(is_candles, &genome, expiry, min_total_trades, min_trades_per_day, total_days_is, slippage_pct, payout);
            (genome, fitness)
        })
        .collect();
        
    rated_final.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    
    // Tomar las mejores soluciones y filtrar por robustez OOS y vecindario
    let mut results = Vec::new();
    let evaluation_depth = rated_final.len().min(100);
    
    for i in 0..evaluation_depth {
        let genome = rated_final[i].0;
        let is_sim = run_simulation(is_candles, &genome, expiry, slippage_pct);
        let trades_per_day = is_sim.total_trades as f64 / total_days_is;
        if is_sim.total_trades == 0 || (is_sim.total_trades as f64) < min_total_trades {
            continue;
        }
        
        // 1. Filtro de Estabilidad de vecindario en IS
        let neighbour_is = calculate_neighbour_stability(is_candles, &genome, expiry, is_sim.win_rate, slippage_pct);
        
        // 2. Simulación en el dataset Out-of-Sample (OOS)
        let oos_sim = run_simulation(oos_candles, &genome, expiry, slippage_pct);
        
        let degradation = (is_sim.win_rate - oos_sim.win_rate).max(0.0);
        let status = if degradation <= 0.08 {
            "ROBUSTO (Sin Overfitting)".to_string()
        } else if degradation <= 0.18 {
            "MODERADO (Overfitting Aceptable)".to_string()
        } else {
            "ALTO OVERFITTING (Cuidado)".to_string()
        };

        results.push(OptimizationResult {
            in_sample_win_rate: is_sim.win_rate_effective,
            in_sample_win_rate_gross: is_sim.win_rate_gross,
            in_sample_win_rate_effective: is_sim.win_rate_effective,
            out_of_sample_win_rate: oos_sim.win_rate_effective,
            out_of_sample_win_rate_gross: oos_sim.win_rate_gross,
            out_of_sample_win_rate_effective: oos_sim.win_rate_effective,
            in_sample_trades: is_sim.total_trades,
            out_of_sample_trades: oos_sim.total_trades,
            trades_per_day,
            neighbour_stability_is: neighbour_is,
            overfitting_degradation: degradation,
            overfitting_status: status,
            parameters: genome,
        });
    }
    
    // Ordenar resultados evaluando EXCLUSIVAMENTE métricas In-Sample para evitar Data Leakage del OOS:
    // 1) Cumplimiento del Target Win Rate In-Sample (80%-90%)
    // 2) Frecuencia de trades por día (para completar ciclo el mismo día)
    // 3) Win Rate In-Sample y Estabilidad de vecindario en In-Sample
    results.sort_by(|a, b| {
        let is_target_a = if a.in_sample_win_rate >= target_winrate { 10.0 } else { 0.0 };
        let is_target_b = if b.in_sample_win_rate >= target_winrate { 10.0 } else { 0.0 };

        let tpd_bonus_a = if a.trades_per_day >= min_trades_per_day { 5.0 } else { a.trades_per_day };
        let tpd_bonus_b = if b.trades_per_day >= min_trades_per_day { 5.0 } else { b.trades_per_day };

        let score_a = is_target_a + tpd_bonus_a + a.in_sample_win_rate * 4.0 + a.neighbour_stability_is * 2.0;
        let score_b = is_target_b + tpd_bonus_b + b.in_sample_win_rate * 4.0 + b.neighbour_stability_is * 2.0;

        score_b.partial_cmp(&score_a).unwrap_or(std::cmp::Ordering::Equal)
    });
    
    // Devolver el mejor resultado en formato JSON impreso en stdout
    if !results.is_empty() {
        let json_output = serde_json::to_string_pretty(&results[0])?;
        println!("{}", json_output);
    } else {
        println!("{{ \"error\": \"No se encontraron soluciones que cumplan los criterios de trades minimos y robustez.\" }}");
    }
    
    Ok(())
}

fn tournament_select(rated_pop: &[(Genome, f64)], tournament_size: usize) -> usize {
    let mut rng = rand::thread_rng();
    let mut best_idx = rng.gen_range(0..rated_pop.len());
    let mut best_fit = rated_pop[best_idx].1;
    
    for _ in 1..tournament_size {
        let idx = rng.gen_range(0..rated_pop.len());
        let fit = rated_pop[idx].1;
        if fit > best_fit {
            best_fit = fit;
            best_idx = idx;
        }
    }
    
    best_idx
}
