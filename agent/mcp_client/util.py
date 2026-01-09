import asyncio
import json
import functools
import logging
from typing import Any, Dict, List

# Import from mcp libraries
from mcp.types import Tool as MCPTool, CallToolResult
from .server import MCPServer

logger = logging.getLogger(__name__)

# Import notification helper - use try/except to avoid circular imports
async def send_mcp_notification(event_type: str, tool_name: str, data: dict):
    """Send notification to frontend for MCP tool events"""
    try:
        # Import here to avoid circular dependency
        from tools import send_frontend_notification
        await send_frontend_notification(event_type, {
            "tool": tool_name,
            **data
        })
    except Exception as e:
        logger.debug(f"Could not send notification: {e}")

# A minimal FunctionTool class used by the agent.
class FunctionTool:
    def __init__(self, name: str, description: str, params_json_schema: Dict[str, Any], on_invoke_tool, strict_json_schema: bool = False):
        self.name = name
        self.description = description
        self.params_json_schema = params_json_schema
        self.on_invoke_tool = on_invoke_tool  # This should be an async function.
        self.strict_json_schema = strict_json_schema

    def __repr__(self):
        return f"FunctionTool(name={self.name})"

class MCPUtil:
    @classmethod
    async def get_function_tools(cls, server, convert_schemas_to_strict: bool) -> List[FunctionTool]:
        tools = await server.list_tools()
        function_tools = []
        for tool in tools:
            ft = cls.to_function_tool(tool, server, convert_schemas_to_strict)
            function_tools.append(ft)
        return function_tools

    @classmethod
    def to_function_tool(cls, tool, server, convert_schemas_to_strict: bool) -> FunctionTool:
        # In a more complete implementation, you might convert the JSON schema into a strict version.
        schema = tool.inputSchema

        # Use a default argument to capture the current tool correctly in the closure
        async def invoke_tool(context: Any, input_json: str, current_tool_name=tool.name) -> str:
            try:
                arguments = json.loads(input_json) if input_json else {}
            except Exception as e:
                # Return error message as string
                return f"Error parsing input JSON for tool '{current_tool_name}': {e}"
            
            try:
                # Send notification that knowledge base search is starting (only for knowledge_base_search)
                if current_tool_name == "knowledge_base_search":
                    query = arguments.get('query', 'unknown query')
                    await send_mcp_notification("tool_started", current_tool_name, {
                        "message": f"Searching knowledge base for: {query}",
                        "query": query
                    })
                
                # Try to call the tool with automatic reconnection on connection errors
                max_retries = 2
                for attempt in range(max_retries):
                    try:
                        result = await server.call_tool(current_tool_name, arguments)
                        break  # Success, exit retry loop
                    except Exception as connection_error:
                        # Check if it's a connection error (ClosedResourceError, etc.)
                        error_type = type(connection_error).__name__
                        if 'Closed' in error_type or 'Connection' in error_type or 'Stream' in error_type:
                            if attempt < max_retries - 1:
                                # Attempt to reconnect
                                print(f"⚠️ MCP connection closed, attempting to reconnect (attempt {attempt + 1}/{max_retries})...")
                                try:
                                    await server.cleanup()
                                    await server.connect()
                                    print("✅ Reconnected to MCP server")
                                    continue  # Retry the tool call
                                except Exception as reconnect_error:
                                    print(f"❌ Failed to reconnect: {reconnect_error}")
                                    if attempt == max_retries - 1:
                                        return f"Error: MCP connection closed and reconnection failed: {reconnect_error}"
                            else:
                                return f"Error: MCP connection closed after {max_retries} attempts: {connection_error}"
                        else:
                            # Not a connection error, re-raise
                            raise
                
                # Handle CallToolResult object (from MCP SDK)
                # CallToolResult has .content attribute which is a list of content items
                result_text = ""
                if hasattr(result, 'content'):
                    content_list = result.content
                    if content_list and len(content_list) >= 1:
                        if len(content_list) == 1:
                            content_item = content_list[0]
                            # Content items have .text or other attributes
                            if hasattr(content_item, 'text'):
                                result_text = str(content_item.text)
                            elif hasattr(content_item, 'data'):
                                result_text = str(content_item.data)
                            else:
                                result_text = str(content_item)
                        else:
                            # Multiple content items - extract text from each
                            texts = []
                            for item in content_list:
                                if hasattr(item, 'text'):
                                    texts.append(str(item.text))
                                elif hasattr(item, 'data'):
                                    texts.append(str(item.data))
                                else:
                                    texts.append(str(item))
                            result_text = "\n".join(texts)
                    else:
                        result_text = "No content returned from tool"
                
                # Fallback for dict-like results
                elif isinstance(result, dict):
                    if "content" in result and isinstance(result["content"], list) and len(result["content"]) >= 1:
                        if len(result["content"]) == 1:
                            content_item = result["content"][0]
                            if isinstance(content_item, (str, int, float, bool)):
                                result_text = str(content_item)
                            else:
                                try:
                                    result_text = json.dumps(content_item)
                                except TypeError:
                                    result_text = str(content_item)
                        else:
                            try:
                                result_text = json.dumps(result["content"])
                            except TypeError:
                                result_text = str(result["content"])
                    else:
                        try:
                            result_text = json.dumps(result)
                        except TypeError:
                            result_text = str(result)
                else:
                    result_text = str(result)
                
                # Send success notification for knowledge_base_search
                if current_tool_name == "knowledge_base_search":
                    query = arguments.get('query', 'unknown query')
                    await send_mcp_notification("tool_success", current_tool_name, {
                        "message": "Knowledge base search completed",
                        "query": query,
                        "preview": result_text[:150] if result_text else "No results found"
                    })
                
                return result_text
                    
            except Exception as e:
                 # Catch errors during tool call itself
                 import traceback
                 traceback.print_exc()
                 
                 # Send error notification for knowledge_base_search
                 if current_tool_name == "knowledge_base_search":
                     query = arguments.get('query', 'unknown query')
                     await send_mcp_notification("tool_error", current_tool_name, {
                         "message": "Knowledge base search failed",
                         "query": query,
                         "error": str(e)
                     })
                 
                 return f"Error calling tool '{current_tool_name}': {e}"

        return FunctionTool(
            name=tool.name,
            description=tool.description,
            params_json_schema=schema,
            on_invoke_tool=invoke_tool,
            strict_json_schema=convert_schemas_to_strict,
        )