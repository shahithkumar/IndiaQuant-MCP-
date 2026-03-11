import logging
import sys
from mcp.server.fastmcp import FastMCP
import market_data
import options_engine
import signals
import portfolio
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

# Initialize FastMCP Server
mcp = FastMCP("IndiaQuant")

def format_response(data: Any) -> dict:
    if isinstance(data, dict) and "error" in data:
        return {"status": "error", "message": data.pop("error"), "data": data}
    return {"status": "success", "data": data}

@mcp.tool()
def get_live_price(symbol: str) -> dict:
    """
    Fetch real-time NSE/BSE stock price.
    symbol (str): The stock symbol (e.g. RELIANCE, TCS).
    """
    logging.info(f"fetching yfinance data for {symbol}")
    return format_response(market_data.get_live_price_data(symbol))

@mcp.tool()
def get_options_chain(symbol: str, expiry: str = None) -> dict:
    """
    Pull live options chain including strikes, CE/PE Open Interest.
    symbol (str): The base asset symbol (e.g. NIFTY).
    expiry (str): Optional. The target expiry target YYYY-MM-DD.
    """
    logging.info(f"fetching options chain for {symbol}")
    return format_response(options_engine.get_options_data(symbol, expiry))

@mcp.tool()
def analyze_sentiment(symbol: str) -> dict:
    """
    Run NLP sentiment analysis using VADER on recent headlines for a symbol.
    symbol (str): The stock symbol/company name.
    """
    logging.info(f"analyzing sentiment for {symbol}")
    return format_response(signals.analyze_sentiment(symbol))

@mcp.tool()
def generate_signal(symbol: str, timeframe: str = "1d") -> dict:
    """
    Compute RSI, MACD, Bollinger Bands, Head/Shoulders, Double Tops and emit BUY/SELL/HOLD signal.
    symbol (str): The stock symbol.
    timeframe (str): Timeframe e.g. "1d", "1h". Default is "1d".
    """
    logging.info(f"generating signal for {symbol} on {timeframe} timeframe")
    data = signals.generate_signal(symbol, timeframe)
    logging.info(f"returning signal: {data.get('signal', 'HOLD')} with confidence {data.get('confidence', 0)}")
    return format_response(data)

@mcp.tool()
def get_portfolio_pnl() -> dict:
    """
    Show your virtual portfolio positions, absolute P&L, process Stop-Loss exits, and volatility Risk classifications.
    return: Dictionary mapping positions and total account health.
    """
    logging.info(f"calculating portfolio PnL and assessing risk scoring")
    return format_response(portfolio.get_portfolio_pnl())

@mcp.tool()
def place_virtual_trade(symbol: str, qty: int, side: str, stop_loss: float = None) -> dict:
    """
    Place a virtual paper trade into the SQLite database.
    symbol (str): The stock symbol.
    qty (int): Quantity of shares.
    side (str): "BUY" or "SELL".
    stop_loss (float): Optional integer set to automatically execute a Stop-Loss sell if price drops below this bound.
    """
    logging.info(f"placing virtual trade for {qty} of {symbol} side {side}")
    return format_response(portfolio.place_virtual_trade(symbol, qty, side, stop_loss))

@mcp.tool()
def calculate_greeks(symbol: str, expiry: str, strike: float, option_type: str) -> dict:
    """
    Calculate Delta, Gamma, Theta, Vega mathematically from scratch for an option.
    symbol (str): Asset symbol.
    expiry (str): Option expiry date (YYYY-MM-DD).
    strike (float): Option strike price.
    option_type (str): "CE" for call, "PE" for put.
    """
    logging.info(f"calculating greeks for {symbol} {strike} {option_type}")
    return format_response(options_engine.compute_greeks_for_option(symbol, expiry, strike, option_type))

@mcp.tool()
def detect_unusual_activity(symbol: str) -> dict:
    """
    Detect unusual volume/OI spikes in the options chain for a symbol.
    """
    logging.info(f"detecting unusual options activity for {symbol}")
    return format_response({"activity": options_engine.find_unusual_options_activity(symbol)})

@mcp.tool()
def scan_market(filter_criteria: dict) -> dict:
    """
    Scan a predefined basket of top Indian market stocks based on specific technical limits.
    filter_criteria specifies fields like:
        - sector (str): e.g. "IT", "BANK", or "NIFTY50"
        - rsi_below (float): e.g. 30
        - rsi_above (float): e.g. 70
        - signal (str): e.g. "BUY", "SELL"
    example: {"sector": "IT", "rsi_below": 40}
    """
    logging.info(f"scanning market with criteria: {filter_criteria}")
    return format_response(signals.scan_market(filter_criteria))

@mcp.tool()
def get_sector_heatmap() -> dict:
    """
    Get percentage change across major NSE sectors.
    """
    logging.info(f"fetching sector heatmap")
    return format_response(market_data.get_sector_heatmap_data())

if __name__ == "__main__":
    mcp.run()
