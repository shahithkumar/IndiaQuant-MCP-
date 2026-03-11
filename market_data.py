import yfinance as yf
import pandas as pd
from typing import Dict, Any, List
from cache import ttl_cache

def normalize_symbol(symbol: str) -> str:
    """Ensure symbol has NSE suffix if it's an Indian stock"""
    symbol = symbol.upper()
    if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
        if symbol == 'NIFTY':
            return '^NSEI'
        elif symbol == 'BANKNIFTY':
            return '^NSEBANK'
        else:
            return symbol + '.NS'
    return symbol

@ttl_cache(ttl_seconds=10) # 10 second cache to avoid rate limits on live price
def get_live_price_data(symbol: str) -> Dict[str, Any]:
    """Fetch live price, change, and volume for a symbol."""
    try:
        norm_symbol = normalize_symbol(symbol)
        ticker = yf.Ticker(norm_symbol)
        
        info = ticker.fast_info
        
        current_price = info.last_price
        prev_close = info.previous_close
        volume = info.last_volume
        
        if prev_close and prev_close > 0:
            change_pct = ((current_price - prev_close) / prev_close) * 100
        else:
            change_pct = 0.0
            
        return {
            "symbol": norm_symbol,
            "price": round(current_price, 2) if current_price else None,
            "change_pct": round(change_pct, 2),
            "volume": volume
        }
    except Exception as e:
        return {
            "error": f"Failed to fetch live price data for {symbol}: {str(e)}",
            "symbol": symbol,
            "price": None,
            "change_pct": None,
            "volume": None
        }

@ttl_cache(ttl_seconds=300) # 5 min cache for OHLC history
def get_historical_data(symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch historical OHLC data."""
    try:
        norm_symbol = normalize_symbol(symbol)
        ticker = yf.Ticker(norm_symbol)
        df = ticker.history(period=period, interval=interval)
        return df
    except Exception:
        return pd.DataFrame()

@ttl_cache(ttl_seconds=300)
def get_sector_heatmap_data() -> Dict[str, float]:
    """Return a mock-up of Indian sectors via proxy ETFs or indices since yfinance
    doesn't easily export live sector components in one go without a massive scan.
    We will use sector indices available on NSE."""
    sectors = {
        "IT": "^CNXIT",
        "Bank": "^NSEBANK",
        "Auto": "^CNXAUTO",
        "FMCG": "^CNXFMCG",
        "Pharma": "^CNXPHARMA",
        "Metal": "^CNXMETAL"
    }
    
    heatmap = {}
    for name, ticker in sectors.items():
        try:
            data = get_live_price_data(ticker)
            heatmap[name] = data.get('change_pct', 0.0)
        except Exception:
            heatmap[name] = 0.0
            
    return heatmap
