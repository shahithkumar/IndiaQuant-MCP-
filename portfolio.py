import sqlite3
import numpy as np
import pandas as pd
from config import DB_PATH
from market_data import get_live_price_data, get_historical_data

def auto_execute_stop_loss(symbol: str, qty: int, current_price: float):
    """Executes a SELL order dynamically if stop-loss triggers below threshold."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Sell entire position (Simulated Market Order execution)
    cur.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
    # Log trade with Stop-Loss Tag
    cur.execute("INSERT INTO trades (symbol, side, quantity, price) VALUES (?, ?, ?, ?)",
               (symbol, "SELL (STOP-LOSS)", qty, current_price))
    conn.commit()
    conn.close()

def calculate_risk_score(symbol: str, position_value: float) -> str:
    """Computes a risk classification score based on 1mo historical standard deviation."""
    try:
        df = get_historical_data(symbol, period="1mo", interval="1d")
        if df is None or df.empty:
            return "UNKNOWN"
            
        returns = df['Close'].pct_change().dropna()
        volatility = returns.std()
        
        # Using volatility threshold proxies to determine classification score
        risk_metric = volatility * 100
        if risk_metric > 3.0: 
            return "HIGH"
        elif risk_metric > 1.5: 
            return "MEDIUM"
        else:
            return "LOW"
    except Exception:
        return "UNKNOWN"

def get_portfolio_pnl() -> dict:
    """Computes live PnL and executes contingent Risk Management checks dynamically."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT symbol, quantity, avg_price, stop_loss FROM positions")
    rows = cur.fetchall()
    conn.close()
    
    if not rows:
        return {"positions": [], "total_pnl": 0.0, "total_value": 0.0}
        
    positions = []
    total_pnl = 0.0
    total_value = 0.0
    alerts = []
    
    for row in rows:
        symbol, qty, avg_price, stop_loss = row
        market = get_live_price_data(symbol)
        
        current_price = market.get('price')
        if not current_price:
            current_price = avg_price # fallback to avg_price
        
        # Stop-Loss logic trigger intercept
        if stop_loss is not None and current_price <= stop_loss:
            auto_execute_stop_loss(symbol, qty, current_price)
            alerts.append(f"STOP-LOSS TRIGGERED: Automatic Market Sell executed on {qty} of {symbol} at current price {current_price}")
            continue # Filter this positional line out as it's been closed
            
        pnl = (current_price - avg_price) * qty
        value = current_price * qty
        
        total_pnl += pnl
        total_value += value
        
        # Dynamically measure standard deviation
        risk_level = calculate_risk_score(symbol, value)
        
        positions.append({
            "symbol": symbol,
            "quantity": qty,
            "avg_buy_price": round(avg_price, 2),
            "current_price": round(current_price, 2),
            "unrealized_pnl": round(pnl, 2),
            "pnl_percentage": round((pnl / (avg_price * qty)) * 100, 2) if avg_price > 0 else 0,
            "stop_loss": stop_loss,
            "risk_score": risk_level
        })
        
    response = {
        "positions": positions,
        "total_pnl": round(total_pnl, 2),
        "total_value": round(total_value, 2)
    }
    
    if alerts:
        response["risk_alerts"] = alerts
        
    return response

def place_virtual_trade(symbol: str, qty: int, side: str, stop_loss: float = None) -> dict:
    side = side.upper()
    if side not in ["BUY", "SELL"]:
        return {"error": "Side must be BUY or SELL"}
        
    if qty <= 0:
        return {"error": "Quantity must be greater than 0"}
        
    market = get_live_price_data(symbol)
    price = market.get('price')
    
    if not price:
        return {"error": f"Failed to fetch live price for {symbol}"}
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("INSERT INTO trades (symbol, side, quantity, price) VALUES (?, ?, ?, ?)",
               (symbol, side, qty, price))
    order_id = cur.lastrowid
    
    cur.execute("SELECT quantity, avg_price, stop_loss FROM positions WHERE symbol = ?", (symbol,))
    pos = cur.fetchone()
    
    if side == "BUY":
        if pos:
            old_qty, old_price, old_sl = pos
            new_qty = old_qty + qty
            new_avg = ((old_qty * old_price) + (qty * price)) / new_qty
            final_sl = stop_loss if stop_loss else old_sl
            cur.execute("UPDATE positions SET quantity = ?, avg_price = ?, stop_loss = ? WHERE symbol = ?",
                       (new_qty, new_avg, final_sl, symbol))
        else:
            cur.execute("INSERT INTO positions (symbol, quantity, avg_price, stop_loss) VALUES (?, ?, ?, ?)",
                       (symbol, qty, price, stop_loss))
    else: # SELL
        if not pos or pos[0] < qty:
            conn.rollback()
            conn.close()
            return {"error": "Insufficient quantity to sell"}
            
        old_qty, old_price, old_sl = pos
        new_qty = old_qty - qty
        
        if new_qty == 0:
            cur.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        else:
            cur.execute("UPDATE positions SET quantity = ? WHERE symbol = ?",
                       (new_qty, symbol))
                       
    conn.commit()
    conn.close()
    
    return {
        "order_id": order_id,
        "symbol": symbol,
        "side": side,
        "quantity": qty,
        "executed_price": price,
        "stop_loss_set": stop_loss,
        "status": "FILLED"
    }
