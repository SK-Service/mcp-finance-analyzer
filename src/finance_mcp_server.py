#!/usr/bin/env python3
"""
Finance MCP Server - HTTP Transport
Provides stock and crypto data through Alpha Vantage API
Run independently as: python src/finance_mcp_server.py
"""
import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MCP imports for HTTP transport
from mcp.server.fastmcp import FastMCP

# Alpha Vantage API configuration
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

if not ALPHA_VANTAGE_API_KEY:
    print("Warning: ALPHA_VANTAGE_API_KEY not found in environment variables")

# Create the FastMCP server for HTTP transport
mcp = FastMCP("finance-analyzer")

def make_api_request(function: str, **kwargs) -> Dict[str, Any]:
    """Make a request to Alpha Vantage API."""
    if not ALPHA_VANTAGE_API_KEY:
        return {"error": "Alpha Vantage API key not configured"}
    
    params = {
        "function": function,
        "apikey": ALPHA_VANTAGE_API_KEY,
        **kwargs
    }
    
    try:
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"API request failed: {str(e)}"}

@mcp.tool()
def get_stock_quote(symbol: str) -> str:
    """Get current stock price and basic info for a given symbol"""
    symbol = symbol.upper()
    
    # Get quote data
    data = make_api_request("GLOBAL_QUOTE", symbol=symbol)
    
    if "error" in data:
        return f"Error: {data['error']}"
    
    if "Error Message" in data:
        return f"Error: Invalid symbol '{symbol}' or API limit reached"
    
    # Parse the response
    quote = data.get("Global Quote", {})
    if not quote:
        return f"No data found for symbol: {symbol}"
    
    # Format the response
    price = quote.get("05. price", "N/A")
    change = quote.get("09. change", "N/A")
    change_percent = quote.get("10. change percent", "N/A")
    volume = quote.get("06. volume", "N/A")
    
    result = f"""Stock Quote for {symbol}:
• Current Price: ${price}
• Change: {change} ({change_percent})
• Volume: {volume}
• Last Updated: {quote.get('07. latest trading day', 'N/A')}
"""
    
    return result

@mcp.tool()
def search_stocks(query: str) -> str:
    """Search for stocks by company name or symbol"""
    # Use symbol search function
    data = make_api_request("SYMBOL_SEARCH", keywords=query)
    
    if "error" in data:
        return f"Error: {data['error']}"
    
    matches = data.get("bestMatches", [])
    if not matches:
        return f"No stocks found matching: {query}"
    
    # Format results (limit to top 5)
    result = f"Search results for '{query}':\n\n"
    for i, match in enumerate(matches[:5], 1):
        symbol = match.get("1. symbol", "N/A")
        name = match.get("2. name", "N/A")
        result += f"{i}. {symbol} - {name}\n"
    
    return result

@mcp.tool()
def get_crypto_price(symbol: str) -> str:
    """Get current cryptocurrency price in USD"""
    symbol = symbol.upper()
    
    # Get crypto quote (using CURRENCY_EXCHANGE_RATE)
    data = make_api_request("CURRENCY_EXCHANGE_RATE",
                          from_currency=symbol,
                          to_currency="USD")
    
    if "error" in data:
        return f"Error: {data['error']}"
    
    if "Error Message" in data:
        return f"Error: Invalid crypto symbol '{symbol}' or API limit reached"
    
    # Parse crypto data
    exchange_rate = data.get("Realtime Currency Exchange Rate", {})
    if not exchange_rate:
        return f"No data found for crypto: {symbol}"
    
    price = exchange_rate.get("5. Exchange Rate", "N/A")
    from_currency = exchange_rate.get("1. From_Currency Code", "N/A")
    last_refreshed = exchange_rate.get("6. Last Refreshed", "N/A")
    
    result = f"""Crypto Price for {from_currency}:
• Current Price: ${price} USD
• Last Updated: {last_refreshed}
"""
    
    return result

def main():
    """Run the MCP server with HTTP transport."""
    print("=" * 50)
    print("Finance MCP Server (HTTP Transport)")
    print("=" * 50)
    print("Server starting on http://localhost:3000")
    print("Available tools: get_stock_quote, search_stocks, get_crypto_price")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    # Run server with SSE transport on default port 3000
    mcp.run(transport="sse")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server failed to start: {e}")
        sys.exit(1)