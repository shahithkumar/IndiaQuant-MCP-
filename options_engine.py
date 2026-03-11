import yfinance as yf
import math
import datetime
from typing import Dict, Any, List
from cache import ttl_cache
from market_data import normalize_symbol, get_live_price_data

# Pure Black-Scholes Math
def norm_cdf(x):
    """Cumulative distribution function for the standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x):
    """Probability density function for the standard normal distribution."""
    return math.exp(-0.5 * x**x) / math.sqrt(2 * math.pi)

def calculate_d1(S, K, T, r, sigma):
    return (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))

def calculate_d2(d1, sigma, T):
    return d1 - sigma * math.sqrt(T)

def black_scholes_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Dict[str, float]:
    """
    Calculate option Greeks from scratch.
    S: Current Stock Price
    K: Strike Price
    T: Time to Expiration (in years)
    r: Risk-free rate (e.g., 0.05 for 5%)
    sigma: Volatility (e.g., 0.2 for 20%)
    option_type: 'CE' for Call, 'PE' for Put
    """
    # Handle extremely short expiry (T approx 0)
    if T <= 0:
        T = 0.0001
    
    # Handle zero volatility
    if sigma <= 0:
        sigma = 0.0001
        
    d1 = calculate_d1(S, K, T, r, sigma)
    d2 = calculate_d2(d1, sigma, T)
    
    cdf_d1 = norm_cdf(d1)
    cdf_d2 = norm_cdf(d2)
    pdf_d1 = norm_pdf(d1)
    
    greeks = {}
    
    if option_type == 'CE':
        greeks['delta'] = cdf_d1
        greeks['theta'] = (- (S * sigma * pdf_d1) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * cdf_d2) / 365.0
    elif option_type == 'PE':
        greeks['delta'] = cdf_d1 - 1
        greeks['theta'] = (- (S * sigma * pdf_d1) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0
    else:
        raise ValueError("option_type must be 'CE' or 'PE'")
        
    greeks['gamma'] = pdf_d1 / (S * sigma * math.sqrt(T))
    greeks['vega'] = (S * pdf_d1 * math.sqrt(T)) / 100.0 # Standard vega is per 1% change in vol
    
    return {k: round(v, 4) for k, v in greeks.items()}

@ttl_cache(ttl_seconds=60)
def get_options_data(symbol: str, expiry: str = None) -> Dict[str, Any]:
    norm_symbol = normalize_symbol(symbol)
    ticker = yf.Ticker(norm_symbol)
    
    exp_dates = ticker.options
    if not exp_dates:
        return {"error": f"No options chain available for {norm_symbol}"}
        
    target_expiry = expiry if expiry and expiry in exp_dates else exp_dates[0]
    
    chain = ticker.option_chain(target_expiry)
    
    calls = chain.calls[['strike', 'lastPrice', 'impliedVolatility', 'openInterest', 'volume']].fillna(0).to_dict('records')
    puts = chain.puts[['strike', 'lastPrice', 'impliedVolatility', 'openInterest', 'volume']].fillna(0).to_dict('records')
    
    return {
        "symbol": norm_symbol,
        "expiry": target_expiry,
        "available_expiries": list(exp_dates),
        "calls": calls,
        "puts": puts
    }

def calculate_max_pain(symbol: str, expiry: str = None) -> float:
    data = get_options_data(symbol, expiry)
    if "error" in data:
        return 0.0
        
    calls, puts = data['calls'], data['puts']
    
    # Combine strikes
    strikes = set([c['strike'] for c in calls] + [p['strike'] for p in puts])
    
    max_pain_val = float('inf')
    max_pain_strike = 0.0
    
    for strike in sorted(list(strikes)):
        loss = 0.0
        # Call losses
        for c in calls:
            if strike > c['strike']:
                loss += (strike - c['strike']) * c['openInterest']
        # Put losses
        for p in puts:
            if strike < p['strike']:
                loss += (p['strike'] - strike) * p['openInterest']
                
        if loss < max_pain_val:
            max_pain_val = loss
            max_pain_strike = strike
            
    return max_pain_strike

def find_unusual_options_activity(symbol: str) -> List[Dict[str, Any]]:
    data = get_options_data(symbol)
    if "error" in data:
        return []
        
    alerts = []
    
    for opt_type, chain in [("Call", data['calls']), ("Put", data['puts'])]:
        for opt in chain:
            vol = opt.get('volume', 0)
            oi = opt.get('openInterest', 0)
            
            # Unusually high volume compared to prior open interest
            if vol > 0 and oi > 0 and (vol > oi * 2):
                alerts.append({
                    "symbol": symbol,
                    "strike": opt['strike'],
                    "type": opt_type,
                    "volume": vol,
                    "open_interest": oi,
                    "reason": f"Volume ({vol}) is > 2x Open Interest ({oi})"
                })
                
    return alerts

def compute_greeks_for_option(symbol: str, expiry: str, strike: float, option_type: str) -> Dict[str, Any]:
    # 1. Get live price S
    price_data = get_live_price_data(symbol)
    S = price_data.get('price')
    if not S:
        return {"error": f"Could not fetch live price for {symbol}"}
        
    # 2. Get target option
    opt_data = get_options_data(symbol, expiry)
    if "error" in opt_data:
        return opt_data
        
    target_expiry = opt_data['expiry']
    
    chain = opt_data['calls'] if option_type == 'CE' else opt_data['puts']
    vol_target = 0.2 # fallback
    
    for opt in chain:
        if isinstance(opt, dict) and 'strike' in opt and abs(opt['strike'] - strike) < 0.1:
            vol_target = opt.get('impliedVolatility', 0.2)
            if vol_target < 0.01: # Avoid zero or NaN IV
                vol_target = 0.2
            break
            
    # 3. Calculate Time to Expiry (T in years)
    try:
        exp_date = datetime.datetime.strptime(target_expiry, "%Y-%m-%d")
        now = datetime.datetime.now()
        days_to_expiry = (exp_date - now).days
        T = max(days_to_expiry / 365.0, 0.0001)
    except Exception:
        T = 0.1 # Fallback
        
    # 4. Risk-free rate
    r = 0.07 # Assume 7% RBI repo rate proxy for Indian markets
    
    greeks = black_scholes_greeks(S, strike, T, r, vol_target, option_type)
    greeks['implied_volatility'] = round(vol_target, 4)
    greeks['underlying_price'] = S
    
    return greeks
