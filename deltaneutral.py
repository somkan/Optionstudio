from datetime import datetime, timedelta
#from papertrade import PaperTrade
import math

class DeltaNeutralStrategy:

    def __init__(self, underlying_symbol='NIFTY', options_chain=None):
        self.underlying_symbol = underlying_symbol
        self.options_chain = options_chain
        self.positions = []
        self.backtest_results = None
        self.risk_parameters = {
            'max_loss_per_trade': 50,  # Max allowed loss per trade
            'max_delta_deviation': 0.1,  # Max allowed delta deviation from neutral
            'position_size': 75  # Default position size
        }

    def calculate_delta(self, option_type, moneyness, days_to_expiry):
        """Simple delta approximation based on moneyness and time"""
        if option_type == 'CE':
            return min(0.5 + (moneyness * 0.1) + (1 / (days_to_expiry + 1)), 0.99)
        else:
            return max(-0.5 + (moneyness * 0.1) - (1 / (days_to_expiry + 1)), -0.99)

    def find_neutral_combination(self, spot_price):
        """Find the best Delta Neutral combination"""
        if not self.options_chain:
            return None

        candidates = []

        for expiry in self.options_chain['records']['data']:
            moneyness = (spot_price - expiry['strikePrice']) / spot_price
            days_to_expiry = (datetime.strptime(expiry['expiryDate'], "%d-%b-%Y") - datetime.now()).days

            # Call option
            if 'CE' in expiry:
                call_delta = self.calculate_delta('CE', moneyness, days_to_expiry)
                call_price = expiry['CE']['lastPrice']
            else:
                call_delta = 0
                call_price = None

            # Put option
            if 'PE' in expiry:
                put_delta = self.calculate_delta('PE', moneyness, days_to_expiry)
                put_price = expiry['PE']['lastPrice']
            else:
                put_delta = 0
                put_price = None

            if call_price and put_price:
                candidates.append({
                    'expiry': expiry['expiryDate'],
                    'strike': expiry['strikePrice'],
                    'call_delta': call_delta,
                    'put_delta': put_delta,
                    'call_price': call_price,
                    'put_price': put_price,
                    'net_delta': call_delta + put_delta,
                    'premium_collected': call_price + put_price
                })

        # Filter candidates based on risk parameters
        filtered_candidates = [
            c for c in candidates
            if abs(c['net_delta']) <= self.risk_parameters['max_delta_deviation']
        ]

        # Sort by premium collected (descending)
        filtered_candidates.sort(key=lambda x: x['premium_collected'], reverse=True)

        return filtered_candidates[0] if filtered_candidates else None

    def open_position(self, spot_price, combination):
        """Open a Delta Neutral position"""
        if not combination:
            return False

        position = {
            'entry_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'entry_price': spot_price,
            'strike': combination['strike'],
            'call_price': combination['call_price'],
            'put_price': combination['put_price'],
            'net_delta': combination['net_delta'],
            'premium_collected': combination['premium_collected'],
            'exit_date': None,
            'exit_price': None,
            'pnl': 0
        }
        self.positions.append(position)
        return True

    def monitor_positions(self, spot_price):
        """Monitor and adjust open positions"""
        for position in self.positions:
            if not position['exit_date']:
                # Calculate current PnL
                position['pnl'] = (spot_price - position['entry_price']) * self.risk_parameters['position_size']

                # Check for exit conditions
                if position['pnl'] <= -self.risk_parameters['max_loss_per_trade']:
                    position['exit_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    position['exit_price'] = spot_price

    def get_open_positions(self):
        """Get all open positions"""
        return [p for p in self.positions if not p['exit_date']]

    def get_closed_positions(self):
        """Get all closed positions"""
        return [p for p in self.positions if p['exit_date']]

    def backtest(self, historical_data):
        """Backtest the strategy"""
        results = []
        for i in range(1, len(historical_data)):
            current = historical_data[i]
            prev = historical_data[i - 1]

            # Open position if conditions are met
            combination = self.find_neutral_combination(float(current['EOD_CLOSE_INDEX_VAL']))
            if combination:
                self.open_position(float(current['EOD_CLOSE_INDEX_VAL']), combination)

            # Monitor and close positions
            self.monitor_positions(float(current['EOD_CLOSE_INDEX_VAL']))

            # Record closed positions
            results.extend(self.get_closed_positions())

        self.backtest_results = results
        return results

    def get_backtest_metrics(self):
        """Calculate backtest performance metrics"""
        if not self.backtest_results:
            return {}

        pnls = [trade['pnl'] for trade in self.backtest_results]
        return {
            'total_trades': len(self.backtest_results),
            'profitable_trades': sum(1 for pnl in pnls if pnl > 0),
            'total_return': sum(pnls),
            'win_rate': sum(1 for pnl in pnls if pnl > 0) / len(pnls) if pnls else 0,
            'max_drawdown': min(pnls) if pnls else 0
        }

    def generate_signals(self, combination, spot_price):
        """Generate buy/sell signals based on Delta Neutral criteria"""
        signals = {
            'underlying_action': 'HOLD',
            'call_action': 'HOLD',
            'put_action': 'HOLD',
            'reasoning': []
        }

        try:
            # Calculate theoretical values using Put-Call Parity
            risk_free_rate = 0.05
            days_to_expiry = combination['days_to_expiry']
            time_to_expiry = max(days_to_expiry, 1) / 365  # Prevent division by zero

            discount_factor = math.exp(-risk_free_rate * time_to_expiry)
            theoretical_put = combination['call_price'] - spot_price + (combination['strike'] * discount_factor)
            theoretical_call = spot_price - (combination['strike'] * discount_factor) + combination['put_price']

            # Underlying Action
            if combination['net_delta'] > 0.1:
                signals['underlying_action'] = "SELL"
                signals['reasoning'].append(f"Net Delta {combination['net_delta']:.2f} > 0.1")
            elif combination['net_delta'] < -0.1:
                signals['underlying_action'] = "BUY"
                signals['reasoning'].append(f"Net Delta {combination['net_delta']:.2f} < -0.1")

            # Call Option Action
            if combination['call_price'] > theoretical_call * 1.05:
                signals['call_action'] = "SELL"
                signals['reasoning'].append(
                    f"Call overpriced by {(combination['call_price'] / theoretical_call - 1) * 100:.1f}%")
            elif combination['call_price'] < theoretical_call * 0.95:
                signals['call_action'] = "BUY"
                signals['reasoning'].append(
                    f"Call underpriced by {(1 - combination['call_price'] / theoretical_call) * 100:.1f}%")

            # Put Option Action
            if combination['put_price'] > theoretical_put * 1.05:
                signals['put_action'] = "SELL"
                signals['reasoning'].append(
                    f"Put overpriced by {(combination['put_price'] / theoretical_put - 1) * 100:.1f}%")
            elif combination['put_price'] < theoretical_put * 0.95:
                signals['put_action'] = "BUY"
                signals['reasoning'].append(
                    f"Put underpriced by {(1 - combination['put_price'] / theoretical_put) * 100:.1f}%")

        except Exception as e:
            signals['reasoning'].append(f"Signal error: {str(e)}")

        return signals