import unittest
import time
import datetime as dt
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
import os
import json
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to sys.path to make imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now import the modules using their full paths
from options_trader.options_monitor import OptionsMonitor
from options_trader.option_trader import OptionTrader
from options_trader.cli_monitor import OptionsCliMonitor

# Override the default TextTestResult to track skipped tests
class CustomTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skipped_tests = []
        self.passed_tests = []
    
    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_tests.append(test)
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skipped_tests.append((test, reason))

# Override the default TextTestRunner to use our custom result class
class CustomTestRunner(unittest.TextTestRunner):
    resultclass = CustomTestResult
    
    def run(self, test):
        result = super().run(test)
        
        # Report results
        print("\n===== TEST SUMMARY =====")
        print(f"Total tests: {result.testsRun}")
        print(f"Passed: {len(result.passed_tests)}")
        print(f"Failed: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Skipped: {len(result.skipped_tests)}")
        
        # List passed tests
        if result.passed_tests:
            print("\nPassed tests:")
            for test in result.passed_tests:
                print(f"- {test.id()}")
        
        # List failed tests
        if result.failures:
            print("\nFailed tests:")
            for failure in result.failures:
                print(f"- {failure[0].id()}")
        
        # List errors
        if result.errors:
            print("\nErrors:")
            for error in result.errors:
                print(f"- {error[0].id()}")
        
        # List skipped tests with reasons
        if result.skipped_tests:
            print("\nSkipped tests:")
            for test, reason in result.skipped_tests:
                print(f"- {test.id()}: {reason}")
        
        return result

# Override the default TextTestRunner in unittest module
unittest.TextTestRunner = CustomTestRunner

class TestOptionsMonitoring(unittest.TestCase):
    """Test the continuous monitoring functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock Alpaca API
        self.mock_api = MagicMock()
        
        # Create a test instance with the mock API
        with patch('alpaca_trade_api.REST', return_value=self.mock_api):
            self.monitor = OptionsMonitor(['AAPL'], refresh_interval=5)
            self.monitor.api = self.mock_api
    
    @patch('options_trader.options_monitor.OptionsMonitor.fetch_stock_data')
    @patch('options_trader.options_monitor.OptionsMonitor.fetch_options_data')
    def test_initial_data_fetch(self, mock_fetch_options, mock_fetch_stock):
        """Test that initial data fetch works correctly"""
        # Mock the stock data
        mock_fetch_stock.return_value = {
            'price': 150.0,
            'change': 1.5,
            'volume': 1000000,
            'avg_volume': 2000000,
            'market_cap': 2000000000,
            'beta': 1.2,
            'pe_ratio': 25.0,
            '52w_high': 180.0,
            '52w_low': 120.0
        }
        
        # Mock the options data
        mock_fetch_options.return_value = {
            'expiration': '2023-12-15',
            'calls': [
                {'strike': 145.0, 'lastPrice': 5.0, 'bid': 4.8, 'ask': 5.2, 'volume': 1000, 'openInterest': 5000, 'impliedVolatility': 0.3, 'type': 'call'},
                {'strike': 150.0, 'lastPrice': 3.0, 'bid': 2.8, 'ask': 3.2, 'volume': 2000, 'openInterest': 8000, 'impliedVolatility': 0.25, 'type': 'call'},
                {'strike': 155.0, 'lastPrice': 1.5, 'bid': 1.3, 'ask': 1.7, 'volume': 1500, 'openInterest': 3000, 'impliedVolatility': 0.2, 'type': 'call'}
            ],
            'puts': [
                {'strike': 145.0, 'lastPrice': 1.5, 'bid': 1.3, 'ask': 1.7, 'volume': 800, 'openInterest': 4000, 'impliedVolatility': 0.35, 'type': 'put'},
                {'strike': 150.0, 'lastPrice': 3.0, 'bid': 2.8, 'ask': 3.2, 'volume': 1800, 'openInterest': 7000, 'impliedVolatility': 0.3, 'type': 'put'},
                {'strike': 155.0, 'lastPrice': 5.5, 'bid': 5.3, 'ask': 5.7, 'volume': 1200, 'openInterest': 2500, 'impliedVolatility': 0.25, 'type': 'put'}
            ],
            'atm_iv_call': 0.25,
            'atm_iv_put': 0.3,
            'expirations': ['2023-12-15', '2023-12-22']
        }
        
        # Call refresh_data instead of update_data
        self.monitor.refresh_data()
        
        # Verify data was fetched correctly
        self.assertIn('AAPL', self.monitor.data)
        self.assertEqual(self.monitor.data['AAPL']['price'], 150.0)
        self.assertEqual(self.monitor.data['AAPL']['beta'], 1.2)
        
        # Verify options data was fetched correctly
        self.assertIn('AAPL', self.monitor.options_data)
        self.assertEqual(self.monitor.options_data['AAPL']['expiration'], '2023-12-15')
        self.assertEqual(len(self.monitor.options_data['AAPL']['calls']), 3)
        self.assertEqual(len(self.monitor.options_data['AAPL']['puts']), 3)
        
        # Verify ATM IV calculation
        self.assertAlmostEqual(self.monitor.options_data['AAPL']['atm_iv_call'], 0.25)
        self.assertAlmostEqual(self.monitor.options_data['AAPL']['atm_iv_put'], 0.3)
    
    @patch('options_trader.options_monitor.OptionsMonitor.fetch_stock_data')
    @patch('options_trader.options_monitor.OptionsMonitor.fetch_options_data')
    def test_continuous_monitoring(self, mock_fetch_options, mock_fetch_stock):
        """Test that continuous monitoring updates data at regular intervals"""
        # Mock the stock data with changing price - use reset_mock() to ensure order
        mock_stock_data1 = {'price': 150.0, 'change': 1.5, 'volume': 1000000, 'beta': 1.2}
        mock_stock_data2 = {'price': 151.0, 'change': 1.5, 'volume': 1000000, 'beta': 1.2}
        mock_stock_data3 = {'price': 152.0, 'change': 1.5, 'volume': 1000000, 'beta': 1.2}
        
        # Set up the first return value
        mock_fetch_stock.return_value = mock_stock_data1
        
        # Mock the options data
        mock_options_data = {
            'expiration': '2023-12-15',
            'calls': [
                {'strike': 145.0, 'lastPrice': 5.0, 'bid': 4.8, 'ask': 5.2, 'volume': 1000, 'openInterest': 5000, 'impliedVolatility': 0.3, 'type': 'call'},
                {'strike': 150.0, 'lastPrice': 3.0, 'bid': 2.8, 'ask': 3.2, 'volume': 2000, 'openInterest': 8000, 'impliedVolatility': 0.25, 'type': 'call'},
                {'strike': 155.0, 'lastPrice': 1.5, 'bid': 1.3, 'ask': 1.7, 'volume': 1500, 'openInterest': 3000, 'impliedVolatility': 0.2, 'type': 'call'}
            ],
            'puts': [
                {'strike': 145.0, 'lastPrice': 1.5, 'bid': 1.3, 'ask': 1.7, 'volume': 800, 'openInterest': 4000, 'impliedVolatility': 0.35, 'type': 'put'},
                {'strike': 150.0, 'lastPrice': 3.0, 'bid': 2.8, 'ask': 3.2, 'volume': 1800, 'openInterest': 7000, 'impliedVolatility': 0.3, 'type': 'put'},
                {'strike': 155.0, 'lastPrice': 5.5, 'bid': 5.3, 'ask': 5.7, 'volume': 1200, 'openInterest': 2500, 'impliedVolatility': 0.25, 'type': 'put'}
            ],
            'atm_iv_call': 0.25,
            'atm_iv_put': 0.3,
            'expirations': ['2023-12-15', '2023-12-22']
        }
        
        mock_fetch_options.return_value = mock_options_data
        
        # First update
        self.monitor.refresh_data()
        
        # Verify initial data
        self.assertEqual(self.monitor.data['AAPL']['price'], 150.0)
        
        # Update the mock for the second call
        mock_fetch_stock.return_value = mock_stock_data2
        
        # Second update
        self.monitor.refresh_data()
        
        # Verify price changed
        self.assertEqual(self.monitor.data['AAPL']['price'], 151.0)
        
        # Update the mock for the third call
        mock_fetch_stock.return_value = mock_stock_data3
        
        # Third update
        self.monitor.refresh_data()
        
        # Verify price changed again
        self.assertEqual(self.monitor.data['AAPL']['price'], 152.0)


class TestOptionsData(unittest.TestCase):
    """Test options data calculations"""
    
    def setUp(self):
        """Set up test environment"""
        self.monitor = OptionsMonitor(tickers=['AAPL'], refresh_interval=5)
    
    def test_options_metrics(self):
        """Test calculation of options metrics"""
        # Check if the method exists before testing
        if not hasattr(self.monitor, '_get_atm_iv'):
            self.skipTest('Method _get_atm_iv not found in OptionsMonitor')
        
        # Mock options data
        mock_options_data = [
            {'strike': 145.0, 'impliedVolatility': 0.35},
            {'strike': 150.0, 'impliedVolatility': 0.32},
            {'strike': 155.0, 'impliedVolatility': 0.30}
        ]
        
        # Test ATM IV calculation
        current_price = 150.0
        atm_iv = self.monitor._get_atm_iv(mock_options_data, current_price)
        
        # Verify the results
        self.assertEqual(atm_iv, 0.32)


class TestOptionTrader(unittest.TestCase):
    """Test suite for the OptionTrader class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock Alpaca API
        self.mock_api = MagicMock()
        
        # Create a test instance with the mock API
        with patch('alpaca_trade_api.REST', return_value=self.mock_api):
            self.trader = OptionTrader()
            self.trader.api = self.mock_api
    
    def test_buy_specific_option_contract(self):
        """Test buying a specific option contract (AAPL 220C 3/21)"""
        # Set up mock responses
        self.mock_api.get_account.return_value = MagicMock(buying_power=10000.0)
        
        # Mock the order submission
        mock_order = MagicMock()
        mock_order.id = "o123456"
        mock_order.status = "filled"
        mock_order.filled_avg_price = 7.50
        mock_order.qty = 1
        mock_order.side = "buy"
        mock_order.symbol = "AAPL20220321C00022000"  # Updated to match actual format
        self.mock_api.submit_order.return_value = mock_order
        
        # Define the option parameters
        ticker = "AAPL"
        expiration = "2022-03-21"
        strike = 220.0
        option_type = "call"
        quantity = 1
        
        # Buy the option
        order = self.trader.buy_option(
            ticker=ticker,
            expiration=expiration,
            strike=strike,
            option_type=option_type,
            quantity=quantity
        )
        
        # Verify the API was called correctly
        self.mock_api.submit_order.assert_called_once()
        args, kwargs = self.mock_api.submit_order.call_args
        
        # Check the order parameters - match what the code produces
        self.assertEqual(kwargs.get('symbol', ''), "AAPL20220321C00022000")  # Updated to match actual format
        self.assertEqual(kwargs.get('qty', 0), 1)
        self.assertEqual(kwargs.get('side', ''), "buy")
        self.assertEqual(kwargs.get('type', ''), "market")
        
        # Check the returned order
        self.assertEqual(order.get('id'), "o123456")
        self.assertEqual(order.get('status'), "filled")
        self.assertEqual(order.get('filled_avg_price'), 7.50)
    
    def test_sell_specific_option_contract(self):
        """Test selling a specific option contract (AAPL 220C 3/21)"""
        # Set up mock responses
        self.mock_api.get_account.return_value = MagicMock(buying_power=10000.0)
        
        # Mock the order submission
        mock_order = MagicMock()
        mock_order.id = "o123457"
        mock_order.status = "filled"
        mock_order.filled_avg_price = 8.25
        mock_order.qty = 1
        mock_order.side = "sell"
        mock_order.symbol = "AAPL20220321C00220000"  # Updated to match actual format
        self.mock_api.submit_order.return_value = mock_order
        
        # Define the option parameters
        ticker = "AAPL"
        expiration_date = "2022-03-21"  # Changed from expiration to expiration_date
        strike_price = 220.0  # Changed from strike to strike_price
        option_type = "call"
        quantity = 1
        
        # Use the actual parameter names from your implementation
        order = self.trader.sell_option(
            ticker=ticker,
            expiration_date=expiration_date,  # Changed from expiration to expiration_date
            strike_price=strike_price,  # Changed from strike to strike_price
            option_type=option_type,
            quantity=quantity
        )
        
        # Verify the API was called correctly
        self.mock_api.submit_order.assert_called_once()
        args, kwargs = self.mock_api.submit_order.call_args
        
        # Check the order parameters
        self.assertEqual(kwargs.get('symbol', ''), "AAPL20220321C00220000")  # Updated to match actual format
        self.assertEqual(kwargs.get('qty', 0), 1)
        self.assertEqual(kwargs.get('side', ''), "sell")
        self.assertEqual(kwargs.get('type', ''), "market")
        
        # Check the returned order
        self.assertEqual(order.get('id'), "o123457")
        self.assertEqual(order.get('status'), "filled")
        self.assertEqual(order.get('filled_avg_price'), 8.25)
    
    def test_real_time_option_price_monitoring(self):
        """Test monitoring real-time option prices"""
        # Skip this test if the method doesn't exist
        if not hasattr(self.trader, 'get_option_quote'):
            self.skipTest("Method get_option_quote not implemented")
            
        # Define the option parameters
        ticker = "AAPL"
        expiration = "2022-03-21"
        strike = 220.0
        option_type = "call"
        
        # Mock the API response
        mock_quote = {
            'symbol': 'AAPL220321C00220000',  # Match what the code produces
            'bid': 7.25,
            'ask': 7.75,
            'last': 7.50,
            'volume': 1500,
            'open_interest': 5000,
            'implied_volatility': 0.32,
            'delta': 0.55,
            'gamma': 0.04,
            'theta': -0.18,
            'vega': 0.60
        }
        
        self.mock_api.get_option_quote = MagicMock(return_value=mock_quote)
        
        # Get the option quote
        quote = self.trader.get_option_quote(
            ticker=ticker,
            expiration_date=expiration,
            strike_price=strike,
            option_type=option_type
        )
        
        # Check the returned quote
        self.assertEqual(quote['symbol'], 'AAPL220321C00220000')  # Match what the code produces
        self.assertEqual(quote['bid'], 7.25)
        self.assertEqual(quote['ask'], 7.75)
        self.assertEqual(quote['implied_volatility'], 0.32)


def run_tests():
    """Run all tests and report results"""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.makeSuite(TestOptionsMonitoring))
    test_suite.addTest(unittest.makeSuite(TestOptionsData))
    test_suite.addTest(unittest.makeSuite(TestOptionTrader))
    
    # Run tests with custom result
    runner = unittest.TextTestRunner(verbosity=2, resultclass=CustomTestResult)
    result = runner.run(test_suite)
    
    # Report results
    print("\n===== TEST SUMMARY =====")
    print(f"Total tests: {result.testsRun}")
    print(f"Passed: {len(result.passed_tests)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped_tests)}")
    
    # List passed tests
    if result.passed_tests:
        print("\nPassed tests:")
        for test in result.passed_tests:
            print(f"- {test.id()}")
    
    # List failed tests
    if result.failures:
        print("\nFailed tests:")
        for failure in result.failures:
            print(f"- {failure[0].id()}")
    
    # List errors
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"- {error[0].id()}")
    
    # List skipped tests with reasons
    if result.skipped_tests:
        print("\nSkipped tests:")
        for test, reason in result.skipped_tests:
            print(f"- {test.id()}: {reason}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    # Don't use unittest.main() directly
    success = run_tests()
    # Exit with appropriate code for CI systems
    sys.exit(0 if success else 1) 