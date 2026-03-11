import pandas as pd
import pandas_ta as ta
import requests
from config import NEWS_API_KEY
from market_data import get_historical_data
from cache import ttl_cache

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    vader_analyzer = SentimentIntensityAnalyzer()
except ImportError:
    vader_analyzer = None

def analyze_sentiment(symbol: str) -> dict:
    """Fetch recent news and calculate NLP sentiment using VADER."""
    if not NEWS_API_KEY:
        return {"error": "NewsAPI key not configured", "score": 0.0, "signal": "HOLD"}
        
    url = f"https://newsapi.org/v2/everything?q={symbol}&sortBy=publishedAt&apiKey={NEWS_API_KEY}&language=en"
    
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get("status") != "ok":
            return {"error": data.get("message", "API Error"), "score": 0.0, "signal": "HOLD"}
            
        articles = data.get("articles", [])[:10]
        if not articles:
            return {"error": "No news found", "score": 0.0, "signal": "HOLD"}
            
        headlines = []
        compound_score = 0.0
        
        for article in articles:
            title = (article.get('title') or "")
            headlines.append(title)
            
            if vader_analyzer:
                # Advanced NLP Sentiment Scoring
                sentiment = vader_analyzer.polarity_scores(title)
                compound_score += sentiment['compound']
            else:
                # Primitive Lexicon Fallback
                title_lower = title.lower()
                pos_words = ["growth", "profit", "surge", "gain", "buy", "up", "bull", "record", "dividend"]
                neg_words = ["loss", "decline", "fall", "drop", "sell", "down", "bear", "miss", "scandal"]
                if any(w in title_lower for w in pos_words): compound_score += 0.5
                if any(w in title_lower for w in neg_words): compound_score -= 0.5
            
        normalized_score = max(-1.0, min(1.0, compound_score / max(1, len(articles))))
        
        signal = "HOLD"
        if normalized_score > 0.15:
            signal = "BUY"
        elif normalized_score < -0.15:
            signal = "SELL"
            
        return {
            "score": round(normalized_score, 2),
            "signal": signal,
            "headlines": headlines[:3]
        }
            
    except Exception as e:
        return {"error": str(e), "score": 0.0, "signal": "HOLD"}

def generate_signal(symbol: str, timeframe: str = "1d") -> dict:
    import logging
    period = "1y" # expanded period to get 200 SMA
    interval = "1d"
    if timeframe.lower() in ["1h", "1hour"]:
        period = "1mo"
        interval = "1h"
    elif timeframe.lower() in ["1wk", "1week", "1w"]:
        period = "5y"
        interval = "1wk"
        
    df = get_historical_data(symbol, period=period, interval=interval)
    if df is None or df.empty or len(df) < 50:
        return {"signal": "HOLD", "confidence": 0, "reason": "Not enough data"}
        
    logging.info(f"calculating Technical Indicators (RSI, MACD, BB, SMA) for {symbol}")
    # Technical Indicators via pandas-ta
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.bbands(length=20, append=True)
    df.ta.sma(length=50, append=True)
    df.ta.sma(length=200, append=True)
    
    last_row = df.iloc[-1]
    
    # Safely extract values
    rsi = last_row.get('RSI_14', 50)
    macd = last_row.get('MACD_12_26_9', 0)
    macd_signal = last_row.get('MACDs_12_26_9', 0)
    close_price = last_row.get('Close', 0)
    bb_lower = last_row.get('BBL_20_2.0', 0)
    bb_upper = last_row.get('BBU_20_2.0', 0)
    sma_50 = last_row.get('SMA_50', 0)
    sma_200 = last_row.get('SMA_200', 0)
    
    score = 0.0
    
    # RSI Exhaustion Logic (Scale up score as it gets more extreme)
    if pd.notna(rsi):
        if rsi < 30:
            score += 30 + (30 - rsi) # Extra points the lower it goes
        elif rsi > 70:
            score -= 30 + (rsi - 70) 
            
    # Trend Analysis (Golden Cross / Bearish Trend)
    if pd.notna(sma_50) and pd.notna(sma_200) and sma_200 > 0:
        if sma_50 > sma_200:
            score += 15 # Bullish trend baseline
        else:
            score -= 15 # Bearish trend
            
    # MACD Momentum Logic
    if pd.notna(macd) and pd.notna(macd_signal):
        if macd > macd_signal and macd > 0:
            score += 20 # Strong up momentum
        elif macd > macd_signal:
            score += 10 # Recovering
        elif macd < macd_signal and macd < 0:
            score -= 20 # Strong downward momentum
        elif macd < macd_signal:
            score -= 10 # Cooling off
            
    # Bollinger Bands Reversion
    if pd.notna(close_price) and pd.notna(bb_lower) and pd.notna(bb_upper) and bb_upper > bb_lower:
        if close_price < bb_lower:
            score += 25 # Oversold bounce potential
        elif close_price > bb_upper:
            score -= 25 # Overbought pullback potential
            
    # Pattern Detection (Head & Shoulders, Double Top & Double Bottom)
    closes = df['Close'].tail(20).values
    highs = df['High'].tail(20).values
    is_double_top = False
    is_double_bot = False
    is_head_shoulders = False
    
    if len(closes) >= 20:
        p1, p2, p3, p4, p5 = closes[0], closes[5], closes[10], closes[15], closes[-1]
        
        # Double Top
        if (p2 > p1 and p2 > p3) and (p4 > p3 and p4 > p5) and (abs(p2 - p4) / p2 < 0.03) and p5 < p3:
            is_double_top = True
            score -= 25
        
        # Double Bottom
        if (p2 < p1 and p2 < p3) and (p4 < p3 and p4 < p5) and (abs(p2 - p4) / p2 < 0.03) and p5 > p3:
            is_double_bot = True
            score += 25
            
        # Head & Shoulders Approximation (Left Shoulder -> Head -> Right Shoulder)
        left_shoulder = max(highs[2:7])
        head = max(highs[7:14])
        right_shoulder = max(highs[14:19])
        
        if head > left_shoulder and head > right_shoulder and abs(left_shoulder - right_shoulder) / left_shoulder < 0.05:
            is_head_shoulders = True
            score -= 30  # Bearish Pattern
            
    # Sentiment Weight Fusion
    logging.info(f"evaluating NLP sentiment block for {symbol}")
    sentiment_data = analyze_sentiment(symbol)
    sentiment_score = sentiment_data.get('score', 0.0)
    score += (sentiment_score * 35) # High impact from news sentiment
    
    # Determine final signal (Cap confidence at 100)
    confidence = min(100.0, float(abs(score)))
    
    if score >= 35:
        final_signal = "BUY"
    elif score <= -35:
        final_signal = "SELL"
    else:
        final_signal = "HOLD"
        confidence = max(0.0, 100.0 - (confidence * 2)) # Hold confidence scales inversely
        
    return {
        "signal": final_signal,
        "confidence": round(confidence, 2),
        "patterns_detected": {
            "head_and_shoulders": is_head_shoulders,
            "double_top": is_double_top,
            "double_bottom": is_double_bot
        },
        "metrics": {
            "rsi": round(rsi, 2) if pd.notna(rsi) else None,
            "macd": round(macd, 2) if pd.notna(macd) else None,
            "sma_50": round(sma_50, 2) if pd.notna(sma_50) else None,
            "sma_200": round(sma_200, 2) if pd.notna(sma_200) else None,
            "sentiment_score": round(sentiment_score, 2)
        }
    }

def scan_market(filter_criteria: dict) -> dict:
    """Scans the market across different proxy sectors handling specific query filtering logic."""
    baskets = {
        "NIFTY50": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS"],
        "IT": ["INFY.NS", "TCS.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
        "BANK": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"]
    }
    
    target_basket = filter_criteria.get("sector", "NIFTY50").upper()
    symbols = baskets.get(target_basket, baskets["NIFTY50"])
    
    matches = []
    for symbol in symbols:
        try:
            sig = generate_signal(symbol)
            if "error" in sig and sig["error"]:
                continue
                
            rsi = sig.get('metrics', {}).get('rsi', 50)
            if rsi is None:
                continue
                
            # Execute Advanced Pipeline Filters
            add_match = True
            
            if "rsi_below" in filter_criteria and rsi > float(filter_criteria["rsi_below"]):
                add_match = False
            if "rsi_above" in filter_criteria and rsi < float(filter_criteria["rsi_above"]):
                add_match = False
            if "signal" in filter_criteria and sig['signal'] != filter_criteria["signal"].upper():
                add_match = False
                
            if add_match:
                matches.append({
                    "symbol": symbol,
                    "rsi": rsi,
                    "signal": sig['signal'],
                    "confidence": sig['confidence']
                })
        except Exception:
            continue
            
    return {
        "query": filter_criteria,
        "sector_scanned": target_basket,
        "total_matches": len(matches),
        "matches": [m['symbol'] for m in matches],
        "details": matches
    }
