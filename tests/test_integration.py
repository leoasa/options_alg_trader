import unittest
import sys
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from options_trader.options_monitor import OptionsMonitor
from options_trader.option_trader import OptionTrader

class TestIntegration(unittest.TestCase):
    """Integration tests for the options trading system"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a mock Alpaca API
        self.mock_api = MagicMock()
        
        # Create test instances with the mock API
        with patch('alpaca_trade_api.REST', return_value=self.mock_api):
            self.trader = OptionTrader()
            self.trader.api = self.mock_api
            
            self.monitor = OptionsMonitor(['AAPL'], refresh_interval=5)
            self.monitor.api = self.mock_api
            self.monitor.trader = self.trader
    
    def test_end_to_end_option_trade(self):
        """Test an end-to-end option trade workflow"""
        # 1. Set up mock data for monitoring
        mock_stock_data = {'price': 150.0, 'change': 1.5, 'volume': 1000000}
        
        # Mock option chain data
        mock_options_data = {
            'ticker': 'AAPL',
            'expiration': '2022-03-21',
            'expirations': ['2022-03-21', '2022-04-15', '2022-05-20'],
            'calls': [
                {'strike': 220.0, 'lastPrice': 7.50, 'bid': 7.25, 'ask': 7.75, 'impliedVolatility': 0.32}
            ],
            'puts': [],
            'atm_iv_call': 0.32,
            'atm_iv_put': None
        }
        
        # 2. Mock the API responses
        with patch.object(self.monitor, 'fetch_stock_data', return_value=mock_stock_data):
            with patch.object(self.monitor, 'fetch_options_data', return_value=mock_options_data):
                # 3. Refresh the data
                self.monitor.refresh_data()
                
                # Verify the data was loaded
                self.assertEqual(self.monitor.data['AAPL']['price'], 150.0)
                self.assertEqual(self.monitor.options_data['AAPL']['calls'][0]['lastPrice'], 7.50)
        
        # 4. Set up mock order responses with specific attribute values
        mock_buy_order = MagicMock()
        mock_buy_order.id = "o123456"
        mock_buy_order.status = "filled"
        mock_buy_order.filled_avg_price = 7.50
        mock_buy_order.filled_qty = 1
        mock_buy_order.qty = 1
        mock_buy_order.side = "buy"
        mock_buy_order.symbol = "AAPL20220321C00022000"
        
        mock_sell_order = MagicMock()
        mock_sell_order.id = "o123457"
        mock_sell_order.status = "filled"
        mock_sell_order.filled_avg_price = 8.25
        mock_sell_order.filled_qty = 1
        mock_sell_order.qty = 1
        mock_sell_order.side = "sell"
        mock_sell_order.symbol = "AAPL20220321C00022000"
        
        # Convert the MagicMock objects to dictionaries for easier handling
        buy_order_dict = {
            'id': mock_buy_order.id,
            'symbol': mock_buy_order.symbol,
            'status': mock_buy_order.status,
            'side': mock_buy_order.side,
            'qty': mock_buy_order.qty,
            'filled_qty': mock_buy_order.filled_qty,
            'filled_avg_price': mock_buy_order.filled_avg_price
        }
        
        sell_order_dict = {
            'id': mock_sell_order.id,
            'symbol': mock_sell_order.symbol,
            'status': mock_sell_order.status,
            'side': mock_sell_order.side,
            'qty': mock_sell_order.qty,
            'filled_qty': mock_sell_order.filled_qty,
            'filled_avg_price': mock_sell_order.filled_avg_price
        }
        
        # Mock the API to return our dictionaries instead of MagicMock objects
        self.mock_api.submit_order.side_effect = [buy_order_dict, sell_order_dict]
        
        # 4. Execute a buy order for AAPL 220C 3/21
        buy_order = self.trader.buy_option(
            ticker="AAPL",
            expiration="2022-03-21",
            strike=220.0,
            option_type="call",
            quantity=1
        )
        
        # Verify the buy order
        self.assertEqual(buy_order['status'], "filled")
        self.assertEqual(buy_order['filled_avg_price'], 7.50)
        
        # 5. Update the option price in the monitor data
        updated_options_data = mock_options_data.copy()
        updated_options_data['calls'][0]['lastPrice'] = 8.25
        updated_options_data['calls'][0]['bid'] = 8.00
        updated_options_data['calls'][0]['ask'] = 8.50
        
        with patch.object(self.monitor, 'fetch_options_data', return_value=updated_options_data):
            # Refresh the data
            self.monitor.refresh_data()
            
            # Verify the price was updated
            updated_price = self.monitor.options_data['AAPL']['calls'][0]['lastPrice']
            self.assertEqual(updated_price, 8.25)
        
        # 6. Execute a sell order based on the updated price
        sell_order = self.trader.sell_option(
            ticker="AAPL",
            expiration="2022-03-21",
            strike=220.0,
            option_type="call",
            quantity=1
        )
        
        # Verify the sell order
        self.assertEqual(sell_order['status'], "filled")
        self.assertEqual(sell_order['filled_avg_price'], 8.25)
        
        # 7. Calculate profit/loss using numeric values
        profit = (sell_order['filled_avg_price'] - buy_order['filled_avg_price']) * sell_order['filled_qty'] * 100
        self.assertEqual(profit, 75.0)  # (8.25 - 7.50) * 1 * 100 = 75.0

if __name__ == '__main__':
    unittest.main() 