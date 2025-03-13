import os
import json
import datetime as dt
from typing import Dict, List, Optional, Union, Tuple
import pandas as pd
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
import time
import random

class OptionTrader:
    """
    Class for handling option trading operations.
    Uses Alpaca for paper trading.
    """
    
    def __init__(self, api_key=None, api_secret=None, base_url=None):
        """Initialize the option trader"""
        self.simulation_mode = False
        self.simulated_portfolio = None
        
        # Try to get API credentials from environment variables if not provided
        self.api_key = api_key or os.environ.get('ALPACA_API_KEY')
        self.api_secret = api_secret or os.environ.get('ALPACA_API_SECRET')
        self.base_url = base_url or os.environ.get('ALPACA_API_BASE_URL', 'https://paper-api.alpaca.markets')
        
        # Initialize API connection if credentials are available
        if self.api_key and self.api_secret:
            try:
                self.api = tradeapi.REST(
                    self.api_key,
                    self.api_secret,
                    self.base_url,
                    api_version='v2'
                )
            except Exception as e:
                print(f"Error connecting to Alpaca API: {e}")
                self.api = None
        else:
            print("No Alpaca API credentials found. Running in simulation mode.")
            self.api = None
        
        # Initialize simulated portfolio if in simulation mode
        if self.api is None:
            self._initialize_simulation()
    
    def _initialize_simulation(self):
        """Initialize simulation mode with a simulated portfolio"""
        # Check if we have a saved portfolio
        if os.path.exists('simulated_portfolio.json'):
            with open('simulated_portfolio.json', 'r') as f:
                self.simulated_portfolio = json.load(f)
        else:
            # Create a new simulated portfolio
            self.simulated_portfolio = {
                'cash': 100000.0,
                'buying_power': 200000.0,  # 2x margin
                'equity': 100000.0,
                'positions': [],
                'transactions': []
            }
            self._save_portfolio()
    
    def _save_portfolio(self):
        """Save the simulated portfolio to a file"""
        with open('simulated_portfolio.json', 'w') as f:
            json.dump(self.simulated_portfolio, f, indent=2)
    
    def get_account_info(self) -> Dict:
        """Get account information"""
        if self.api:
            try:
                account = self.api.get_account()
                return {
                    'cash': float(account.cash),
                    'equity': float(account.equity),
                    'buying_power': float(account.buying_power),
                    'portfolio_value': float(account.portfolio_value)
                }
            except APIError as e:
                print(f"API Error: {e}")
                return {'error': str(e)}
        else:
            # Return simulated account info
            portfolio_value = self.simulated_portfolio['cash']
            for position in self.simulated_portfolio['positions']:
                portfolio_value += position['market_value']
            
            return {
                'cash': self.simulated_portfolio['cash'],
                'equity': portfolio_value,
                'buying_power': self.simulated_portfolio['cash'] * 2,  # Simulate 2x margin
                'portfolio_value': portfolio_value
            }
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        if self.api:
            try:
                positions = self.api.list_positions()
                return [
                    {
                        'symbol': p.symbol,
                        'qty': int(p.qty),
                        'avg_entry_price': float(p.avg_entry_price),
                        'market_value': float(p.market_value),
                        'unrealized_pl': float(p.unrealized_pl),
                        'current_price': float(p.current_price)
                    }
                    for p in positions
                ]
            except APIError as e:
                print(f"API Error: {e}")
                return []
        else:
            # Return simulated positions
            return self.simulated_portfolio['positions']
    
    def format_option_symbol(self, ticker: str, expiration_date: str, 
                            strike_price: float, option_type: str) -> str:
        """
        Format an option symbol in OCC format.
        
        Args:
            ticker: Stock ticker symbol
            expiration_date: Option expiration date in YYYY-MM-DD format
            strike_price: Option strike price
            option_type: 'call' or 'put'
        
        Returns:
            Option symbol in OCC format
        """
        # Convert expiration date to required format (YYMMDD)
        exp_date = dt.datetime.strptime(expiration_date, '%Y-%m-%d')
        exp_formatted = exp_date.strftime('%y%m%d')
        
        # Format strike price (multiply by 1000 and remove decimal)
        strike_formatted = f"{int(strike_price * 1000):08d}"
        
        # Option type (C for call, P for put)
        opt_type = 'C' if option_type.lower() == 'call' else 'P'
        
        # Construct OCC symbol: SYMBOL + YY + MM + DD + C/P + Strike
        return f"{ticker.upper()}{exp_formatted}{opt_type}{strike_formatted}"
    
    def _get_simulated_price(self, ticker, strike, option_type):
        """Generate a simulated price for an option"""
        # This is a very simplified model
        # In reality, option pricing is much more complex
        underlying_price = 150.0  # Simulated underlying price
        time_to_expiry = 30 / 365.0  # Simulated 30 days to expiry
        volatility = 0.3  # Simulated volatility
        
        # Calculate intrinsic value
        if option_type.lower() == 'call':
            intrinsic = max(0, underlying_price - strike)
        else:
            intrinsic = max(0, strike - underlying_price)
        
        # Add time value (very simplified)
        time_value = underlying_price * volatility * (time_to_expiry ** 0.5)
        
        # Total option price
        price = intrinsic + time_value
        
        # Add some random noise
        price *= random.uniform(0.9, 1.1)
        
        return round(price, 2)
    
    def buy_option(self, ticker, expiration, strike, option_type, quantity, price=None):
        """Buy an option contract"""
        try:
            # Format the option symbol
            date_part = expiration.replace('-', '')
            option_symbol = f"{ticker}{date_part}{'C' if option_type.lower() == 'call' else 'P'}{int(strike*100):08d}"
            
            # Check if we're in simulation mode
            if self.simulation_mode:
                # Generate a simulated order ID
                order_id = f"sim-order-{int(time.time())}"
                
                # Calculate the cost
                if price is None:
                    # If no price specified, use a simulated market price
                    price = self._get_simulated_price(ticker, strike, option_type)
                
                cost = price * quantity * 100  # Each option contract is for 100 shares
                
                # Check if we have enough buying power
                if cost > self.simulated_portfolio['buying_power']:
                    return {'error': 'Insufficient buying power'}
                
                # Update the portfolio
                self.simulated_portfolio['buying_power'] -= cost
                
                # Add the position
                position = {
                    'symbol': option_symbol,
                    'quantity': quantity,
                    'avg_price': price,
                    'current_price': price,
                    'cost_basis': cost,
                    'market_value': cost,
                    'unrealized_pl': 0,
                    'unrealized_plpc': 0,
                    'type': option_type,
                    'expiration': expiration,
                    'strike': strike,
                    'underlying': ticker
                }
                
                self.simulated_portfolio['positions'].append(position)
                
                # Create a simulated order
                order = {
                    'id': order_id,
                    'symbol': option_symbol,
                    'status': 'filled',
                    'side': 'buy',
                    'qty': quantity,
                    'filled_qty': quantity,
                    'filled_avg_price': price,
                    'created_at': dt.datetime.now().isoformat(),
                    'type': 'market' if price is None else 'limit'
                }
                
                # Add to transaction history
                transaction = {
                    'id': f"sim-tx-{int(time.time())}",
                    'order_id': order_id,
                    'symbol': option_symbol,
                    'side': 'buy',
                    'qty': quantity,
                    'price': price,
                    'timestamp': dt.datetime.now().isoformat(),
                    'commission': 0,
                    'asset_class': 'option'
                }
                
                self.simulated_portfolio['transactions'].append(transaction)
                
                # Save the updated portfolio
                self._save_portfolio()
                
                return order
            
            # If not in simulation mode, place a real order with Alpaca
            try:
                # Implement real trading with Alpaca API
                order_type = 'limit' if price else 'market'
                limit_price = price * 100 if price else None  # Convert to per-share price
                
                order = self.api.submit_order(
                    symbol=option_symbol,
                    qty=quantity,
                    side='buy',
                    type=order_type,
                    time_in_force='day',
                    limit_price=limit_price
                )
                
                # Check if order is a dictionary or an object
                if isinstance(order, dict):
                    # If it's already a dictionary, return it
                    return order
                else:
                    # If it's an object, convert it to a dictionary
                    return {
                        'id': order.id,
                        'symbol': order.symbol,
                        'status': order.status,
                        'side': 'buy',
                        'qty': quantity,
                        'filled_qty': order.filled_qty,
                        'filled_avg_price': order.filled_avg_price,
                        'created_at': order.created_at
                    }
            except Exception as e:
                print(f"API Error: {e}")
                return {'error': str(e)}
        except Exception as e:
            print(f"Error buying option: {e}")
            return {'error': str(e)}
    
    def sell_option(self, ticker, expiration, strike, option_type, quantity, price=None):
        """Sell an option contract"""
        try:
            # Format the option symbol
            date_part = expiration.replace('-', '')
            option_symbol = f"{ticker}{date_part}{'C' if option_type.lower() == 'call' else 'P'}{int(strike*100):08d}"
            
            # Check if we're in simulation mode
            if self.simulation_mode:
                # Generate a simulated order ID
                order_id = f"sim-order-{int(time.time())}"
                
                # Calculate the proceeds
                if price is None:
                    # If no price specified, use a simulated market price
                    price = self._get_simulated_price(ticker, strike, option_type)
                
                proceeds = price * quantity * 100  # Each option contract is for 100 shares
                
                # Find the position
                position_found = False
                for i, position in enumerate(self.simulated_portfolio['positions']):
                    if position['symbol'] == option_symbol and position['quantity'] >= quantity:
                        position_found = True
                        
                        # Calculate realized P/L
                        realized_pl = (price - position['avg_price']) * quantity * 100
                        
                        # Update the position
                        if position['quantity'] == quantity:
                            # Remove the position if selling all
                            self.simulated_portfolio['positions'].pop(i)
                        else:
                            # Reduce the position if selling part
                            position['quantity'] -= quantity
                            position['cost_basis'] = position['avg_price'] * position['quantity'] * 100
                            position['market_value'] = position['current_price'] * position['quantity'] * 100
                        
                        # Update the portfolio
                        self.simulated_portfolio['buying_power'] += proceeds
                        self.simulated_portfolio['equity'] += realized_pl
                        
                        break
                
                if not position_found:
                    return {'error': 'Position not found or insufficient quantity'}
                
                # Create a simulated order
                order = {
                    'id': order_id,
                    'symbol': option_symbol,
                    'status': 'filled',
                    'side': 'sell',
                    'qty': quantity,
                    'filled_qty': quantity,
                    'filled_avg_price': price,
                    'created_at': dt.datetime.now().isoformat(),
                    'type': 'market' if price is None else 'limit'
                }
                
                # Add to transaction history
                transaction = {
                    'id': f"sim-tx-{int(time.time())}",
                    'order_id': order_id,
                    'symbol': option_symbol,
                    'side': 'sell',
                    'qty': quantity,
                    'price': price,
                    'timestamp': dt.datetime.now().isoformat(),
                    'commission': 0,
                    'asset_class': 'option',
                    'realized_pl': realized_pl
                }
                
                self.simulated_portfolio['transactions'].append(transaction)
                
                # Save the updated portfolio
                self._save_portfolio()
                
                return order
            
            # If not in simulation mode, place a real order with Alpaca
            try:
                # Implement real trading with Alpaca API
                order_type = 'limit' if price else 'market'
                limit_price = price * 100 if price else None  # Convert to per-share price
                
                order = self.api.submit_order(
                    symbol=option_symbol,
                    qty=quantity,
                    side='sell',
                    type=order_type,
                    time_in_force='day',
                    limit_price=limit_price
                )
                
                # Check if order is a dictionary or an object
                if isinstance(order, dict):
                    # If it's already a dictionary, return it
                    return order
                else:
                    # If it's an object, convert it to a dictionary
                    return {
                        'id': order.id,
                        'symbol': order.symbol,
                        'status': order.status,
                        'side': 'sell',
                        'qty': quantity,
                        'filled_qty': order.filled_qty,
                        'filled_avg_price': order.filled_avg_price,
                        'created_at': order.created_at
                    }
            except Exception as e:
                print(f"API Error: {e}")
                return {'error': str(e), 'status': 'error'}  # Add status field for error cases
        except Exception as e:
            print(f"Error selling option: {e}")
            return {'error': str(e), 'status': 'error'}  # Add status field for error cases
    
    def get_order_history(self) -> List[Dict]:
        """Get order history"""
        if self.api:
            try:
                orders = self.api.list_orders(status='all', limit=100)
                return [
                    {
                        'id': o.id,
                        'symbol': o.symbol,
                        'side': o.side,
                        'qty': int(o.qty),
                        'filled_qty': int(o.filled_qty) if o.filled_qty else 0,
                        'type': o.type,
                        'status': o.status,
                        'created_at': o.created_at,
                        'filled_at': o.filled_at
                    }
                    for o in orders
                ]
            except APIError as e:
                print(f"API Error: {e}")
                return []
        else:
            # Return simulated orders
            return self.simulated_portfolio['orders']
    
    def update_positions_market_value(self, price_updates: Dict[str, float]):
        """
        Update market values of positions based on current prices.
        
        Args:
            price_updates: Dictionary mapping option symbols to current prices
        """
        if not self.api:
            for position in self.simulated_portfolio['positions']:
                if position['symbol'] in price_updates:
                    current_price = price_updates[position['symbol']]
                    position['current_price'] = current_price
                    position['market_value'] = position['qty'] * current_price * 100
                    position['unrealized_pl'] = (current_price - position['avg_entry_price']) * position['qty'] * 100
            
            # Save updated portfolio
            self._save_portfolio()
    
    def get_option_quote(self, ticker, expiration_date, strike_price, option_type):
        """
        Get real-time quote data for a specific option contract.
        
        Args:
            ticker (str): The underlying stock ticker symbol
            expiration_date (str): Option expiration date in YYYY-MM-DD format
            strike_price (float): Option strike price
            option_type (str): 'call' or 'put'
            
        Returns:
            dict: Option quote data including bid, ask, last price, and greeks
        """
        try:
            # Format the option symbol in OCC format
            # Example: AAPL220321C00220000 (AAPL, 2022-03-21, Call, $220.00)
            date_part = expiration_date.replace('-', '')
            option_symbol = f"{ticker}{date_part}{'C' if option_type.lower() == 'call' else 'P'}{int(strike_price*100):08d}"
            
            # Get the option quote from Alpaca
            # Note: This is a placeholder - Alpaca's options API may have different method names
            quote = self.api.get_option_quote(option_symbol)
            
            return quote
        except Exception as e:
            print(f"Error getting option quote: {e}")
            return None 