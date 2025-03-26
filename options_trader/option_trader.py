import os
import json
import datetime as dt
from typing import Dict, List, Optional, Union, Tuple
import pandas as pd
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
import time
import random
import requests

class OptionTrader:
    """
    Class for handling option trading operations.
    Uses Alpaca for paper trading.
    """
    
    def __init__(self, api_key=None, api_secret=None, base_url=None, data_url=None):
        """Initialize the option trader"""
        self.simulation_mode = False
        self.simulated_portfolio = None
        
        # Try to get API credentials from environment variables if not provided
        self.api_key = api_key or os.environ.get('ALPACA_API_KEY')
        self.api_secret = api_secret or os.environ.get('ALPACA_API_SECRET')
        self.base_url = base_url or os.environ.get('ALPACA_API_BASE_URL', 'https://paper-api.alpaca.markets')
        self.data_url = data_url or os.environ.get('ALPACA_DATA_URL', 'https://data.alpaca.markets')
        
        # Initialize API connection
        self.api = self._init_alpaca_api()
        
        # Initialize simulated portfolio if in simulation mode
        if self.api is None:
            self.simulation_mode = True
            self._initialize_simulation()
    
    def _init_alpaca_api(self):
        """Initialize and test connection to Alpaca API"""
        if not self.api_key or not self.api_secret:
            print("No Alpaca API credentials found. Running in simulation mode.")
            return None
            
        try:
            print(f"Initializing Alpaca API with base_url: {self.base_url}")
            api = tradeapi.REST(
                self.api_key,
                self.api_secret,
                self.base_url,
                api_version='v2'
            )
            
            # Test the connection
            try:
                account = api.get_account()
                print(f"Successfully connected to Alpaca API. Account ID: {account.id}")
                print(f"Successfully connected to Alpaca API")
                print(f"Connected to Alpaca account: {account.id} (Status: {account.status})")
                
                # Check if market is open
                clock = api.get_clock()
                if clock.is_open:
                    print("Market is open")
                else:
                    print("Market is closed")
                
                return api
            except Exception as test_error:
                print(f"Warning: API initialized but test connection failed: {test_error}")
                return None
        except Exception as e:
            print(f"Error connecting to Alpaca API: {e}")
            return None
    
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
        """
        Buy an option contract.
        
        Args:
            ticker (str): Stock ticker symbol
            expiration (str): Option expiration date in YYYY-MM-DD format
            strike (float): Option strike price
            option_type (str): Option type ('call' or 'put')
            quantity (int): Number of contracts to buy
            price (float, optional): Limit price (if None, market order is used)
            
        Returns:
            dict: Order information
        """
        # Format the option symbol
        option_symbol = self.format_option_symbol(ticker, expiration, strike, option_type)
        print(f"Attempting to buy {quantity} {option_symbol} contracts")
        
        # Check if we're in simulation mode
        if self.simulation_mode:
            print(f"Running in simulation mode for {option_symbol}")
            # Simulate buying an option
            if not self.simulated_portfolio:
                self._initialize_simulation()
            
            # Check if we have enough buying power
            if price:
                cost = price * 100 * quantity
            else:
                # Estimate price for market order
                cost = self._get_simulated_price(ticker, strike, option_type) * 100 * quantity
            
            if cost > self.simulated_portfolio['buying_power']:
                print(f"Insufficient buying power: {self.simulated_portfolio['buying_power']} < {cost}")
                return {
                    'status': 'rejected',
                    'reason': 'Insufficient buying power',
                    'symbol': option_symbol,
                    'side': 'buy',
                    'qty': quantity,
                    'type': 'market' if price is None else 'limit',
                    'limit_price': price,
                    'filled_avg_price': None,
                    'id': f"sim_{int(time.time())}",
                    'created_at': dt.datetime.now().isoformat(),
                    'error': True,
                    'error_message': f'Insufficient buying power: {self.simulated_portfolio["buying_power"]} < {cost}'
                }
            
            # Simulate the order
            filled_price = self._get_simulated_price(ticker, strike, option_type)
            cost = filled_price * 100 * quantity
            
            # Update portfolio
            self.simulated_portfolio['cash'] -= cost
            self.simulated_portfolio['buying_power'] -= cost
            self.simulated_portfolio['equity'] -= cost  # Will be adjusted when position is added
            
            # Add to positions
            position_found = False
            for position in self.simulated_portfolio['positions']:
                if position['symbol'] == option_symbol:
                    # Update existing position
                    avg_price = (position['avg_entry_price'] * position['qty'] + filled_price * quantity) / (position['qty'] + quantity)
                    position['avg_entry_price'] = avg_price
                    position['qty'] += quantity
                    position['market_value'] = position['qty'] * filled_price * 100
                    position_found = True
                    break
            
            if not position_found:
                # Add new position
                self.simulated_portfolio['positions'].append({
                    'symbol': option_symbol,
                    'qty': quantity,
                    'avg_entry_price': filled_price,
                    'current_price': filled_price,
                    'market_value': filled_price * 100 * quantity,
                    'unrealized_pl': 0,
                    'unrealized_plpc': 0,
                    'type': 'option',
                    'option_type': option_type,
                    'strike': strike,
                    'expiration': expiration,
                    'underlying': ticker
                })
            
            # Add to transactions
            transaction = {
                'id': f"sim_{int(time.time())}",
                'symbol': option_symbol,
                'side': 'buy',
                'qty': quantity,
                'price': filled_price,
                'cost': cost,
                'type': 'option',
                'option_type': option_type,
                'strike': strike,
                'expiration': expiration,
                'underlying': ticker,
                'timestamp': dt.datetime.now().isoformat()
            }
            self.simulated_portfolio['transactions'].append(transaction)
            
            # Save portfolio
            self._save_portfolio()
            print(f"Simulated buy order filled: {quantity} {option_symbol} at ${filled_price}")
            
            # Return order information
            return {
                'status': 'filled',
                'symbol': option_symbol,
                'side': 'buy',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': filled_price,
                'id': transaction['id'],
                'created_at': transaction['timestamp'],
                'success': True
            }
        
        # Real trading with Alpaca API
        if not self.api:
            print("No API connection for real trading")
            return {
                'status': 'rejected',
                'reason': 'No API connection',
                'symbol': option_symbol,
                'side': 'buy',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': None,
                'id': None,
                'created_at': dt.datetime.now().isoformat(),
                'error': True,
                'error_message': 'No API connection'
            }
        
        try:
            # Check account buying power
            account = self.api.get_account()
            buying_power = float(account.buying_power)
            print(f"Account buying power: ${buying_power}")
            
            # Try to get actual option price to estimate cost
            try:
                option_snapshot = self._get_option_snapshot(option_symbol)
                if option_snapshot and 'quote' in option_snapshot:
                    ask_price = option_snapshot['quote'].get('ask_price', None)
                    if ask_price:
                        estimated_cost = float(ask_price) * 100 * quantity
                        print(f"Using ask price ${ask_price} for cost estimate")
                    else:
                        estimated_cost = strike * 0.1 * 100 * quantity
                        print(f"No ask price found, using estimate: ${estimated_cost}")
                else:
                    estimated_cost = strike * 0.1 * 100 * quantity
                    print(f"No option snapshot available, using estimate: ${estimated_cost}")
            except Exception as e:
                print(f"Error getting option price: {e}")
                estimated_cost = strike * 0.1 * 100 * quantity
                print(f"Using fallback cost estimate: ${estimated_cost}")
            
            if estimated_cost > buying_power:
                print(f"Insufficient buying power: ${buying_power} < ${estimated_cost}")
                return {
                    'status': 'rejected',
                    'reason': 'Insufficient buying power',
                    'symbol': option_symbol,
                    'side': 'buy',
                    'qty': quantity,
                    'type': 'market' if price is None else 'limit',
                    'limit_price': price,
                    'filled_avg_price': None,
                    'id': None,
                    'created_at': dt.datetime.now().isoformat(),
                    'error': True,
                    'error_message': f'Insufficient buying power: ${buying_power} < ${estimated_cost}'
                }
            
            # Submit the order
            order_type = 'market' if price is None else 'limit'
            order_args = {
                'symbol': option_symbol,
                'qty': quantity,
                'side': 'buy',
                'type': order_type,
                'time_in_force': 'day'
            }
            
            if price is not None:
                order_args['limit_price'] = price
            
            print(f"Submitting order: {order_args}")
            order = self.api.submit_order(**order_args)
            print(f"Order submitted: {order.id}, status: {order.status}")
            
            # Return order information
            return {
                'status': order.status,
                'symbol': order.symbol,
                'side': order.side,
                'qty': order.qty,
                'type': order.type,
                'limit_price': getattr(order, 'limit_price', None),
                'filled_avg_price': getattr(order, 'filled_avg_price', None),
                'id': order.id,
                'created_at': order.created_at,
                'success': True
            }
        except APIError as e:
            # Handle API errors
            print(f"Alpaca API Error: {e}")
            return {
                'status': 'rejected',
                'reason': str(e),
                'symbol': option_symbol,
                'side': 'buy',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': None,
                'id': None,
                'created_at': dt.datetime.now().isoformat(),
                'error': True,
                'error_message': str(e)
            }
        except Exception as e:
            # Handle other errors
            print(f"Unexpected error: {e}")
            return {
                'status': 'rejected',
                'reason': str(e),
                'symbol': option_symbol,
                'side': 'buy',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': None,
                'id': None,
                'created_at': dt.datetime.now().isoformat(),
                'error': True,
                'error_message': str(e)
            }
    
    def _get_option_snapshot(self, option_symbol):
        """
        Get current snapshot data for an option symbol
        
        Args:
            option_symbol (str): Option symbol in OCC format
            
        Returns:
            dict: Option snapshot data
        """
        if not self.api_key or not self.api_secret:
            print(f"No API credentials to get option snapshot for {option_symbol}")
            return None
            
        try:
            url = f"{self.data_url}/v1beta1/options/snapshots"
            headers = {
                'APCA-API-KEY-ID': self.api_key,
                'APCA-API-SECRET-KEY': self.api_secret
            }
            params = {
                'symbols': option_symbol,
                'feed': 'indicative'  # Use indicative feed if no subscription
            }
            
            print(f"Requesting option snapshot for {option_symbol}")
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # Check if the option symbol is in the response
                if option_symbol in data:
                    return data[option_symbol]
                else:
                    print(f"Option {option_symbol} not found in response")
                    return None
            else:
                print(f"Error fetching option snapshot: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error getting option snapshot: {e}")
            return None
    
    def sell_option(self, ticker, expiration_date, strike_price, option_type, quantity, price=None):
        """
        Sell an option contract.
        
        Args:
            ticker (str): Stock ticker symbol
            expiration_date (str): Option expiration date in YYYY-MM-DD format
            strike_price (float): Option strike price
            option_type (str): Option type ('call' or 'put')
            quantity (int): Number of contracts to sell
            price (float, optional): Limit price (if None, market order is used)
            
        Returns:
            dict: Order information
        """
        # Format the option symbol
        option_symbol = self.format_option_symbol(ticker, expiration_date, strike_price, option_type)
        print(f"Attempting to sell {quantity} {option_symbol} contracts")
        
        # Check if we're in simulation mode
        if self.simulation_mode:
            print(f"Running in simulation mode for {option_symbol}")
            # Simulate selling an option
            if not self.simulated_portfolio:
                self._initialize_simulation()
            
            # Check if we have the position to sell
            position_found = False
            position_index = -1
            for i, position in enumerate(self.simulated_portfolio['positions']):
                if position['symbol'] == option_symbol:
                    position_found = True
                    position_index = i
                    break
            
            if not position_found or self.simulated_portfolio['positions'][position_index]['qty'] < quantity:
                print(f"Insufficient position to sell: {0 if not position_found else self.simulated_portfolio['positions'][position_index]['qty']} < {quantity}")
                return {
                    'status': 'rejected',
                    'reason': 'Insufficient position',
                    'symbol': option_symbol,
                    'side': 'sell',
                    'qty': quantity,
                    'type': 'market' if price is None else 'limit',
                    'limit_price': price,
                    'filled_avg_price': None,
                    'id': f"sim_{int(time.time())}",
                    'created_at': dt.datetime.now().isoformat(),
                    'error': True,
                    'error_message': 'Insufficient position'
                }
            
            # Simulate the order
            filled_price = self._get_simulated_price(ticker, strike_price, option_type)
            proceeds = filled_price * 100 * quantity
            
            # Calculate P&L
            position = self.simulated_portfolio['positions'][position_index]
            entry_price = position['avg_entry_price']
            profit_loss = (filled_price - entry_price) * 100 * quantity
            print(f"Simulated P&L: ${profit_loss} (entry: ${entry_price}, exit: ${filled_price})")
            
            # Update portfolio
            self.simulated_portfolio['cash'] += proceeds
            self.simulated_portfolio['buying_power'] += proceeds
            
            # Update position
            if position['qty'] == quantity:
                # Remove the position entirely
                del self.simulated_portfolio['positions'][position_index]
            else:
                # Reduce the position
                position['qty'] -= quantity
                position['market_value'] = position['qty'] * position['current_price'] * 100
            
            # Add to transactions
            transaction = {
                'id': f"sim_{int(time.time())}",
                'symbol': option_symbol,
                'side': 'sell',
                'qty': quantity,
                'price': filled_price,
                'proceeds': proceeds,
                'profit_loss': profit_loss,
                'type': 'option',
                'option_type': option_type,
                'strike': strike_price,
                'expiration': expiration_date,
                'underlying': ticker,
                'timestamp': dt.datetime.now().isoformat()
            }
            self.simulated_portfolio['transactions'].append(transaction)
            
            # Save portfolio
            self._save_portfolio()
            print(f"Simulated sell order filled: {quantity} {option_symbol} at ${filled_price}")
            
            # Return order information
            return {
                'status': 'filled',
                'symbol': option_symbol,
                'side': 'sell',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': filled_price,
                'proceeds': proceeds,
                'profit_loss': profit_loss,
                'id': transaction['id'],
                'created_at': transaction['timestamp'],
                'success': True
            }
        
        # Real trading with Alpaca API
        if not self.api:
            print("No API connection for real trading")
            return {
                'status': 'rejected',
                'reason': 'No API connection',
                'symbol': option_symbol,
                'side': 'sell',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': None,
                'id': None,
                'created_at': dt.datetime.now().isoformat(),
                'error': True,
                'error_message': 'No API connection'
            }
        
        try:
            # Check if we have the position
            try:
                positions = self.api.list_positions()
                position_found = False
                position_qty = 0
                
                for p in positions:
                    if p.symbol == option_symbol:
                        position_found = True
                        position_qty = int(p.qty)
                        break
                
                if not position_found or position_qty < quantity:
                    print(f"Insufficient position to sell: {position_qty} < {quantity}")
                    return {
                        'status': 'rejected',
                        'reason': 'Insufficient position',
                        'symbol': option_symbol,
                        'side': 'sell',
                        'qty': quantity,
                        'type': 'market' if price is None else 'limit',
                        'limit_price': price,
                        'filled_avg_price': None,
                        'id': None,
                        'created_at': dt.datetime.now().isoformat(),
                        'error': True,
                        'error_message': f'Insufficient position: {position_qty} < {quantity}'
                    }
            except Exception as e:
                print(f"Error checking positions: {e}")
                # Continue anyway, the order will be rejected by Alpaca if we don't have the position
            
            # Submit the order
            order_type = 'market' if price is None else 'limit'
            order_args = {
                'symbol': option_symbol,
                'qty': quantity,
                'side': 'sell',
                'type': order_type,
                'time_in_force': 'day'
            }
            
            if price is not None:
                order_args['limit_price'] = price
            
            print(f"Submitting order: {order_args}")
            order = self.api.submit_order(**order_args)
            print(f"Order submitted: {order.id}, status: {order.status}")
            
            # Return order information
            return {
                'status': order.status,
                'symbol': order.symbol,
                'side': order.side,
                'qty': order.qty,
                'type': order.type,
                'limit_price': getattr(order, 'limit_price', None),
                'filled_avg_price': getattr(order, 'filled_avg_price', None),
                'id': order.id,
                'created_at': order.created_at,
                'success': True
            }
        except APIError as e:
            # Handle API errors
            print(f"Alpaca API Error: {e}")
            return {
                'status': 'rejected',
                'reason': str(e),
                'symbol': option_symbol,
                'side': 'sell',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': None,
                'id': None,
                'created_at': dt.datetime.now().isoformat(),
                'error': True,
                'error_message': str(e)
            }
        except Exception as e:
            # Handle other errors
            print(f"Unexpected error: {e}")
            return {
                'status': 'rejected',
                'reason': str(e),
                'symbol': option_symbol,
                'side': 'sell',
                'qty': quantity,
                'type': 'market' if price is None else 'limit',
                'limit_price': price,
                'filled_avg_price': None,
                'id': None,
                'created_at': dt.datetime.now().isoformat(),
                'error': True,
                'error_message': str(e)
            }
    
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