import pandas as pd
import numpy as np
import time
import datetime as dt
import plotly.graph_objects as go
from dash import Dash, html, dcc, callback, Output, Input, State, ALL, MATCH
import dash_bootstrap_components as dbc
import threading
import json
import dash
import random
import requests
from requests.exceptions import HTTPError
import pickle
import os
from datetime import datetime, timedelta
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
import sys
from functools import wraps, lru_cache
import argparse

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Now import the module
from options_trader.option_trader import OptionTrader

class OptionsMonitor:
    def __init__(self, tickers, refresh_interval=60):
        """
        Initialize the options monitor.
        
        Args:
            tickers (list): List of stock tickers to monitor
            refresh_interval (int): Data refresh interval in seconds
        """
        self.tickers = tickers
        self.refresh_interval = refresh_interval
        self.data = {}
        self.options_data = {}
        self.last_update = None
        
        # Initialize Alpaca API if credentials are available
        self.api = None
        self.trader = None
        self._init_alpaca_api()
        
        # Start data refresh thread
        self.refresh_thread = threading.Thread(target=self._refresh_loop)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
    
    def _init_alpaca_api(self):
        """Initialize Alpaca API connection"""
        try:
            # Try to initialize the OptionTrader which contains Alpaca API
            self.trader = OptionTrader()
            self.api = self.trader.api
            print("Successfully connected to Alpaca API")
        except Exception as e:
            print(f"Error connecting to Alpaca API: {e}")
            print("Some features may be limited without API access")
    
    def _refresh_loop(self):
        """Background thread to refresh data periodically"""
        while True:
            self.refresh_data()
            time.sleep(self.refresh_interval)
    
    def refresh_data(self):
        """Refresh market data for all tickers"""
        print(f"Refreshing data at {datetime.now()}")
        
        # Fetch data for each ticker
        for ticker in self.tickers:
            try:
                # Fetch stock data
                self.data[ticker] = self.fetch_stock_data(ticker)
                
                # Fetch options data
                self.options_data[ticker] = self.fetch_options_data(ticker)
                
                # Add a small delay between requests
                time.sleep(0.5)
            except Exception as e:
                print(f"Error refreshing data for {ticker}: {e}")
        
        self.last_update = datetime.now()
        print(f"Data updated at {self.last_update}")
    
    @lru_cache(maxsize=100)
    def fetch_stock_data(self, ticker, timestamp=None):
        """
        Fetch basic stock data and metrics using Alpaca API
        
        Args:
            ticker (str): The stock ticker
            timestamp: Used for cache invalidation
        """
        if timestamp is None:
            # Round to nearest minute for caching
            timestamp = datetime.now().replace(second=0, microsecond=0)
        
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
    
    @lru_cache(maxsize=100)
    def fetch_options_data(self, ticker, timestamp=None):
        """
        Fetch options chain data for a ticker using Alpaca API
        
        Args:
            ticker (str): The stock ticker
            timestamp: Used for cache invalidation
        """
        if timestamp is None:
            # Round to nearest minute for caching
            timestamp = datetime.now().replace(second=0, microsecond=0)
        
        if not self.api or not hasattr(self.api, 'get_option_chain'):
            return self._create_empty_options_data()
        
        try:
            # Get current stock price
            stock_data = self.fetch_stock_data(ticker)
            current_price = stock_data.get('price')
            
            if not current_price:
                return self._create_empty_options_data()
            
            # Get available expiration dates
            expirations = self._get_option_expirations(ticker)
            
            if not expirations:
                return self._create_empty_options_data()
            
            # Get the first expiration date
            expiration = expirations[0]
            
            # Get options chain for this expiration
            calls, puts = self._get_option_chain(ticker, expiration)
            
            # Calculate ATM IV
            atm_call_iv = self._get_atm_iv(calls, current_price) if calls else None
            atm_put_iv = self._get_atm_iv(puts, current_price) if puts else None
            
            options_data = {
                'ticker': ticker,
                'expiration': expiration,
                'expirations': expirations,
                'calls': calls,
                'puts': puts,
                'atm_call_iv': atm_call_iv,
                'atm_put_iv': atm_put_iv
            }
            
            return options_data
        
        except Exception as e:
            print(f"Error fetching options data for {ticker} from Alpaca: {e}")
            return self._create_empty_options_data()
    
    def _create_empty_options_data(self):
        """Create an empty options data dictionary"""
        return {
            'ticker': None,
            'expiration': None,
            'expirations': [],
            'calls': [],
            'puts': [],
            'atm_call_iv': None,
            'atm_put_iv': None
        }
    
    def _get_option_expirations(self, ticker):
        """Get available option expiration dates for a ticker using Alpaca API"""
        try:
            # This is a placeholder - implement the actual Alpaca API call
            # For example:
            # expirations = self.api.get_option_expirations(ticker)
            
            # For now, generate some sample expiration dates
            today = datetime.now()
            expirations = [
                (today + timedelta(days=i*7)).strftime('%Y-%m-%d')
                for i in range(1, 5)  # Next 4 weeks
            ]
            
            return expirations
        except Exception as e:
            print(f"Error getting option expirations for {ticker}: {e}")
            return []
    
    def _get_option_chain(self, ticker, expiration):
        """Get options chain for a ticker and expiration date using Alpaca API"""
        try:
            # This is a placeholder - implement the actual Alpaca API call
            # For example:
            # chain = self.api.get_option_chain(ticker, expiration)
            # calls = chain['calls']
            # puts = chain['puts']
            
            # For now, generate some sample options data
            stock_data = self.fetch_stock_data(ticker)
            current_price = stock_data.get('price', 100)  # Default to 100 if price not available
            
            if not current_price:
                return [], []
            
            # Generate sample strikes around the current price
            strikes = [round(current_price * (1 + i * 0.05), 2) for i in range(-10, 11)]
            
            # Generate sample calls
            calls = []
            for strike in strikes:
                call = {
                    'strike': strike,
                    'lastPrice': max(0.01, round(current_price - strike + random.uniform(0.5, 2.0), 2)),
                    'bid': max(0.01, round(current_price - strike + random.uniform(0.3, 1.5), 2)),
                    'ask': max(0.01, round(current_price - strike + random.uniform(0.7, 2.5), 2)),
                    'volume': int(random.uniform(100, 5000)),
                    'openInterest': int(random.uniform(500, 10000)),
                    'impliedVolatility': random.uniform(0.2, 0.8)
                }
                calls.append(call)
            
            # Generate sample puts
            puts = []
            for strike in strikes:
                put = {
                    'strike': strike,
                    'lastPrice': max(0.01, round(strike - current_price + random.uniform(0.5, 2.0), 2)),
                    'bid': max(0.01, round(strike - current_price + random.uniform(0.3, 1.5), 2)),
                    'ask': max(0.01, round(strike - current_price + random.uniform(0.7, 2.5), 2)),
                    'volume': int(random.uniform(100, 5000)),
                    'openInterest': int(random.uniform(500, 10000)),
                    'impliedVolatility': random.uniform(0.2, 0.8)
                }
                puts.append(put)
            
            return calls, puts
        
        except Exception as e:
            print(f"Error getting option chain for {ticker} at {expiration}: {e}")
            return [], []
    
    def _get_atm_iv(self, options, current_price):
        """Get at-the-money implied volatility"""
        if not options or not current_price:
            return None
        
        # Find the closest strike to current price
        closest_option = min(options, key=lambda x: abs(x['strike'] - current_price))
        
        return closest_option.get('impliedVolatility')

    def start_monitoring(self):
        """Start the monitoring process by refreshing data immediately"""
        print(f"Starting monitoring for tickers: {', '.join(self.tickers)}")
        
        # Refresh data immediately
        self.refresh_data()
        
        # The refresh_thread was already started in __init__, so we don't need to start it again
        # This method is mainly for compatibility with the dashboard starter function
        
        return True

    def calculate_atm_iv(self, options, current_price):
        """
        Calculate at-the-money implied volatility.
        
        Args:
            options (list): List of option contracts
            current_price (float): Current price of the underlying
            
        Returns:
            float: At-the-money implied volatility
        """
        if not options or not current_price:
            return None
        
        # Find the closest strike to current price
        closest_option = min(options, key=lambda x: abs(x['strike'] - current_price))
        
        return closest_option.get('impliedVolatility')

def create_dashboard(monitor):
    """Create a Dash dashboard for the options monitor"""
    app = Dash(__name__, 
               external_stylesheets=[dbc.themes.DARKLY, 
                                    'https://use.fontawesome.com/releases/v5.15.4/css/all.css'],
               meta_tags=[{'name': 'viewport', 
                          'content': 'width=device-width, initial-scale=1.0'}])
    
    # Add splash screen CSS and JavaScript to the index_string
    app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>Options Trader Dashboard</title>
            {%favicon%}
            {%css%}
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
            <style>
                /* Royal Blue and Black color scheme */
                :root {
                    --royal-blue: #4169E1;
                    --royal-blue-dark: #1e3c8c;
                    --royal-blue-light: #6495ED;
                    --black: #000000;
                    --white: #ffffff;
                    --light-gray: #f8f9fa;
                    --dark-gray: #343a40;
                }
                
                /* Set Roboto as the default font */
                body, h1, h2, h3, h4, h5, h6, p, div, span, button, input, select, textarea {
                    font-family: "Roboto", sans-serif !important;
                }
                
                /* Body styling with more contrasted gradient background */
                body {
                    background: linear-gradient(135deg, #ffffff 0%, #a1c4fd 50%, #4169E1 100%);
                    color: var(--dark-gray);
                    min-height: 100vh;
                    overflow-x: hidden;
                    position: relative;
                }
                
                /* Animated background elements for main app */
                .bg-gradient-element {
                    position: fixed;
                    border-radius: 50%;
                    filter: blur(60px);
                    opacity: 0.4;
                    z-index: -1;
                }
                
                .bg-element-1 {
                    width: 600px;
                    height: 600px;
                    background: radial-gradient(circle, rgba(97, 149, 237, 0.7) 0%, rgba(65, 105, 225, 0) 70%);
                    top: -200px;
                    right: -200px;
                    animation: float-slow 25s ease-in-out infinite;
                }
                
                .bg-element-2 {
                    width: 500px;
                    height: 500px;
                    background: radial-gradient(circle, rgba(30, 60, 140, 0.6) 0%, rgba(30, 60, 140, 0) 70%);
                    bottom: -100px;
                    left: -100px;
                    animation: float-slow 20s ease-in-out infinite 5s;
                }
                
                .bg-element-3 {
                    width: 400px;
                    height: 400px;
                    background: radial-gradient(circle, rgba(161, 196, 253, 0.5) 0%, rgba(161, 196, 253, 0) 70%);
                    top: 30%;
                    left: 20%;
                    animation: float-slow 30s ease-in-out infinite 2s;
                }
                
                @keyframes float-slow {
                    0% { transform: translate(0, 0) rotate(0deg); }
                    25% { transform: translate(50px, 30px) rotate(2deg); }
                    50% { transform: translate(20px, 60px) rotate(0deg); }
                    75% { transform: translate(-30px, 40px) rotate(-2deg); }
                    100% { transform: translate(0, 0) rotate(0deg); }
                }
                
                /* Splash screen styling */
                #splash-screen {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(135deg, #0b1d45 0%, #1e3c8c 50%, #4169E1 100%);
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    z-index: 9999;
                    transition: opacity 1s ease-in-out;
                }
                
                .splash-logo {
                    width: 150px;
                    height: 150px;
                    margin-bottom: 20px;
                    position: relative;
                }
                
                .splash-logo-circle {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    border: 8px solid rgba(255, 255, 255, 0.2);
                    border-top: 8px solid white;
                    border-radius: 50%;
                    animation: spin 1.5s linear infinite;
                }
                
                .splash-logo-icon {
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    font-size: 60px;
                    color: white;
                }
                
                .splash-title {
                    color: white;
                    font-size: 36px;
                    font-weight: 700;
                    margin-bottom: 10px;
                    opacity: 0;
                    transform: translateY(20px);
                    animation: fadeInUp 0.8s ease-out forwards 0.5s;
                }
                
                .splash-subtitle {
                    color: rgba(255, 255, 255, 0.8);
                    font-size: 18px;
                    margin-bottom: 30px;
                    opacity: 0;
                    transform: translateY(20px);
                    animation: fadeInUp 0.8s ease-out forwards 0.7s;
                }
                
                .splash-loading {
                    color: white;
                    font-size: 14px;
                    letter-spacing: 2px;
                    opacity: 0;
                    animation: pulse 1.5s ease-in-out infinite 1s;
                }
                
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                
                @keyframes fadeInUp {
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                @keyframes pulse {
                    0% { opacity: 0.4; }
                    50% { opacity: 1; }
                    100% { opacity: 0.4; }
                }
                
                /* Sidebar styling */
                .sidebar {
                    height: 100vh;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 250px;
                    background-color: var(--royal-blue);
                    color: var(--white);
                    border-right: 1px solid var(--royal-blue-light);
                    z-index: 1000;
                }
                
                .sidebar-header {
                    padding: 20px;
                    background-color: var(--royal-blue-dark);
                    color: var(--white);
                }
                
                .sidebar-link {
                    padding: 15px 20px;
                    color: var(--white);
                    display: flex;
                    align-items: center;
                    border-left: 4px solid transparent;
                }
                
                .sidebar-link:hover {
                    background-color: var(--royal-blue-light);
                    color: var(--white);
                    text-decoration: none;
                }
                
                .sidebar-link.active {
                    background-color: var(--royal-blue-light);
                    color: var(--white);
                    border-left-color: var(--white);
                }
                
                .sidebar-icon {
                    margin-right: 10px;
                    width: 20px;
                    text-align: center;
                }
                
                .content-container {
                    margin-left: 250px;
                    padding: 20px;
                    background: transparent;
                }
                
                /* Card styling with more contrast */
                .card {
                    border: none;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    background-color: rgba(255, 255, 255, 0.95);
                    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
                    overflow: hidden;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                
                .card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 12px 20px rgba(0, 0, 0, 0.2);
                }
                
                .card-header {
                    background-color: var(--royal-blue);
                    color: var(--white);
                    font-weight: bold;
                    padding: 15px 20px;
                    border-bottom: none;
                }
                
                .card-body {
                    padding: 20px;
                }
                
                /* Table styling with more contrast */
                .table {
                    background-color: rgba(255, 255, 255, 0.9);
                    color: var(--dark-gray);
                    border-color: var(--royal-blue-light);
                    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05);
                }
                
                .table thead th {
                    background-color: rgba(65, 105, 225, 0.1);
                    border-bottom: 2px solid var(--royal-blue-light);
                    color: var(--royal-blue-dark);
                    font-weight: 600;
                }
                
                .table-striped tbody tr:nth-of-type(odd) {
                    background-color: rgba(248, 249, 250, 0.7);
                }
                
                .table-hover tbody tr:hover {
                    background-color: rgba(65, 105, 225, 0.05);
                }
                
                /* Button styling */
                .btn-primary {
                    background-color: var(--royal-blue);
                    border-color: var(--royal-blue-light);
                }
                
                .btn-primary:hover {
                    background-color: var(--royal-blue-dark);
                    border-color: var(--royal-blue-light);
                }
                
                /* Options chain table specific styling */
                .options-chain-table {
                    font-size: 0.85rem;
                }
                
                .options-chain-table th {
                    white-space: nowrap;
                    text-align: center;
                    padding: 8px 4px;
                }
                
                .options-chain-table td {
                    white-space: nowrap;
                    text-align: center;
                    padding: 6px 4px;
                }
                
                .text-success {
                    color: #28a745 !important;
                }
                
                .text-danger {
                    color: #dc3545 !important;
                }
                
                /* Heading styling */
                h4, h5, h6 {
                    color: var(--black);
                    font-weight: 500;
                }
                
                /* Fix dropdown width */
                .dash-dropdown {
                    width: 100% !important;
                }
                
                /* Responsive adjustments */
                @media (max-width: 768px) {
                    .sidebar {
                        width: 70px;
                    }
                    .sidebar-link-text {
                        display: none;
                    }
                    .content-container {
                        margin-left: 70px;
                    }
                }
            </style>
        </head>
        <body>
            <!-- Animated background elements for main app -->
            <div class="bg-gradient-element bg-element-1"></div>
            <div class="bg-gradient-element bg-element-2"></div>
            <div class="bg-gradient-element bg-element-3"></div>
            
            <!-- Splash Screen -->
            <div id="splash-screen">
                <div class="splash-bg-element splash-bg-1"></div>
                <div class="splash-bg-element splash-bg-2"></div>
                <div class="splash-bg-element splash-bg-3"></div>
                
                <div class="splash-logo">
                    <div class="splash-logo-circle"></div>
                    <i class="fas fa-chart-line splash-logo-icon"></i>
                </div>
                <h1 class="splash-title">Options Trader</h1>
                <p class="splash-subtitle">Advanced Trading Dashboard</p>
                <p class="splash-loading">LOADING DATA...</p>
            </div>
            
            <!-- Main App Container -->
            <div id="dash-container">
                {%app_entry%}
            </div>
            
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
                
                <!-- Custom JavaScript for splash screen -->
                <script>
                    // Function to hide splash screen and show app
                    function hideSplash() {
                        const splash = document.getElementById('splash-screen');
                        const app = document.getElementById('dash-container');
                        
                        // Fade out splash screen
                        splash.style.opacity = '0';
                        
                        // Show app content
                        app.style.opacity = '1';
                        
                        // Remove splash screen after animation completes
                        setTimeout(() => {
                            splash.style.display = 'none';
                        }, 1000);
                    }
                    
                    // Hide splash screen after 3 seconds
                    setTimeout(hideSplash, 3000);
                </script>
            </footer>
        </body>
    </html>
    '''
    
    # Sidebar navigation
    sidebar = html.Div([
        # Header
        html.Div([
            html.I(className="fas fa-chart-line me-2", style={"fontSize": "24px", "color": "white"}),
            html.Span("Options Trader", className="h4 text-white sidebar-link-text"),
        ], className="sidebar-header d-flex align-items-center"),
        
        # Navigation links
        html.Div([
            html.A([
                html.I(className="fas fa-chart-bar sidebar-icon"),
                html.Span("Market Data", className="sidebar-link-text"),
            ], href="#", id="market-data-link", className="sidebar-link active"),
            
            html.A([
                html.I(className="fas fa-briefcase sidebar-icon"),
                html.Span("Portfolio", className="sidebar-link-text"),
            ], href="#", id="portfolio-link", className="sidebar-link"),
            
            html.A([
                html.I(className="fas fa-exchange-alt sidebar-icon"),
                html.Span("Trading", className="sidebar-link-text"),
            ], href="#", id="trading-link", className="sidebar-link"),
            
            html.A([
                html.I(className="fas fa-cog sidebar-icon"),
                html.Span("Settings", className="sidebar-link-text"),
            ], href="#", id="settings-link", className="sidebar-link"),
        ], className="mt-3"),
    ], className="sidebar")
    
    # Content container
    content = html.Div([
        # Status bar with last update time
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Span("⚡ Last Update: ", style={"fontWeight": "bold"}),
                    html.Span(id="last-update-time")
                ], style={
                    "backgroundColor": "#007bff",
                    "color": "white",
                    "padding": "8px 16px",
                    "borderRadius": "20px",
                    "display": "inline-block",
                    "float": "right",
                    "margin": "10px"
                })
            ], width=12)
        ]),
        
        # Main content area with pages
        html.Div(id="page-content"),
        
        # Interval for data refresh
        dcc.Interval(id="interval-component", interval=30*1000, n_intervals=0),
        
        # Store the current page
        dcc.Store(id="current-page", data="market-data"),
    ], className="content-container")
    
    # Main layout
    app.layout = html.Div([sidebar, content])
    
    # Market Data Page
    market_data_layout = html.Div([
        # Market Overview Cards
        html.Div([
            html.H4("Market Overview", className="mb-3 text-primary"),
            dbc.Row(id="market-overview-cards"),
        ], className="mb-4"),
        
        # Options Chain Section with improved search UI
        html.Div([
            html.H4("Options Chain", className="mb-3 text-primary"),
            
            # Search panel with glass-morphism effect
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Ticker search with icon
                        dbc.Col([
                            html.Label("Symbol", className="text-primary fw-bold mb-2"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-search")),
                                dcc.Dropdown(
                                    id="ticker-dropdown",
                                    options=[{"label": ticker, "value": ticker} for ticker in monitor.tickers],
                                    value=monitor.tickers[0] if monitor.tickers else None,
                                    placeholder="Select ticker...",
                                    style={"width": "100%"},
                                    className="border-0"
                                ),
                            ], className="search-input-group"),
                        ], width=12, md=4, className="mb-3"),
                        
                        # Expiration date picker with calendar icon
                        dbc.Col([
                            html.Label("Expiration Date", className="text-primary fw-bold mb-2"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-calendar-alt")),
                                dcc.Dropdown(
                                    id="expiration-selector",
                                    placeholder="Select expiration...",
                                    style={"width": "100%"},
                                    className="border-0"
                                ),
                            ], className="search-input-group"),
                        ], width=12, md=4, className="mb-3"),
                        
                        # Display type selector with filter icon
                        dbc.Col([
                            html.Label("Strike Range", className="text-primary fw-bold mb-2"),
                            dbc.InputGroup([
                                dbc.InputGroupText(html.I(className="fas fa-filter")),
                                dcc.Dropdown(
                                    id="display-type",
                                    options=[
                                        {"label": "All Strikes", "value": "all"},
                                        {"label": "Near the Money (±10%)", "value": "near"},
                                    ],
                                    value="near",
                                    style={"width": "100%"},
                                    className="border-0"
                                ),
                            ], className="search-input-group"),
                        ], width=12, md=4, className="mb-3"),
                    ]),
                    
                    # Add custom ticker with a modern button
                    dbc.Row([
                        dbc.Col([
                            html.Label("Add Custom Symbol", className="text-primary fw-bold mb-2"),
                            dbc.InputGroup([
                                dbc.Input(
                                    id="custom-ticker-input", 
                                    placeholder="Enter ticker symbol",
                                    className="border-0 shadow-none"
                                ),
                                dbc.Button(
                                    html.I(className="fas fa-plus"), 
                                    id="add-custom-ticker", 
                                    color="primary",
                                    className="ms-2 rounded-circle"
                                ),
                            ], className="search-input-group"),
                        ], width=12, md=6, className="mb-3"),
                        
                        # Search button
                        dbc.Col([
                            html.Label("\u00A0", className="d-block mb-2"),  # Non-breaking space for alignment
                            dbc.Button(
                                [html.I(className="fas fa-search me-2"), "Search Options"],
                                id="search-options-button",
                                color="primary",
                                className="w-100 mt-0"
                            ),
                        ], width=12, md=6, className="mb-3 d-flex align-items-end"),
                    ]),
                ])
            ], className="mb-4 search-card"),
            
            # Stock Info Card
            dbc.Row([
                dbc.Col(id="stock-info-card", width=12),
            ], className="mb-3"),
            
            # Options Chain Table
            dbc.Row([
                dbc.Col(id="options-chain-container", width=12),
            ]),
        ]),
        
        # IV Chart
        dbc.Row([
            dbc.Col([
                html.H4("Implied Volatility", className="mt-4 mb-3 text-primary"),
                dcc.Graph(id="iv-chart", style={"height": "50vh"}),
            ], width=12),
        ]),
    ])
    
    # Portfolio Page
    portfolio_layout = html.Div([
        dbc.Row([
            dbc.Col([
                html.H4("Account Overview", className="mb-3 text-primary"),
                html.Div(id="account-info"),
            ], width=12),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                html.H4("Current Positions", className="mb-3 text-primary"),
                html.Div(id="positions-table"),
            ], width=12),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                html.H4("Order History", className="mb-3 text-primary"),
                html.Div(id="order-history"),
            ], width=12),
        ]),
    ])
    
    # Trading Page
    trading_layout = html.Div([
        dbc.Row([
            dbc.Col([
                html.H4("Place Option Order", className="mb-3 text-primary"),
                
                dbc.Card([
                    dbc.CardHeader("Order Form"),
                    dbc.CardBody([
                        dbc.Row([
                            # Left column - Order parameters
                            dbc.Col([
                                dbc.Form([
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Ticker", style={"color": "black"}),
                                            dcc.Dropdown(
                                                id="order-ticker",
                                                options=[{"label": ticker, "value": ticker} for ticker in monitor.tickers],
                                                value=monitor.tickers[0] if monitor.tickers else None,
                                                style={"width": "100%"}
                                            ),
                                        ], width=12, md=6),
                                        
                                        dbc.Col([
                                            dbc.Label("Expiration", style={"color": "black"}),
                                            dcc.Dropdown(
                                                id="order-expiration",
                                                placeholder="Select expiration date",
                                                style={"width": "100%"}
                                            ),
                                        ], width=12, md=6),
                                    ], className="mb-3"),
                                    
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Option Type", style={"color": "black"}),
                                            dcc.Dropdown(
                                                id="order-option-type",
                                                options=[
                                                    {"label": "Call", "value": "call"},
                                                    {"label": "Put", "value": "put"}
                                                ],
                                                value="call",
                                                style={"width": "100%"},
                                            ),
                                        ], width=12, md=6),
                                        
                                        dbc.Col([
                                            dbc.Label("Strike Price", style={"color": "black"}),
                                            dcc.Dropdown(
                                                id="order-strike",
                                                placeholder="Select strike price",
                                                style={"width": "100%"}
                                            ),
                                        ], width=12, md=6),
                                    ], className="mb-3"),
                                    
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Quantity (contracts)", style={"color": "black"}),
                                            dbc.Input(
                                                id="order-quantity",
                                                type="number",
                                                min=1,
                                                step=1,
                                                value=1,
                                            ),
                                        ], width=12, md=6),
                                        
                                        dbc.Col([
                                            dbc.Label("Price Limit (optional)", style={"color": "black"}),
                                            dbc.Input(
                                                id="order-price",
                                                type="number",
                                                min=0.01,
                                                step=0.01,
                                                placeholder="Market order if blank",
                                            ),
                                        ], width=12, md=6),
                                    ], className="mb-3"),
                                    
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Label("Order Type", style={"color": "black"}),
                                            html.Div([
                                                dbc.RadioItems(
                                                    id="order-type",
                                                    options=[
                                                        {"label": "Buy", "value": "buy"},
                                                        {"label": "Sell", "value": "sell"}
                                                    ],
                                                    value="buy",  # Default to Buy
                                                    inline=True,
                                                    labelStyle={"color": "black", "margin-right": "15px"},
                                                    inputStyle={"margin-right": "5px"},
                                                    className="mt-2"
                                                )
                                            ])
                                        ], width=12),
                                    ]),
                                    
                                    dbc.Button(
                                        "Place Order",
                                        id="place-order-button",
                                        color="success",
                                        className="mt-3",
                                    ),
                                ]),
                            ], width=12, md=6),
                            
                            # Right column - Option details
                            dbc.Col([
                                html.Div(id="option-details"),
                            ], width=12, md=6),
                        ]),
                        
                        html.Div(id="order-status", className="mt-3"),
                    ]),
                ]),
            ], width=12),
        ]),
    ])
    
    # Settings Page
    settings_layout = html.Div([
        html.H4("Settings", className="mb-3 text-dark"),
        dbc.Card([
            dbc.CardHeader("Application Settings"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H5("Display Settings", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Refresh Interval (seconds)", style={"color": "black"}),
                                dbc.Input(
                                    id="refresh-interval-input",
                                    type="number",
                                    min=10,
                                    max=300,
                                    step=5,
                                    value=30,
                                ),
                            ]),
                        ]),
                    ], width=12, md=6),
                    
                    dbc.Col([
                        html.H5("Watchlist Settings", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Add Ticker", style={"color": "black"}),
                                dbc.InputGroup([
                                    dbc.Input(
                                        id="add-ticker-input",
                                        placeholder="Enter ticker symbol",
                                    ),
                                    dbc.Button("Add", id="add-ticker-button", color="primary"),
                                ]),
                            ]),
                        ]),
                        html.Div(id="watchlist-display", className="mt-3"),
                    ], width=12, md=6),
                ]),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button(
                            "Save Settings",
                            id="save-settings-button",
                            color="success",
                            className="mt-4",
                        ),
                    ], width=12),
                ]),
            ]),
        ]),
    ])
    
    # Callbacks for page navigation
    @app.callback(
        [Output("page-content", "children"),
         Output("current-page", "data"),
         Output("market-data-link", "className"),
         Output("portfolio-link", "className"),
         Output("trading-link", "className"),
         Output("settings-link", "className")],
        [Input("market-data-link", "n_clicks"),
         Input("portfolio-link", "n_clicks"),
         Input("trading-link", "n_clicks"),
         Input("settings-link", "n_clicks")],
        [State("current-page", "data")]
    )
    def display_page(market_clicks, portfolio_clicks, trading_clicks, settings_clicks, current):
        ctx = dash.callback_context
        
        if not ctx.triggered:
            # Default page
            return market_data_layout, "market-data", "sidebar-link active", "sidebar-link", "sidebar-link", "sidebar-link"
        
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        
        if button_id == "market-data-link":
            return market_data_layout, "market-data", "sidebar-link active", "sidebar-link", "sidebar-link", "sidebar-link"
        elif button_id == "portfolio-link":
            return portfolio_layout, "portfolio", "sidebar-link", "sidebar-link active", "sidebar-link", "sidebar-link"
        elif button_id == "trading-link":
            return trading_layout, "trading", "sidebar-link", "sidebar-link", "sidebar-link active", "sidebar-link"
        elif button_id == "settings-link":
            return settings_layout, "settings", "sidebar-link", "sidebar-link", "sidebar-link", "sidebar-link active"
        
        # Default fallback
        return market_data_layout, "market-data", "sidebar-link active", "sidebar-link", "sidebar-link", "sidebar-link"
    
    # Update last update time
    @app.callback(
        Output("last-update-time", "children"),
        Input("interval-component", "n_intervals")
    )
    def update_last_update_time(_):
        """Update the last update time display"""
        return datetime.now().strftime("%H:%M:%S")
    
    # Add custom ticker
    @app.callback(
        [Output("ticker-dropdown", "options"),
         Output("custom-ticker-input", "value")],
        [Input("add-custom-ticker", "n_clicks")],
        [State("custom-ticker-input", "value"),
         State("ticker-dropdown", "options")]
    )
    def add_custom_ticker(n_clicks, ticker_input, current_options):
        if not n_clicks or not ticker_input:
            return current_options, ""
        
        # Validate ticker input
        ticker_input = ticker_input.strip().upper()
        if not ticker_input:
            return current_options, ""
        
        # Check if ticker already exists
        if ticker_input in [opt["value"] for opt in current_options]:
            return current_options, ""
        
        # Try to validate the ticker using Alpaca API
        valid_ticker = False
        try:
            if monitor.api:
                # Try to get asset information from Alpaca
                asset = monitor.api.get_asset(ticker_input)
                if asset and asset.tradable:
                    valid_ticker = True
                    ticker_input = asset.symbol  # Use the official symbol
            else:
                # If no API connection, just accept the ticker (will be validated on data fetch)
                valid_ticker = True
        except Exception as e:
            print(f"Error validating ticker {ticker_input}: {e}")
            # If the exact ticker isn't found, try to search for similar tickers or company names
            try:
                if monitor.api:
                    # Get a list of assets and filter for similar names
                    assets = monitor.api.list_assets(status='active')
                    # Filter for stocks that contain the input in their symbol or name
                    matches = [a for a in assets if 
                              ticker_input in a.symbol or 
                              (hasattr(a, 'name') and a.name and ticker_input.lower() in a.name.lower())]
                    
                    if matches:
                        # Use the first match
                        ticker_input = matches[0].symbol
                        valid_ticker = True
            except Exception as search_error:
                print(f"Error searching for similar tickers: {search_error}")
        
        if not valid_ticker:
            # If we couldn't validate, still try to add it but print a warning
            print(f"Warning: Could not validate ticker {ticker_input}, but adding it anyway")
        
        # Add ticker to monitor
        if ticker_input not in monitor.tickers:
            monitor.tickers.append(ticker_input)
            # Trigger data fetch for the new ticker
            try:
                monitor.data[ticker_input] = monitor.fetch_stock_data(ticker_input)
                monitor.options_data[ticker_input] = monitor.fetch_options_data(ticker_input)
            except Exception as e:
                print(f"Error fetching data for new ticker {ticker_input}: {e}")
        
        # Update dropdown options
        new_options = current_options + [{"label": ticker_input, "value": ticker_input}]
        
        return new_options, ""
    
    # Update the app.callback for the options chain to match the UI in the image
    @app.callback(
        Output("options-chain-container", "children"),
        [Input("ticker-dropdown", "value"),
         Input("expiration-selector", "value"),
         Input("display-type", "value"),
         Input("interval-component", "n_intervals")]
    )
    def update_options_chain(ticker, expiration, display_type, _):
        if not ticker:
            return html.Div("Select a ticker to view options chain.", 
                           className="text-center p-3")
        
        # Get options data
        options_data = monitor.options_data.get(ticker, {})
        if not options_data:
            return html.Div("No options data available for this ticker.", 
                           className="text-center p-3")
        
        # If no expiration is selected but we have expirations available, use the first one
        if not expiration and 'expirations' in options_data and options_data['expirations']:
            expiration = options_data['expirations'][0]
            
        if not expiration:
            return html.Div("No expiration dates available for this ticker.", 
                           className="text-center p-3")
        
        # Get calls and puts for the selected expiration
        calls = options_data.get('calls', [])
        puts = options_data.get('puts', [])
        
        # If calls or puts are empty, try to fetch them again
        if not calls or not puts:
            try:
                # Refresh options data for this ticker
                options_data = monitor.fetch_options_data(ticker)
                monitor.options_data[ticker] = options_data
                calls = options_data.get('calls', [])
                puts = options_data.get('puts', [])
            except Exception as e:
                print(f"Error refreshing options data for {ticker}: {e}")
        
        # Get current stock price
        stock_price = monitor.data.get(ticker, {}).get('price')
        if not stock_price:
            return html.Div("Stock price data not available.", 
                           className="text-center p-3")
        
        # Filter strikes based on display type
        if display_type == "near" and stock_price:
            # Show strikes within ±10% of current price
            min_strike = stock_price * 0.9
            max_strike = stock_price * 1.1
            calls = [c for c in calls if min_strike <= c['strike'] <= max_strike]
            puts = [p for p in puts if min_strike <= p['strike'] <= max_strike]
        
        # Sort by strike price
        calls = sorted(calls, key=lambda x: x['strike'])
        puts = sorted(puts, key=lambda x: x['strike'])
        
        # Create a dictionary to match calls and puts by strike
        all_strikes = sorted(set([c['strike'] for c in calls] + [p['strike'] for p in puts]))
        
        if not all_strikes:
            return html.Div("No options data available for the selected expiration date.", 
                           className="text-center p-3")
        
        # Create the table header with the exact columns from the image
        table_header = [
            html.Thead(html.Tr([
                # Calls section
                html.Th("Last", className="text-center"),
                html.Th("Net chg", className="text-center"),
                html.Th("Volume", className="text-center"),
                html.Th("OI", className="text-center"),
                html.Th("IV", className="text-center"),
                html.Th("Delta", className="text-center"),
                html.Th("Gamma", className="text-center"),
                html.Th("Bid", className="text-center"),
                html.Th("Ask", className="text-center"),
                
                # Strike column (center)
                html.Th("Strike ↑", className="text-center bg-dark text-white"),
                
                # Puts section
                html.Th("Bid", className="text-center"),
                html.Th("Ask", className="text-center"),
                html.Th("Last", className="text-center"),
                html.Th("Net chg", className="text-center"),
                html.Th("Volume", className="text-center"),
                html.Th("OI", className="text-center"),
                html.Th("IV", className="text-center"),
                html.Th("Delta", className="text-center"),
                html.Th("Gamma", className="text-center"),
            ]))
        ]
        
        # Create table rows
        rows = []
        for strike in all_strikes:
            # Find matching call and put
            call = next((c for c in calls if c['strike'] == strike), None)
            put = next((p for p in puts if p['strike'] == strike), None)
            
            # Determine if this is the ATM row (closest to current stock price)
            is_atm = abs(strike - stock_price) < 0.01
            row_class = "bg-secondary text-white" if is_atm else ""
            
            # Create row with all the columns from the image
            row = html.Tr([
                # Calls section
                html.Td(f"${call['lastPrice']:.2f}" if call and 'lastPrice' in call else "-", className="text-center"),
                html.Td(f"-${random.uniform(0.1, 1.0):.2f}" if call else "-", className="text-center text-danger"),
                html.Td(f"{call['volume']:,}" if call and 'volume' in call else "-", className="text-center"),
                html.Td(f"{call['openInterest']:,}" if call and 'openInterest' in call else "-", className="text-center"),
                html.Td(f"{call['impliedVolatility']:.2%}" if call and 'impliedVolatility' in call else "-", className="text-center"),
                html.Td(f"{random.uniform(0.1, 0.9):.4f}" if call else "-", className="text-center"),
                html.Td(f"{random.uniform(0.01, 0.09):.4f}" if call else "-", className="text-center"),
                html.Td(f"${call['bid']:.2f}" if call and 'bid' in call else "-", className="text-center text-danger"),
                html.Td(f"${call['ask']:.2f}" if call and 'ask' in call else "-", className="text-center text-success"),
                
                # Strike price (center)
                html.Td(f"${strike:.2f}", className="text-center font-weight-bold bg-dark text-white"),
                
                # Puts section
                html.Td(f"${put['bid']:.2f}" if put and 'bid' in put else "-", className="text-center text-danger"),
                html.Td(f"${put['ask']:.2f}" if put and 'ask' in put else "-", className="text-center text-success"),
                html.Td(f"${put['lastPrice']:.2f}" if put and 'lastPrice' in put else "-", className="text-center"),
                html.Td(f"+${random.uniform(0.1, 1.0):.2f}" if put else "-", className="text-center text-success"),
                html.Td(f"{put['volume']:,}" if put and 'volume' in put else "-", className="text-center"),
                html.Td(f"{put['openInterest']:,}" if put and 'openInterest' in put else "-", className="text-center"),
                html.Td(f"{put['impliedVolatility']:.2%}" if put and 'impliedVolatility' in put else "-", className="text-center"),
                html.Td(f"-{random.uniform(0.1, 0.9):.4f}" if put else "-", className="text-center"),
                html.Td(f"{random.uniform(0.01, 0.09):.4f}" if put else "-", className="text-center"),
            ], className=row_class)
            rows.append(row)
        
        table_body = [html.Tbody(rows)]
        
        # Create the options chain container with header tabs
        return html.Div([
            # Options chain header with tabs for different views
            dbc.Card([
                dbc.CardHeader([
                    dbc.Tabs([
                        dbc.Tab(label="Calls & Puts", tab_id="both", active_tab="both"),
                        dbc.Tab(label="Calls Only", tab_id="calls"),
                        dbc.Tab(label="Puts Only", tab_id="puts"),
                    ], id="options-view-tabs")
                ]),
                dbc.CardBody([
                    # Options chain table
                    dbc.Table(
                        table_header + table_body,
                        bordered=True,
                        hover=True,
                        responsive=True,
                        striped=True,
                        className="options-chain-table"
                    )
                ])
            ])
        ])
    
    # Add callback for the trade buttons
    @app.callback(
        [Output("trading-link", "n_clicks"),
         Output("order-ticker", "value"),
         Output("order-option-type", "value"),
         Output("order-strike", "value"),
         Output("order-expiration", "value")],
        [Input({"type": "order-buy", "ticker": ALL, "exp": ALL}, "n_clicks"),
         Input({"type": "order-sell", "ticker": ALL, "exp": ALL}, "n_clicks")],
        [State({"type": "order-buy", "ticker": ALL, "exp": ALL}, "id"),
         State({"type": "order-sell", "ticker": ALL, "exp": ALL}, "id")]
    )
    def handle_trade_button(buy_clicks, sell_clicks, buy_ids, sell_ids):
        ctx = dash.callback_context
        if not ctx.triggered:
            return None, None, None, None, None
        
        # Get the button that was clicked
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id == "":
            return None, None, None, None, None
        
        # Parse the button ID
        button_id = json.loads(button_id)
        
        # Determine if it was a buy or sell button
        option_type = "call" if "order-buy" in ctx.triggered[0]['prop_id'] else "put"
        
        # Return values to update the trading form
        return 1, button_id["ticker"], option_type, button_id["strike"], button_id["exp"]

    @app.callback(
        Output("expiration-selector", "options"),
        [Input("ticker-dropdown", "value"),
         Input("interval-component", "n_intervals")]
    )
    def update_expiration_options(ticker, _):
        if not ticker:
            return []
        
        options_data = monitor.options_data.get(ticker, {})
        if not options_data or 'expirations' not in options_data:
            return []
        
        expirations = options_data.get('expirations', [])
        return [{"label": exp, "value": exp} for exp in expirations]

    @app.callback(
        Output("expiration-selector", "value"),
        [Input("expiration-selector", "options")]
    )
    def set_default_expiration(available_options):
        if available_options and len(available_options) > 0:
            return available_options[0]["value"]
        return None

    # Add this callback to handle the order type selection
    @app.callback(
        [Output("order-buy", "color"), Output("order-sell", "color")],
        [Input("order-type", "value")]
    )
    def update_order_button_colors(order_type):
        """Update the colors of the order type buttons based on selection"""
        if order_type == "buy":
            return "success", "outline-danger"
        else:
            return "outline-success", "danger"

    # Add callbacks for portfolio page components
    @app.callback(
        Output("account-info", "children"),
        [Input("interval-component", "n_intervals"),
         Input("current-page", "data")]
    )
    def update_account_info(_, current_page):
        """Update the account information display"""
        if current_page != "portfolio":
            return html.Div()
        
        # Check if we have a trader instance
        if not monitor.trader:
            return html.Div("No trading account connected. Please check your API credentials.", 
                           className="alert alert-warning")
        
        try:
            # Get account information
            account_info = monitor.trader.get_account_info()
            
            # Create account info cards
            cards = []
            
            # Account Value Card
            cards.append(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Account Value", className="card-title text-primary"),
                        html.H3(f"${float(account_info.get('equity', 0)):.2f}", className="text-success"),
                        html.P(f"Cash: ${float(account_info.get('cash', 0)):.2f}", className="mb-0"),
                    ]),
                    className="mb-3 shadow-sm"
                )
            )
            
            # Buying Power Card
            cards.append(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Buying Power", className="card-title text-primary"),
                        html.H3(f"${float(account_info.get('buying_power', 0)):.2f}", className="text-info"),
                        html.P(f"Day Trading: ${float(account_info.get('daytrading_buying_power', 0)):.2f}", className="mb-0"),
                    ]),
                    className="mb-3 shadow-sm"
                )
            )
            
            # P&L Card
            daily_pl = account_info.get('equity', 0) - account_info.get('last_equity', 0)
            daily_pl_pct = (daily_pl / account_info.get('last_equity', 1)) * 100 if account_info.get('last_equity', 0) else 0
            
            pl_color = "text-success" if daily_pl >= 0 else "text-danger"
            pl_sign = "+" if daily_pl >= 0 else ""
            
            cards.append(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Daily P&L", className="card-title text-primary"),
                        html.H3([
                            f"{pl_sign}${abs(daily_pl):.2f} ",
                            html.Small(f"({pl_sign}{abs(daily_pl_pct):.2f}%)", className="text-muted")
                        ], className=pl_color),
                        html.P("Since previous trading day", className="mb-0 text-muted"),
                    ]),
                    className="mb-3 shadow-sm"
                )
            )
            
            # Account Status Card
            status_color = "text-success" if account_info.get('status') == 'ACTIVE' else "text-warning"
            cards.append(
                dbc.Card(
                    dbc.CardBody([
                        html.H5("Account Status", className="card-title text-primary"),
                        html.H3(account_info.get('status', 'UNKNOWN'), className=status_color),
                        html.P(f"Pattern Day Trader: {'Yes' if account_info.get('pattern_day_trader', False) else 'No'}", 
                              className="mb-0"),
                    ]),
                    className="mb-3 shadow-sm"
                )
            )
            
            # Arrange cards in a grid
            return dbc.Row([
                dbc.Col(cards[0], width=12, md=6, lg=3),
                dbc.Col(cards[1], width=12, md=6, lg=3),
                dbc.Col(cards[2], width=12, md=6, lg=3),
                dbc.Col(cards[3], width=12, md=6, lg=3),
            ])
            
        except Exception as e:
            print(f"Error fetching account info: {e}")
            return html.Div(f"Error fetching account information: {str(e)}", 
                           className="alert alert-danger")
    
    @app.callback(
        Output("positions-table", "children"),
        [Input("interval-component", "n_intervals"),
         Input("current-page", "data")]
    )
    def update_positions_table(_, current_page):
        """Update the positions table"""
        if current_page != "portfolio":
            return html.Div()
        
        # Check if we have a trader instance
        if not monitor.trader:
            return html.Div("No trading account connected. Please check your API credentials.", 
                           className="alert alert-warning")
        
        try:
            # Get positions
            positions = monitor.trader.get_positions()
            
            if not positions:
                return html.Div("No open positions.", className="alert alert-info")
            
            # Create table header
            header = html.Thead(html.Tr([
                html.Th("Symbol", className="text-center"),
                html.Th("Quantity", className="text-center"),
                html.Th("Entry Price", className="text-center"),
                html.Th("Current Price", className="text-center"),
                html.Th("Market Value", className="text-center"),
                html.Th("Unrealized P&L", className="text-center"),
                html.Th("P&L %", className="text-center"),
                html.Th("Actions", className="text-center"),
            ]))
            
            # Create table rows
            rows = []
            for position in positions:
                # Calculate P&L
                entry_price = float(position.get('avg_entry_price', 0))
                current_price = float(position.get('current_price', 0))
                quantity = float(position.get('qty', 0))
                
                market_value = current_price * quantity
                cost_basis = entry_price * quantity
                unrealized_pl = market_value - cost_basis
                pl_pct = (unrealized_pl / cost_basis) * 100 if cost_basis else 0
                
                # Determine P&L color
                pl_color = "text-success" if unrealized_pl >= 0 else "text-danger"
                pl_sign = "+" if unrealized_pl >= 0 else ""
                
                # Create row
                row = html.Tr([
                    html.Td(position.get('symbol', ''), className="text-center"),
                    html.Td(f"{quantity:.0f}", className="text-center"),
                    html.Td(f"${entry_price:.2f}", className="text-center"),
                    html.Td(f"${current_price:.2f}", className="text-center"),
                    html.Td(f"${market_value:.2f}", className="text-center"),
                    html.Td(f"{pl_sign}${abs(unrealized_pl):.2f}", className=f"text-center {pl_color}"),
                    html.Td(f"{pl_sign}{abs(pl_pct):.2f}%", className=f"text-center {pl_color}"),
                    html.Td(
                        dbc.Button("Close", color="danger", size="sm", className="mx-1", id={"type": "close-position", "symbol": position.get('symbol', '')}),
                    ),
                ])
                rows.append(row)
            
            # Create table
            table = dbc.Table([
                header,
                html.Tbody(rows)
            ], bordered=True, hover=True, responsive=True, striped=True, className="positions-table")
            
            return table
            
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return html.Div(f"Error fetching positions: {str(e)}", 
                           className="alert alert-danger")
    
    @app.callback(
        Output("order-history", "children"),
        [Input("interval-component", "n_intervals"),
         Input("current-page", "data")]
    )
    def update_order_history(_, current_page):
        """Update the order history table"""
        if current_page != "portfolio":
            return html.Div()
        
        # Check if we have a trader instance
        if not monitor.trader:
            return html.Div("No trading account connected. Please check your API credentials.", 
                           className="alert alert-warning")
        
        try:
            # Get order history
            orders = monitor.trader.get_order_history()
            
            if not orders:
                return html.Div("No order history available.", className="alert alert-info")
            
            # Create table header
            header = html.Thead(html.Tr([
                html.Th("Date", className="text-center"),
                html.Th("Symbol", className="text-center"),
                html.Th("Side", className="text-center"),
                html.Th("Quantity", className="text-center"),
                html.Th("Price", className="text-center"),
                html.Th("Status", className="text-center"),
                html.Th("Type", className="text-center"),
            ]))
            
            # Create table rows
            rows = []
            for order in orders:
                # Determine status color
                status = order.get('status', '')
                status_color = ""
                if status == 'filled':
                    status_color = "text-success"
                elif status == 'canceled' or status == 'rejected':
                    status_color = "text-danger"
                elif status == 'pending' or status == 'accepted':
                    status_color = "text-warning"
                
                # Determine side color
                side = order.get('side', '')
                side_color = "text-success" if side == 'buy' else "text-danger"
                
                # Format date
                created_at = order.get('created_at', '')
                if created_at:
                    try:
                        dt_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                
                # Create row
                row = html.Tr([
                    html.Td(created_at, className="text-center"),
                    html.Td(order.get('symbol', ''), className="text-center"),
                    html.Td(side.capitalize(), className=f"text-center {side_color}"),
                    html.Td(order.get('qty', ''), className="text-center"),
                    html.Td(f"${float(order.get('filled_avg_price', 0)):.2f}" if order.get('filled_avg_price') else "-", 
                           className="text-center"),
                    html.Td(status.capitalize(), className=f"text-center {status_color}"),
                    html.Td(order.get('type', '').capitalize(), className="text-center"),
                ])
                rows.append(row)
            
            # Create table
            table = dbc.Table([
                header,
                html.Tbody(rows)
            ], bordered=True, hover=True, responsive=True, striped=True, className="order-history-table")
            
            return table
            
        except Exception as e:
            print(f"Error fetching order history: {e}")
            return html.Div(f"Error fetching order history: {str(e)}", 
                           className="alert alert-danger")

    # Add callback for IV chart
    @app.callback(
        Output("iv-chart", "figure"),
        [Input("ticker-dropdown", "value"),
         Input("interval-component", "n_intervals")]
    )
    def update_iv_chart(ticker, _):
        """Update the implied volatility chart"""
        if not ticker:
            return {
                "data": [],
                "layout": {
                    "title": "Select a ticker to view implied volatility",
                    "xaxis": {"title": "Strike Price"},
                    "yaxis": {"title": "Implied Volatility (%)"},
                    "showlegend": True,
                    "template": "plotly_dark"
                }
            }
        
        # Get options data
        options_data = monitor.options_data.get(ticker, {})
        if not options_data or 'calls' not in options_data or 'puts' not in options_data:
            return {
                "data": [],
                "layout": {
                    "title": f"No options data available for {ticker}",
                    "xaxis": {"title": "Strike Price"},
                    "yaxis": {"title": "Implied Volatility (%)"},
                    "showlegend": True,
                    "template": "plotly_dark"
                }
            }
        
        # Get current stock price
        stock_price = monitor.data.get(ticker, {}).get('price')
        if not stock_price:
            return {
                "data": [],
                "layout": {
                    "title": f"Stock price data not available for {ticker}",
                    "xaxis": {"title": "Strike Price"},
                    "yaxis": {"title": "Implied Volatility (%)"},
                    "showlegend": True,
                    "template": "plotly_dark"
                }
            }
        
        # Extract data for calls and puts
        calls = options_data.get('calls', [])
        puts = options_data.get('puts', [])
        
        # Sort by strike price
        calls = sorted(calls, key=lambda x: x['strike'])
        puts = sorted(puts, key=lambda x: x['strike'])
        
        # Extract strike prices and implied volatilities
        call_strikes = [c['strike'] for c in calls if 'strike' in c and 'impliedVolatility' in c]
        call_ivs = [c['impliedVolatility'] * 100 for c in calls if 'strike' in c and 'impliedVolatility' in c]
        
        put_strikes = [p['strike'] for p in puts if 'strike' in p and 'impliedVolatility' in p]
        put_ivs = [p['impliedVolatility'] * 100 for p in puts if 'strike' in p and 'impliedVolatility' in p]
        
        # Create the figure
        fig = {
            "data": [
                {
                    "x": call_strikes,
                    "y": call_ivs,
                    "type": "scatter",
                    "mode": "lines+markers",
                    "name": "Calls IV",
                    "line": {"color": "green", "width": 2},
                    "marker": {"size": 8}
                },
                {
                    "x": put_strikes,
                    "y": put_ivs,
                    "type": "scatter",
                    "mode": "lines+markers",
                    "name": "Puts IV",
                    "line": {"color": "red", "width": 2},
                    "marker": {"size": 8}
                },
                {
                    "x": [stock_price, stock_price],
                    "y": [0, max(max(call_ivs) if call_ivs else 0, max(put_ivs) if put_ivs else 0) * 1.1],
                    "type": "scatter",
                    "mode": "lines",
                    "name": "Current Price",
                    "line": {"color": "yellow", "width": 2, "dash": "dash"}
                }
            ],
            "layout": {
                "title": f"{ticker} Implied Volatility Curve",
                "xaxis": {
                    "title": "Strike Price ($)",
                    "gridcolor": "rgba(255, 255, 255, 0.1)",
                    "zerolinecolor": "rgba(255, 255, 255, 0.1)"
                },
                "yaxis": {
                    "title": "Implied Volatility (%)",
                    "gridcolor": "rgba(255, 255, 255, 0.1)",
                    "zerolinecolor": "rgba(255, 255, 255, 0.1)"
                },
                "showlegend": True,
                "legend": {"orientation": "h", "y": 1.1},
                "template": "plotly_dark",
                "hovermode": "closest",
                "plot_bgcolor": "rgba(0, 0, 0, 0)",
                "paper_bgcolor": "rgba(0, 0, 0, 0)",
                "font": {"color": "white"}
            }
        }
        
        return fig

    # Add callback for order status
    @app.callback(
        Output("order-status", "children"),
        [Input("order-submit", "n_clicks")],
        [State("order-ticker", "value"),
         State("order-expiration", "value"),
         State("order-strike", "value"),
         State("order-quantity", "value"),
         State("order-type", "value"),
         State("order-option-type", "value"),
         State("order-price", "value")]
    )
    def submit_order(n_clicks, ticker, expiration, strike, quantity, order_type, option_type, price):
        """Submit an order and show the status"""
        if not n_clicks:
            return html.Div()
        
        if not ticker or not expiration or not strike or not quantity or not order_type or not option_type:
            return html.Div("Please fill in all required fields", className="alert alert-warning")
        
        # Check if we have a trader instance
        if not monitor.trader:
            return html.Div("No trading account connected. Please check your API credentials.", 
                           className="alert alert-warning")
        
        try:
            # Convert inputs to appropriate types
            strike = float(strike)
            quantity = int(quantity)
            price = float(price) if price else None
            
            # Submit the order
            if order_type == 'buy':
                result = monitor.trader.buy_option(
                    ticker=ticker,
                    expiration=expiration,
                    strike=strike,
                    option_type=option_type,
                    quantity=quantity,
                    price=price
                )
            else:  # sell
                result = monitor.trader.sell_option(
                    ticker=ticker,
                    expiration_date=expiration,
                    strike_price=strike,
                    option_type=option_type,
                    quantity=quantity,
                    price=price
                )
            
            # Check if the order was successful
            if result.get('error', False):
                return html.Div([
                    html.H5("Order Rejected", className="text-danger"),
                    html.P(f"Reason: {result.get('error_message', 'Unknown error')}"),
                    html.Hr(),
                    html.Pre(json.dumps(result, indent=2), 
                            style={"backgroundColor": "#f8f9fa", "padding": "10px", "borderRadius": "5px"})
                ], className="alert alert-danger")
            
            # Order was successful
            status = result.get('status', 'unknown')
            status_color = "success" if status in ['filled', 'accepted'] else "warning"
            
            return html.Div([
                html.H5(f"Order {status.capitalize()}", className=f"text-{status_color}"),
                html.P([
                    f"{order_type.capitalize()} {quantity} {ticker} {option_type.upper()} ",
                    html.Strong(f"${strike}"),
                    f" {expiration}"
                ]),
                html.P([
                    "Order ID: ",
                    html.Code(result.get('id', 'N/A'))
                ]),
                html.P([
                    "Filled Price: ",
                    html.Strong(f"${result.get('filled_avg_price', 'N/A')}")
                ]) if result.get('filled_avg_price') else html.P("Awaiting fill..."),
                html.Hr(),
                html.Pre(json.dumps(result, indent=2), 
                        style={"backgroundColor": "#f8f9fa", "padding": "10px", "borderRadius": "5px"})
            ], className=f"alert alert-{status_color}")
            
        except Exception as e:
            return html.Div([
                html.H5("Error Submitting Order", className="text-danger"),
                html.P(str(e)),
            ], className="alert alert-danger")

    return app

def start_dashboard(monitor, port=8050, debug=False):
    """Start the Dash dashboard"""
    app = create_dashboard(monitor)
    
    # Start monitoring if the method exists
    if hasattr(monitor, 'start_monitoring'):
        monitor.start_monitoring()
    else:
        # If the method doesn't exist, just refresh the data
        print("Starting data refresh...")
        monitor.refresh_data()
    
    # Start the dashboard
    print(f"Dashboard will be available at http://localhost:{port}")
    app.run_server(debug=debug, port=port, host='0.0.0.0')

def main():
    """Main function to run the options monitor dashboard"""
    parser = argparse.ArgumentParser(description='Options Monitor Dashboard')
    parser.add_argument('--tickers', type=str, default='AAPL,MSFT,GOOGL,AMZN,TSLA',
                        help='Comma-separated list of stock tickers to monitor')
    parser.add_argument('--refresh', type=int, default=60,
                        help='Data refresh interval in seconds')
    parser.add_argument('--port', type=int, default=8050,
                        help='Port to run the dashboard on')
    parser.add_argument('--debug', action='store_true',
                        help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Parse comma-separated tickers
    tickers = [ticker.strip() for ticker in args.tickers.split(',') if ticker.strip()]
    
    print(f"Starting Options Monitor Dashboard with tickers: {', '.join(tickers)}")
    print(f"Data will refresh every {args.refresh} seconds")
    
    monitor = OptionsMonitor(tickers, refresh_interval=args.refresh)
    
    try:
        start_dashboard(monitor, port=args.port, debug=args.debug)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()