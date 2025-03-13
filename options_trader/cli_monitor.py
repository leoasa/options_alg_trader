# Remove the yfinance import
# import yfinance as yf  # Remove this line

import pandas as pd
import numpy as np
import time
import datetime as dt
import argparse
from tabulate import tabulate
import os
import alpaca_trade_api as tradeapi
from datetime import datetime, timedelta
import random

class OptionsCliMonitor:
    def __init__(self, tickers, refresh_interval=60):
        """
        Initialize the options CLI monitor.
        
        Args:
            tickers (list): List of stock tickers to monitor
            refresh_interval (int): Data refresh interval in seconds
        """
        self.tickers = tickers
        self.refresh_interval = refresh_interval
        self.data = {}
        self.options_data = {}
        self.last_update = None
        
        # Initialize Alpaca API
        self.api = None
        self._init_alpaca_api()
    
    def _init_alpaca_api(self):
        """Initialize Alpaca API connection"""
        try:
            # Get API credentials from environment variables
            api_key = os.environ.get('ALPACA_API_KEY')
            api_secret = os.environ.get('ALPACA_API_SECRET')
            base_url = os.environ.get('ALPACA_API_BASE_URL', 'https://paper-api.alpaca.markets')
            
            if not api_key or not api_secret:
                print("Alpaca API credentials not found in environment variables.")
                print("Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables.")
                return
            
            # Initialize Alpaca API
            self.api = tradeapi.REST(api_key, api_secret, base_url, api_version='v2')
            print("Successfully connected to Alpaca API")
        except Exception as e:
            print(f"Error connecting to Alpaca API: {e}")
            print("Some features may be limited without API access")
        
    def fetch_stock_data(self, ticker):
        """Fetch basic stock data and metrics using Alpaca API"""
        if not self.api:
            return self._create_empty_stock_data()
        
        try:
            # Get asset information
            asset = self.api.get_asset(ticker)
            
            # Get latest bar data
            bars = self.api.get_bars(ticker, '1Day', limit=1).df
            if bars.empty:
                return self._create_empty_stock_data()
            
            latest_bar = bars.iloc[-1]
            
            # Get previous day's close for calculating change
            yesterday = datetime.now() - timedelta(days=1)
            yesterday_bars = self.api.get_bars(ticker, '1Day', 
                                              start=yesterday.strftime('%Y-%m-%d'),
                                              limit=1).df
            prev_close = yesterday_bars.iloc[-1]['close'] if not yesterday_bars.empty else latest_bar['close']
            
            # Calculate change percentage
            change_pct = ((latest_bar['close'] - prev_close) / prev_close) * 100
            
            # Get 52-week high/low
            year_ago = datetime.now() - timedelta(days=365)
            yearly_bars = self.api.get_bars(ticker, '1Day', 
                                           start=year_ago.strftime('%Y-%m-%d')).df
            
            high_52w = yearly_bars['high'].max() if not yearly_bars.empty else None
            low_52w = yearly_bars['low'].min() if not yearly_bars.empty else None
            
            # Create stock data dictionary
            stock_data = {
                'price': latest_bar['close'],
                'change': change_pct,
                'volume': latest_bar['volume'],
                'avg_volume': yearly_bars['volume'].mean() if not yearly_bars.empty else None,
                'market_cap': None,  # Not directly available from Alpaca
                'beta': None,  # Not directly available from Alpaca
                'pe_ratio': None,  # Not directly available from Alpaca
                '52w_high': high_52w,
                '52w_low': low_52w
            }
            
            return stock_data
        
        except Exception as e:
            print(f"Error fetching stock data for {ticker} from Alpaca: {e}")
            return self._create_empty_stock_data()
    
    def _create_empty_stock_data(self):
        """Create an empty stock data dictionary"""
        return {
            'price': None,
            'change': None,
            'volume': None,
            'avg_volume': None,
            'market_cap': None,
            'beta': None,
            'pe_ratio': None,
            '52w_high': None,
            '52w_low': None
        }
    
    def fetch_options_data(self, ticker):
        """Fetch options chain data for a ticker using Alpaca API"""
        if not self.api or not hasattr(self.api, 'get_option_chain'):
            return self._create_empty_options_data()
        
        try:
            # Get current stock price
            stock_data = self.fetch_stock_data(ticker)
            current_price = stock_data.get('price')
            
            if not current_price:
                return self._create_empty_options_data()
            
            # This is a placeholder - implement the actual Alpaca API calls
            # For now, generate sample data
            
            # Generate sample expiration date
            today = datetime.now()
            exp_date = (today + timedelta(days=7)).strftime('%Y-%m-%d')
            
            # Generate sample strikes around the current price
            strikes = [round(current_price * (1 + i * 0.05), 2) for i in range(-5, 6)]
            
            # Generate sample calls and puts data
            calls_data = []
            puts_data = []
            
            for strike in strikes:
                # Sample call option
                call = {
                    'strike': strike,
                    'lastPrice': max(0.01, round(current_price - strike + random.uniform(0.5, 2.0), 2)),
                    'bid': max(0.01, round(current_price - strike + random.uniform(0.3, 1.5), 2)),
                    'ask': max(0.01, round(current_price - strike + random.uniform(0.7, 2.5), 2)),
                    'volume': int(random.uniform(100, 5000)),
                    'openInterest': int(random.uniform(500, 10000)),
                    'impliedVolatility': random.uniform(0.2, 0.8),
                    'type': 'call'
                }
                calls_data.append(call)
                
                # Sample put option
                put = {
                    'strike': strike,
                    'lastPrice': max(0.01, round(strike - current_price + random.uniform(0.5, 2.0), 2)),
                    'bid': max(0.01, round(strike - current_price + random.uniform(0.3, 1.5), 2)),
                    'ask': max(0.01, round(strike - current_price + random.uniform(0.7, 2.5), 2)),
                    'volume': int(random.uniform(100, 5000)),
                    'openInterest': int(random.uniform(500, 10000)),
                    'impliedVolatility': random.uniform(0.2, 0.8),
                    'type': 'put'
                }
                puts_data.append(put)
            
            # Find ATM options
            atm_call = min(calls_data, key=lambda x: abs(x['strike'] - current_price))
            atm_put = min(puts_data, key=lambda x: abs(x['strike'] - current_price))
            
            options_data = {
                'expiration': exp_date,
                'calls': calls_data,
                'puts': puts_data,
                'atm_iv_call': atm_call['impliedVolatility'],
                'atm_iv_put': atm_put['impliedVolatility']
            }
            
            return options_data
        
        except Exception as e:
            print(f"Error fetching options data for {ticker} from Alpaca: {e}")
            return self._create_empty_options_data()
    
    def _create_empty_options_data(self):
        """Create an empty options data dictionary"""
        return {
            'expiration': None,
            'calls': [],
            'puts': [],
            'atm_iv_call': None,
            'atm_iv_put': None
        }
    
    def update_data(self):
        """Update all data for monitored tickers"""
        for ticker in self.tickers:
            try:
                self.data[ticker] = self.fetch_stock_data(ticker)
                self.options_data[ticker] = self.fetch_options_data(ticker)
                # Add a small delay between requests
                time.sleep(0.5)
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
        
        self.last_update = dt.datetime.now()
    
    def display_stock_summary(self):
        """Display a summary of stock data"""
        if not self.data:
            print("No data available yet.")
            return
        
        # Prepare data for tabulate
        table_data = []
        for ticker in self.tickers:
            if ticker in self.data:
                stock_data = self.data[ticker]
                options_data = self.options_data.get(ticker, {})
                
                row = [
                    ticker,
                    f"${stock_data.get('price', 'N/A')}",
                    f"{stock_data.get('change', 'N/A'):.2f}%" if stock_data.get('change') else "N/A",
                    f"{stock_data.get('beta', 'N/A'):.2f}" if stock_data.get('beta') else "N/A",
                    f"{options_data.get('atm_iv_call', 'N/A'):.2%}" if options_data.get('atm_iv_call') else "N/A",
                    f"{options_data.get('atm_iv_put', 'N/A'):.2%}" if options_data.get('atm_iv_put') else "N/A"
                ]
                table_data.append(row)
        
        headers = ["Ticker", "Price", "Change", "Beta", "ATM Call IV", "ATM Put IV"]
        print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))
    
    def display_options_data(self, ticker):
        """Display options data for a specific ticker"""
        if ticker not in self.options_data or not self.options_data[ticker]:
            print(f"No options data available for {ticker}")
            return
        
        options_data = self.options_data[ticker]
        
        print(f"\n{ticker} Options - Expiration: {options_data['expiration']}")
        
        # Display calls
        print("\nCALLS:")
        calls_data = []
        for call in options_data['calls'][:10]:  # Limit to 10 rows for readability
            calls_data.append([
                f"${call['strike']}",
                f"${call['lastPrice']}",
                f"${call['bid']}",
                f"${call['ask']}",
                call['volume'],
                call['openInterest'],
                f"{call['impliedVolatility']:.2%}"
            ])
        
        headers = ["Strike", "Last", "Bid", "Ask", "Volume", "Open Int", "IV"]
        print(tabulate(calls_data, headers=headers, tablefmt="simple"))
        
        # Display puts
        print("\nPUTS:")
        puts_data = []
        for put in options_data['puts'][:10]:  # Limit to 10 rows for readability
            puts_data.append([
                f"${put['strike']}",
                f"${put['lastPrice']}",
                f"${put['bid']}",
                f"${put['ask']}",
                put['volume'],
                put['openInterest'],
                f"{put['impliedVolatility']:.2%}"
            ])
        
        print(tabulate(puts_data, headers=headers, tablefmt="simple"))
    
    def run(self):
        """Run the CLI monitor"""
        try:
            while True:
                # Clear screen
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Update data
                self.update_data()
                
                # Display header
                print(f"Options Monitor - Last Update: {self.last_update}")
                print("=" * 80)
                
                # Display stock summary
                self.display_stock_summary()
                
                # Display options data for the first ticker
                if self.tickers:
                    self.display_options_data(self.tickers[0])
                
                # Wait for next update
                print(f"\nRefreshing in {self.refresh_interval} seconds... (Press Ctrl+C to exit)")
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            print("\nExiting Options Monitor...")


def main():
    parser = argparse.ArgumentParser(description="Options CLI Monitor")
    parser.add_argument("--tickers", "-t", type=str, default="AAPL,MSFT,GOOGL,AMZN,TSLA",
                        help="Comma-separated list of tickers to monitor")
    parser.add_argument("--interval", "-i", type=int, default=60,
                        help="Refresh interval in seconds")
    
    args = parser.parse_args()
    tickers = args.tickers.split(",")
    
    # Add tabulate to requirements
    with open("requirements.txt", "a") as f:
        f.write("\ntabulate==0.9.0\n")
    
    # Create and run monitor
    monitor = OptionsCliMonitor(tickers, refresh_interval=args.interval)
    monitor.run()


if __name__ == "__main__":
    main() 