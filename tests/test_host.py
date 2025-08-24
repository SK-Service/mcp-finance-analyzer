# tests/test_host.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, call
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from host import FinanceAnalyzerHost

class TestFinanceAnalyzerHost:

    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
    @patch('host.anthropic.Anthropic')
    def test_init_with_valid_api_key(self, mock_anthropic):
        """Test successful initialization with valid API key"""
        # Arrange
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        # Act
        host = FinanceAnalyzerHost()

        # Assert
        assert host.anthropic_api_key == 'test-api-key'
        assert host.anthropic_client == mock_client
        assert host.available_tools == []
        assert host.proceed_without_tools == False
        assert host.server_url == "http://localhost:8000/sse"
        mock_anthropic.assert_called_once_with(api_key='test-api-key')

    @patch.dict(os.environ, {}, clear=True)  # Remove ANTHROPIC_API_KEY
    def test_init_missing_api_key_exits(self):
        """Test that missing API key causes system exit"""
        with pytest.raises(SystemExit):
            FinanceAnalyzerHost()

    @pytest.mark.asyncio
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
    @patch('host.anthropic.Anthropic')
    async def test_get_claude_response_without_tools(self, mock_anthropic):
        """Test Claude response when no tools are available"""
        # Arrange
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        # Mock Claude API response
        mock_response = Mock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [Mock(text="I can help with general financial questions.")]

        # Create a mock function that returns our mock_response
        def mock_create(*args, **kwargs):
            return mock_response

        mock_client.messages.create = mock_create

        host = FinanceAnalyzerHost()
        host.available_tools = []  # No tools available

        # Act
        result = await host.get_claude_response("What is a stock?")

        # Assert
        assert result == "I can help with general financial questions."

    @pytest.mark.asyncio
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
    @patch('host.anthropic.Anthropic')
    async def test_get_claude_response_with_tools(self, mock_anthropic):
        """Test Claude response when tools are available"""
        # Arrange
        mock_client = Mock()
        mock_anthropic.return_value = mock_client

        # Mock Claude API response with tool use - FIX: Make name a string, not Mock
        mock_content_block = Mock()
        mock_content_block.type = "tool_use"
        mock_content_block.name = "get_stock_quote"  # STRING, not Mock
        mock_content_block.input = {"symbol": "AAPL"}
        mock_content_block.id = "tool_123"

        mock_response = Mock()
        mock_response.stop_reason = "tool_use"
        mock_response.content = [mock_content_block]

        def mock_create(*args, **kwargs):
            return mock_response

        mock_client.messages.create = mock_create

        # Mock tools
        mock_tool = Mock()
        mock_tool.name = "get_stock_quote"
        mock_tool.description = "Get stock quote"
        mock_tool.inputSchema = {"type": "object"}

        host = FinanceAnalyzerHost()
        host.available_tools = [mock_tool]  # Tools available

        # Mock the MCP tool call
        with patch.object(host, 'call_mcp_tool', return_value="AAPL: $150.00") as mock_call_tool:
            # Mock the final Claude response after tool execution
            final_mock_response = Mock()
            final_mock_response.content = [Mock(text="Apple stock is trading at $150.00")]

            # Make the second call return the final response
            mock_client.messages.create = Mock(side_effect=[mock_response, final_mock_response])

            # Act
            result = await host.get_claude_response("What's Apple stock price?")

            # Assert
            mock_call_tool.assert_called_once_with("get_stock_quote", {"symbol": "AAPL"})
            assert result == "Apple stock is trading at $150.00"

@pytest.mark.asyncio
@patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
@patch('host.anthropic.Anthropic')
@patch('host.sse_client')
async def test_connect_to_mcp_server_failure(mock_sse_client, mock_anthropic):
    """Test MCP server connection failure"""
    # Arrange
    mock_anthropic.return_value = Mock()

    # Mock connection failure
    mock_sse_client.side_effect = Exception("Connection failed")

    host = FinanceAnalyzerHost()

    # Act
    result = await host.connect_to_mcp_server()

    # Assert
    assert result == False
    assert len(host.available_tools) == 0

@pytest.mark.asyncio
@patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
@patch('host.anthropic.Anthropic')
async def test_call_mcp_tool_success(mock_anthropic):
    """Test successful MCP tool call"""
    # Arrange
    mock_anthropic.return_value = Mock()

    # Mock MCP session
    mock_session = AsyncMock()
    mock_result = Mock()
    mock_result.content = [Mock(text="AAPL: $150.00")]
    mock_session.call_tool.return_value = mock_result

    host = FinanceAnalyzerHost()
    host.mcp_session = mock_session

    # Act
    result = await host.call_mcp_tool("get_stock_quote", {"symbol": "AAPL"})

    # Assert
    assert result == "AAPL: $150.00"
    mock_session.call_tool.assert_called_once_with("get_stock_quote", {"symbol": "AAPL"})

@pytest.mark.asyncio
@patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
@patch('host.anthropic.Anthropic')
async def test_call_mcp_tool_connection_error(mock_anthropic):
    """Test MCP tool call with connection error"""
    # Arrange
    mock_anthropic.return_value = Mock()

    # Mock MCP session with connection error
    mock_session = AsyncMock()
    mock_session.call_tool.side_effect = Exception("RemoteProtocolError: peer closed connection")

    host = FinanceAnalyzerHost()
    host.mcp_session = mock_session
    host.available_tools = [Mock()]  # Start with tools

    # Act
    result = await host.call_mcp_tool("get_stock_quote", {"symbol": "AAPL"})

    # Assert
    assert "MCP server is no longer available" in result
    assert len(host.available_tools) == 0  # Tools should be cleared

@patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
@patch('host.anthropic.Anthropic')
def test_format_tools_for_claude(mock_anthropic):
    """Test formatting MCP tools for Claude API"""
    # Arrange
    mock_anthropic.return_value = Mock()

    mock_tool = Mock()
    mock_tool.name = "get_stock_quote"
    mock_tool.description = "Get current stock price"
    mock_tool.inputSchema = {
        "type": "object",
        "properties": {"symbol": {"type": "string"}},
        "required": ["symbol"]
    }

    host = FinanceAnalyzerHost()
    host.available_tools = [mock_tool]

    # Act
    claude_tools = host.format_tools_for_claude()

    # Assert
    assert len(claude_tools) == 1
    assert claude_tools[0]["name"] == "get_stock_quote"
    assert claude_tools[0]["description"] == "Get current stock price"
    assert claude_tools[0]["input_schema"]["type"] == "object"

@pytest.mark.asyncio
@patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
@patch('host.anthropic.Anthropic')
@patch('builtins.input')
async def test_run_interactive_quit_command(mock_input, mock_anthropic):
    """Test interactive session with quit command"""
    # Arrange
    mock_anthropic.return_value = Mock()
    mock_input.return_value = "quit"

    host = FinanceAnalyzerHost()

    # Act & Assert - should not raise exception and should exit gracefully
    await host.run_interactive()

    mock_input.assert_called_once()

@pytest.mark.asyncio
@patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-api-key'})
@patch('host.anthropic.Anthropic')
async def test_cleanup_connections(mock_anthropic):
    """Test cleanup of MCP connections"""
    # Arrange
    mock_anthropic.return_value = Mock()

    mock_exit_stack = AsyncMock()
    host = FinanceAnalyzerHost()
    host.exit_stack = mock_exit_stack
    host.mcp_session = Mock()

    # Act
    await host.cleanup_connections()

    # Assert
    mock_exit_stack.aclose.assert_called_once()
    assert host.exit_stack is None
    assert host.mcp_session is None