# MCP Finance Analyzer

A sophisticated finance analyzer application that leverages the Model Context Protocol (MCP) to connect Claude LLM with real-time financial data APIs. The system uses a client-server architecture where an MCP server provides financial tools, and a host client integrates these tools with Claude for intelligent financial analysis.

## Architecture
┌─────────────────┐    HTTP/SSE    ┌──────────────────┐    API Calls    ┌─────────────────┐
│                 │◄──────────────►│                  │◄───────────────►│                 │
│   Host Client   │                │   MCP Server     │                 │ Alpha Vantage   │
│  (Claude LLM)   │                │ (Financial APIs) │                 │      API        │
│                 │                │                  │                 │                 │
└─────────────────┘                └──────────────────┘                 └─────────────────┘

- **Host Client** (`host.py`): Integrates with Claude LLM and manages end-user interactions
- **MCP Server** (`finance_mcp_server.py`): Provides financial data tools via Alpha Vantage API
- **Communication**: HTTP Server-Sent Events (SSE) transport between client and server

## Features

### Financial Tools
- **Stock Quotes**: Get real-time stock prices and market data
- **Stock Search**: Search for stocks by company name or symbol
- **Cryptocurrency Prices**: Retrieve current cryptocurrency prices in USD

### System Capabilities
- **Automatic Retry Logic**: Exponential backoff for connection failures
- **Graceful Error Handling**: Continues operation even when MCP server is unavailable
- **Independent Processes**: Client and server run separately for better reliability
- **Comprehensive Testing**: Unit tests with mocking for all components
- **Interactive Chat**: Natural language interface powered by Claude LLM

## Quick Start

### Prerequisites
- Python 3.11 or higher
- Alpha Vantage API key (free at [alphavantage.co](https://www.alphavantage.co/support/#api-key))
- Anthropic API key (get from [Anthropic Console](https://console.anthropic.com/))

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/mcp-finance-analyzer.git
   cd mcp-finance-analyzer

   python -m venv venv

2. **Set up virtual environment:**
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

3. **Install dependencies:**
pip install -r requirements.txt

4. **Configure environment variables:** Create a .env file in the project root:
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here

## Running the Application
### Run these commands in separate terminals

1. **Start the MCP server (Terminal 1):**
python src/finance_mcp_server.py

You should see:
Finance MCP Server (HTTP Transport)
Server will start on default port (likely 8000)
Available tools: get_stock_quote, search_stocks, get_crypto_price

2. **Start the MCP server (Terminal 1):**
python src/host.py

Example Usage:
You: What's the current price of Apple stock?

Claude: I'll get the current Apple stock price for you.

[Tool call: get_stock_quote with symbol: AAPL]

Stock Quote for AAPL:
- Current Price: $182.52
- Change: +1.25 (+0.69%)
- Volume: 45,123,456
- Last Updated: 2024-01-15

Based on the current data, Apple (AAPL) is trading at $182.52, up $1.25 (+0.69%) from the previous close.

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_host.py -v

# Watch mode (re-run tests on file changes)
pytest tests/ -v --tb=short -x

# Run specific test method
pytest tests/test_host.py::TestFinanceAnalyzerHost::test_specific_method -v

Test Coverage
Test Coverage includes:

Initialization and configuration
MCP server connection (success/failure scenarios)
Tool discovery and execution
Claude LLM integration
Error handling and retry logic
Interactive session flow

Project Structure
mcp-finance-analyzer/
├── src/
│   ├── host.py                 # Main client application
│   └── finance_mcp_server.py   # MCP server with financial tools
├── tests/
│   └── test_host.py           # Comprehensive test suite
├── .env                       # Environment variables (create this)
├── .gitignore                # Git ignore rules
├── requirements.txt          # Python dependencies
└── README.md                # This file

Configuration
Environment Variables
ANTHROPIC_API_KEY Anthropic API key for Claude LLM
ALPHA_VANTAGE_API_KEY Alpha Vantage API key for financial dataYes

Server Configuration
The MCP server runs on http://localhost:8000 by default. To modify:
python# In finance_mcp_server.py
mcp.run(transport="sse")  # Uses default port 8000

Development
Adding New Financial Tools

Add tool definition in finance_mcp_server.py:
python@mcp.tool()
def my_new_tool(parameter: str) -> str:
    """Tool description for Claude"""
    # Implementation
    return result

Tool will automatically be available to Claude via the MCP protocol

Troubleshooting
Common Issues

"Connection failed"

Ensure MCP server is running on port 8000
Check firewall settings
Verify no other service is using port 8000


"Invalid API key"

Verify your .env file exists and contains valid keys
Check that environment variables are loaded correctly


"No tools available"

Confirm MCP server started successfully
Check server logs for any startup errors
Verify client can connect to http://localhost:8000



Debug Mode
Enable verbose logging by adding debug prints in key methods:
python# In host.py, add debug logging
print(f"Debug: Available tools: {len(self.available_tools)}")
print(f"Debug: Server URL: {self.server_url}")
Contributing

Fork the repository
Create a feature branch (git checkout -b feature/amazing-feature)
Make your changes
Add tests for new functionality
Ensure all tests pass (pytest tests/)
Commit your changes (git commit -m 'Add amazing feature')
Push to the branch (git push origin feature/amazing-feature)
Open a Pull Request