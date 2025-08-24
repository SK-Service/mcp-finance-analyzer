#!/usr/bin/env python3
"""
Finance Analyzer Host Application - HTTP Client
Connects to independent MCP server via HTTP and integrates with Claude LLM
"""
import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
from contextlib import AsyncExitStack

from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# MCP client imports for HTTP transport
from mcp import ClientSession
from mcp.client.sse import sse_client

class FinanceAnalyzerHost:
    def __init__(self):
        """Initialize the Finance Analyzer Host."""
        self.anthropic_client = None
        self.mcp_session = None
        self.available_tools = []
        self.exit_stack = None
        self.server_url = "http://localhost:8000/sse"
        self.max_retries = 3
        self.base_delay = 1.0  # Initial delay in seconds
        self.proceed_without_tools = False  # Remember user choice
        
        # Get API keys
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            print("Error: ANTHROPIC_API_KEY not found in environment variables")
            print("Please add your Anthropic API key to the .env file")
            sys.exit(1)
        
        # Initialize Anthropic client
        try:
            self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        except Exception as e:
            print(f"Error initializing Anthropic client: {e}")
            sys.exit(1)
    
    async def connect_to_mcp_server(self) -> bool:
        """Connect to MCP server with exponential backoff retry."""
        print("Connecting to Finance MCP Server...")
        print(f"Server URL: {self.server_url}")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"Connection attempt {attempt}/{self.max_retries}...")
                
                # Create exit stack for proper resource management
                if self.exit_stack:
                    await self.cleanup_connections()
                
                self.exit_stack = AsyncExitStack()
                
                # Connect to SSE server with timeout
                sse_streams = await asyncio.wait_for(
                    self.exit_stack.enter_async_context(sse_client(self.server_url)),
                    timeout=10.0
                )
                read_stream, write_stream = sse_streams
                
                # Create ClientSession
                self.mcp_session = await self.exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                
                print("Initializing MCP session...")
                await asyncio.wait_for(self.mcp_session.initialize(), timeout=10.0)
                
                print("Connected to MCP server successfully!")
                
                # Discover available tools
                success = await self.discover_tools()
                if success:
                    return True
                else:
                    print("Failed to discover tools, retrying...")
                    
            except asyncio.TimeoutError:
                print(f"Connection attempt {attempt} timed out")
            except Exception as e:
                print(f"Connection attempt {attempt} failed: {type(e).__name__}")
                # Don't print the full traceback for connection errors
                if "ConnectError" not in str(type(e)):
                    print(f"Details: {e}")
            
            # Cleanup failed attempt
            await self.cleanup_connections()
            
            # Exponential backoff (don't wait after last attempt)
            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** (attempt - 1))
                print(f"Waiting {delay:.1f} seconds before retry...")
                await asyncio.sleep(delay)
        
        print("Failed to connect to MCP server after all retry attempts")
        print("\nTroubleshooting:")
        print("1. Make sure the MCP server is running: python src/finance_mcp_server.py")
        print("2. Check that the server is accessible at http://localhost:8000")
        print("3. Verify your network connection and firewall settings")
        return False
    
    async def discover_tools(self) -> bool:
        """Discover tools available from the MCP server."""
        print("Discovering available tools...")
        
        try:
            # List available tools with timeout
            tools_response = await asyncio.wait_for(
                self.mcp_session.list_tools(), 
                timeout=5.0
            )
            print(f"Found {len(tools_response.tools)} tools on server" if tools_response.tools else "No tools found")
            self.available_tools = tools_response.tools
            
            if self.available_tools:
                print(f"Found {len(self.available_tools)} tools:")
                for tool in self.available_tools:
                    print(f"  > {tool.name}: {tool.description}")
                return True
            else:
                print("No tools found on server")
                return False
                
        except asyncio.TimeoutError:
            print("Tool discovery timed out")
            return False
        except Exception as e:
            print(f"Error discovering tools: {type(e).__name__}")
            return False
    
    def format_tools_for_claude(self) -> List[Dict[str, Any]]:
        """Format MCP tools for Claude API."""
        claude_tools = []
        
        for tool in self.available_tools:
            try:
                claude_tool = {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                }
                claude_tools.append(claude_tool)
            except Exception as e:
                print(f"Warning: Failed to format tool {tool.name}: {e}")
        
        return claude_tools
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool and return the result with graceful error handling."""
        try:
            print(f"Calling tool: {tool_name} with args: {arguments}")
            
            # Call the tool via MCP with timeout
            result = await asyncio.wait_for(
                self.mcp_session.call_tool(tool_name, arguments),
                timeout=30.0
            )
            
            # Extract text content from result
            if result.content and len(result.content) > 0:
                print(f"Tool {tool_name} executed successfully with result: {result.content[0].text}")
                return result.content[0].text
            else:
                return f"Tool {tool_name} executed but returned no content"
                
        except asyncio.TimeoutError:
            return f"Tool {tool_name} timed out after 30 seconds - MCP server may be unavailable"
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e).lower()
            
            # Check if this is a connection/server down error
            connection_keywords = [
                'connection', 'protocol', 'remote', 'disconnect', 'closed', 
                'reset', 'refused', 'unreachable', 'timeout', 'network'
            ]
            
            if any(keyword in error_type.lower() or keyword in error_msg for keyword in connection_keywords):
                # Server is down - mark tools as unavailable and inform user
                self.available_tools = []
                return ("MCP server is no longer available. The server may have been shut down. "
                       "You can continue with general questions or restart the server and try again.")
            else:
                # Other type of error
                return f"Error calling tool {tool_name}: {error_type}"
    
    async def get_claude_response(self, user_message: str) -> str:
        """Single method for all Claude interactions - handles both with/without tools."""
        try:
            print(f"Sending to Claude: {user_message}")
            
            # Prepare tools for Claude
            claude_tools = self.format_tools_for_claude()
            
            # Create the message
            messages = [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
            
            # If no tools available, let Claude know
            if not claude_tools:
                messages.append({
                    "role": "system", 
                    "content": "Note: MCP server tools are currently unavailable. Provide a helpful response based on general knowledge."
                })
            
            print(f"Messages being sent to Claude: {messages}")
            # Call Claude with tools (if available)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    tools=claude_tools if claude_tools else None,
                    messages=messages
                ),
                timeout=30.0
            )

            print(f"Claude response received: {response.content[0].text} and stop reason: {response.stop_reason}")
            
            # Process Claude's response
            if response.stop_reason == "tool_use" and claude_tools:
                # Claude wants to use a tool
                return await self.handle_tool_use(response, messages)
            else:
                # Claude responded directly
                return response.content[0].text
                
        except asyncio.TimeoutError:
            return "Claude request timed out after 30 seconds"
        except Exception as e:
            error_type = type(e).__name__
            if "authentication" in error_type.lower():
                return "Authentication error with Claude API. Please check your ANTHROPIC_API_KEY."
            else:
                return f"Error communicating with Claude: {error_type}"
    
    async def handle_tool_use(self, response, messages: List[Dict]) -> str:
        """Handle when Claude wants to use tools."""
        try:
            # Add Claude's response to message history
            assistant_message = {
                "role": "assistant",
                "content": response.content
            }
            messages.append(assistant_message)
            
            # Execute each tool call
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input
                    tool_call_id = content_block.id
                    
                    # Call the MCP tool
                    tool_result = await self.call_mcp_tool(tool_name, tool_input)
                    
                    # Add tool result to messages
                    tool_result_message = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_call_id,
                                "content": tool_result
                            }
                        ]
                    }
                    messages.append(tool_result_message)
            
            print(f"message being sent to Claude after tool execution: {messages}")
            # Get Claude's final response after tool execution
            final_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    tools=self.format_tools_for_claude(),
                    messages=messages
                ),
                timeout=30.0
            )
            
            return final_response.content[0].text
            
        except asyncio.TimeoutError:
            return "Tool execution timed out"
        except Exception as e:
            return f"Error during tool execution: {type(e).__name__}"
    
    async def run_interactive(self):
        """Run interactive chat session."""
        print("\n" + "=" * 50)
        print("Finance Analyzer Ready!")
        print("Ask me about stocks, crypto, or financial analysis.")
        print("Type 'quit', 'exit', or 'q' to exit.")
        print("=" * 50 + "\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Check if we need to try connecting to MCP server
                if not self.available_tools and not self.proceed_without_tools:
                    print("No MCP tools available. Attempting to connect to server...")
                    connected = await self.connect_to_mcp_server()
                    
                    if not connected:
                        print("\nUnable to connect to MCP server.")
                        choice = input("Proceed without financial tools? (yes/no): ").strip().lower()
                        
                        if choice in ['yes', 'y']:
                            self.proceed_without_tools = True
                            print("Continuing with general questions only...")
                        else:
                            print("Please start the MCP server and try again.")
                            continue
                
                # Get response from Claude
                response = await self.get_claude_response(user_input)
                print(f"\nClaude: {response}\n")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break
            except Exception as e:
                error_type = type(e).__name__
                print(f"An unexpected error occurred: {error_type}")
                print("Please try again or type 'quit' to exit.")
    
    async def cleanup_connections(self):
        """Clean up MCP connections only."""
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except Exception:
            pass  # Ignore cleanup errors
        finally:
            self.exit_stack = None
            self.mcp_session = None
    
    async def cleanup(self):
        """Clean up all resources properly."""
        print("Cleaning up resources...")
        await self.cleanup_connections()
        print("Cleanup completed")

async def main():
    """Main function."""
    print("=" * 60)
    print("Finance Analyzer with MCP Integration (HTTP Client)")
    print("=" * 60)
    
    try:
        host = FinanceAnalyzerHost()
        
        # Try to connect to MCP server with retry
        connected = await host.connect_to_mcp_server()
        
        if connected:
            # Run interactive session
            await host.run_interactive()
        else:
            print("Unable to connect to MCP server. Exiting gracefully.")
            return
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}")
        print("Application will exit because of an error.")
    finally:
        # Always cleanup
        try:
            await host.cleanup()
        except:
            pass  # Ignore cleanup errors

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception:
        print("Application terminated")
    finally:
        sys.exit(0)  # Always exit cleanly