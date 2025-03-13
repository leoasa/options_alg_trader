# Options Trader

A Python application for monitoring and trading options using the Alpaca API.

## Features

- Real-time stock price monitoring
- Options data visualization
- Command-line interface for quick monitoring
- Web dashboard for detailed analysis
- Automated trading strategies

## Prerequisites

- Python 3.11+
- Alpaca API account (for live trading)

## Installation

### Method 1: Clone and Install Dependencies

1. Clone the repository:
   ```
   git clone https://github.com/leoasa/options_alg_trader.git
   cd options_alg_trader
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

### Method 2: Install as a Package

You can also install the package directly using pip:

```
pip install git+https://github.com/leoasa/options_alg_trader.git
```

Or install it in development mode:

```
git clone https://github.com/leoasa/options_alg_trader.git
cd options_alg_trader
pip install -e .
```

### Environment Setup

Create a `.env` file in the root directory with the following variables:

```
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_API_SECRET=your_alpaca_api_secret
ALPACA_API_BASE_URL=https://paper-api.alpaca.markets  # Use paper trading for testing
```

You can copy the `.env.example` file provided in the repository:

```
cp .env.example .env
```

Then edit the `.env` file with your actual Alpaca API credentials.

## Configuration Files

### Portfolio Files

The application uses JSON files to track portfolio information:

- `portfolio.json`: Used for real trading with Alpaca API
- `simulated_portfolio.json`: Used for simulated trading without actual orders

Both files are initialized with default values:

**portfolio.json**
```json
{
  "cash": 100000.0,
  "positions": [],
  "orders": [],
  "transactions": []
}
```

**simulated_portfolio.json**
```json
{
  "cash": 100000.0,
  "buying_power": 200000.0,
  "equity": 100000.0,
  "positions": [],
  "transactions": []
}
```

You can modify these files to adjust your starting capital or to import existing positions.

## Usage

### Command Line Interface

Monitor stock prices and options data from the command line:

```
python -m options_trader.cli_monitor --tickers AAPL,MSFT,GOOGL --refresh 60
```

If installed as a package:

```
options-cli --tickers AAPL,MSFT,GOOGL --refresh 60
```

Options:
- `--tickers`: Comma-separated list of stock tickers to monitor
- `--refresh`: Data refresh interval in seconds (default: 60)

### Web Dashboard

Launch the interactive web dashboard:

```
python -m options_trader.options_monitor --tickers AAPL,MSFT,GOOGL --port 8050
```

If installed as a package:

```
options-monitor --tickers AAPL,MSFT,GOOGL --port 8050
```

Options:
- `--tickers`: Comma-separated list of stock tickers to monitor
- `--port`: Port number for the web server (default: 8050)
- `--refresh`: Data refresh interval in seconds (default: 60)

## Project Structure

- `options_trader/`: Main package
  - `option_trader.py`: Core trading functionality
  - `options_monitor.py`: Web dashboard for monitoring
  - `cli_monitor.py`: Command-line interface
- `tests/`: Test files
  - `test_options_trading.py`: Unit tests for options trading functionality
  - `test_integration.py`: Integration tests
  - `test_runner.py`: Custom test runner
- `portfolio.json`: Real trading portfolio configuration
- `simulated_portfolio.json`: Simulated trading portfolio configuration
- `setup.py`: Package installation configuration
- `.env.example`: Example environment variables file

## Tests

The project includes comprehensive unit and integration tests to ensure reliability.

### Running Tests with the Custom Test Runner

The custom test runner provides a clear summary of test results with color-coded output:

```
python tests/test_runner.py
```

This will run all tests and show a summary of passed, failed, and skipped tests.

### Running Specific Test Modules

You can specify which test modules to run:

```
python tests/test_runner.py tests.test_options_trading
python tests/test_runner.py tests.test_integration
```

### Running Tests with unittest

You can also run tests using the standard unittest module:

```
# Run all tests
python -m unittest discover -v tests

# Run a specific test module
python -m unittest -v tests.test_options_trading
python -m unittest -v tests.test_integration

# Run a specific test class
python -m unittest -v tests.test_options_trading.TestOptionTrader

# Run a specific test method
python -m unittest -v tests.test_options_trading.TestOptionTrader.test_buy_specific_option_contract
```

### Test Coverage

Our test suite covers the following functionality:

#### Unit Tests (test_options_trading.py)
- **Option Contract Buying**: Tests the ability to buy specific option contracts with various parameters
- **Option Contract Selling**: Verifies proper execution of sell orders for option positions
- **Real-time Price Monitoring**: Tests the monitoring of option prices and updates
- **Option Symbol Formatting**: Ensures correct formatting of option symbols for the Alpaca API
- **Error Handling**: Tests proper handling of API errors and edge cases

#### Integration Tests (test_integration.py)
- **End-to-End Trading Workflow**: Tests the complete workflow from monitoring to buying and selling options
- **Data Refresh and Updates**: Verifies that option data is properly refreshed and updated
- **Profit/Loss Calculation**: Tests accurate calculation of P&L for option trades
- **API Integration**: Tests proper integration with the Alpaca API for order execution

#### Simulation Mode Tests
- **Portfolio Management**: Tests the management of a simulated portfolio
- **Order Execution Simulation**: Verifies proper simulation of order execution
- **Position Tracking**: Tests tracking of positions in simulation mode

These tests ensure that all components of the system work correctly both individually and together, providing confidence in the reliability of the trading system.

## Cache Management

The application caches data to improve performance. Cache files are stored in platform-specific locations:

- **macOS**: `~/Library/Caches/options_trader/`
- **Linux**: `~/.cache/options_trader/`
- **Windows**: `C:\Users\<username>\AppData\Local\options_trader\Cache\`

Note: To manually clear the cache, you can delete the cache directories above.

## Current Limitations

Please note the following limitations of the current implementation:

1. **Configuration Required**: Tickers, options chain settings, and order placement parameters need to be modified to work with your specific requirements.
2. **No Database**: There is currently no database to save trades or user information. All data is stored in JSON files.
3. **Paper Trading**: By default, the system is configured for paper trading. Modify the `.env` file to switch to live trading.

## Tech Stack

This project uses several key technologies and libraries:

### Core Dependencies

- **Alpaca Trade API**: Provides access to market data and order execution for stocks and options. Used for real-time trading and data retrieval.

- **Pandas**: Powerful data manipulation library used for analyzing financial data, calculating metrics, and managing time series data.

- **NumPy**: Numerical computing library that supports mathematical operations on arrays and matrices. Used for calculations in option pricing models and strategy algorithms.

- **Matplotlib**: Data visualization library used for creating charts and graphs to analyze market trends and strategy performance.

### Utility Libraries

- **Requests**: HTTP library for making API calls to external data sources when needed beyond what Alpaca provides.

- **Python-dotenv**: Loads environment variables from .env files, used to securely store API credentials without hardcoding them.

- **Colorama**: Cross-platform colored terminal text, used to enhance the readability of test outputs and logging information.

### Testing Framework

- **Unittest**: Python's built-in testing framework used for unit and integration tests.

- **MagicMock**: Part of the unittest.mock module, used to create mock objects for testing components in isolation.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.