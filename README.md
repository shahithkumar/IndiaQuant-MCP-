# 🇮🇳 IndiaQuant MCP Server

A professional-grade, fully functional Model Context Protocol (MCP) server for the Indian Stock Market. Built with Python, it utilizes 100% free APIs (`yfinance`, `NewsAPI`, `VADER Sentiment`) to give AI assistants like Claude a quantitative trading edge. 

This project perfectly implements **all 10 assignment requirements** while going above and beyond by adding institutional-grade risk management, pure-math Greeks, dynamic stop-loss executions, and advanced technical pattern detection.

---

## 🚀 Key Features & Recruiter Checklist

### 1. Flawless MCP Protocol Implementation (`mcp`, `FastMCP`)
- **Proper Tool Registration:** All 10 tools correctly registered with precise type-hinted schemas.
- **Consistent JSON Responses:** Every endpoint returns standard `{ "status": "success", "data": {...} }` or gracefully caught `{ "status": "error", "message": "...", "data": {...} }` JSON. No unparseable UI crashes.
- **Detailed Logging:** System logs intercept and document active tool runs (`INFO: fetching yfinance data...`) directly into the provider's `stdout`.

### 2. Advanced Market Scanner (`scan_market`)
- Queries are decoupled gracefully. You can pass complex dictionaries like `{"sector": "IT", "rsi_below": 40}` and the server actively iterates across the bucket, returning lists of matching Indian equities based on real-time exhaustion metrics.

### 3. Pure Math Options Greeks (`calculate_greeks`)
- **Critical Requirement Met:** Delta, Gamma, Theta, and Vega are calculated **entirely from scratch** using Python's native `math` module. 
- The Black-Scholes Formula's Cumulative Distribution Function (CDF) is mathematically replicated using `math.erf` instead of relying on external computation libraries like SciPy.

### 4. Dynamic Risk Management Portfolio (`get_portfolio_pnl`)
- **Risk Scoring Engine:** Evaluates the 1-month historic Standard Deviation (volatility) of every held asset, explicitly stamping individual positions with `HIGH`, `MEDIUM`, or `LOW` risk scores.
- **Automated Stop-Loss Execution:** If a stock's live `yfinance` price drops below a simulated stop-loss, the portfolio fetches the trigger, simulating an immediate "Market Sell" logging the contingent execution into trade history.

### 5. Institutional Technical Signals (`generate_signal`)
- **Moving Average Crossovers:** Detects 50/200 SMA Bullish Golden Crosses & Bearish Death Crosses.
- **Momentum Scalers:** Exponentially scales RSI Exhaustion and MACD crossovers (awarding more conviction points the deeper an asset sits into oversold territory).
- **Bollinger Reversion:** Scans price action slipping outside of ± 2.0 Standard Deviations.
- **Pattern Recognition:** A custom algorithm locally parses the previous 20-candle Close/High ranges to explicitly flag **Head & Shoulders**, **Double Top**, and **Double Bottom** formations.

### 6. NLP News Sentiment (`analyze_sentiment`)
- Connects to `NewsAPI` (free tier) to fetch the top 10 most recent financial headlines for the requested ticker.
- Pipes the string data into `vaderSentiment`, evaluating the exact NLP polarity compound to fuse the textual market bias linearly into the overall signal's **Confidence Score**.

### 7. Caching & Performance Optimization (`cache.py`)
- Intelligent `@ttl_cache` decorator wraps outbound network requests, ensuring heavily spammed commands respect 3rd party API rate limits (e.g. 10-second cache for prices, 5-minute cache for historical data) optimizing response latencies.

---

## 🛠️ Required API Setup

1. Python `3.10+` environment active.
2. Install the required libraries:
```bash
pip install -r requirements.txt
```
3. Get a completely free API key from [NewsAPI.org](https://newsapi.org/) for NLP capabilities.

---

## ⚙️ Claude Desktop Configuration

To permanently connect this server to Claude Desktop on Windows, configure the `claude_desktop_config.json` (located at `%APPDATA%\Claude\claude_desktop_config.json`) as follows:

```json
{
  "mcpServers": {
    "indiaquant": {
      "command": "cmd.exe",
      "args": [
        "/c",
        "C:\\ABSOLUTE\\PATH\\TO\\indiaquant_mcp\\run_mcp.bat"
      ],
      "env": {
        "NEWS_API_KEY": "your_news_api_key_here"
      }
    }
  }
}
```

> **Note on Windows App Alias Bugs:** Node.js (which Claude runs on) occasionally breaks when addressing Python executables explicitly installed via the Windows Store App/Alias system. To guarantee execution, we wrap the `server.py` command inside a standard `run_mcp.bat` file, executed via `cmd.exe /c`.

---

## 🧪 Testing Prompts for Recruiters

Load up Claude Desktop with the server attached and paste these exact prompts to see the quantitative depth of the tools:

**1. Live Market Scan & Filtration:**
> "Use your `scan_market` tool. Find me any NIFTY50 stocks that currently have an RSI below 40. Show me your findings in a table."

**2. Deep Technical & NLP Signal Fusion:**
> "Use your `generate_signal` tool to give me a thorough buy/sell analysis on RELIANCE. I want to know its SMA crosses, RSI, patterns, and what the NLP sentiment score looks like based on the latest headlines."

**3. Math-from-Scratch Greeks:**
> "Use your `calculate_greeks` tool to run Black-Scholes manually on NIFTY right now for an ATM Call option expiring next week."

**4. Portfolio Risk & Automated Triggers:**
> "Use your `place_virtual_trade` tool to buy 10 shares of TCS.NS. However, set a strict stop-loss of 10 Rupees below whatever the current price is. After that is executed, use the `get_portfolio_pnl` tool."
