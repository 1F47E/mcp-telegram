#!/usr/bin/env python3
"""
MCP Telegram Server

An MCP server that provides tools for sending Telegram messages.
The recipient's username/chat_id is configured privately via environment variables.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from telegram import Bot


# --- Configuration ---
class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_chat_id: str
    host: str = "127.0.0.1"
    port: int = 8008
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'


# --- Models ---
class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class JSONRPCNotification(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None


# --- Session Management ---
class SSESession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.event_queue = asyncio.Queue(maxsize=100)
        self.notification_queue = asyncio.Queue(maxsize=100)
        self.initialized = False
        self.closed = False
        
    async def send_event(self, event: str) -> bool:
        if self.closed:
            return False
        try:
            self.event_queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            logging.warning(f"Event queue full for session {self.session_id}")
            return False
    
    async def send_notification(self, notification: JSONRPCNotification) -> bool:
        if self.closed:
            return False
        try:
            self.notification_queue.put_nowait(notification)
            return True
        except asyncio.QueueFull:
            logging.warning(f"Notification queue full for session {self.session_id}")
            return False
    
    def close(self):
        self.closed = True


# --- Global State ---
sessions: Dict[str, SSESession] = {}
settings = Settings()
telegram_bot: Optional[Bot] = None


# --- Telegram Integration ---
async def initialize_telegram():
    global telegram_bot
    try:
        telegram_bot = Bot(token=settings.telegram_bot_token)
        bot_info = await telegram_bot.get_me()
        logging.info(f"Connected to Telegram bot: @{bot_info.username}")
        return True
    except Exception as e:
        logging.error(f"Failed to connect to Telegram: {e}")
        return False


# --- MCP Tool Handlers ---
async def handle_send_message(params: Dict[str, Any]) -> Dict[str, Any]:
    """Send a text message via Telegram"""
    if not telegram_bot:
        raise HTTPException(status_code=500, detail="Telegram bot not initialized")
    
    message = params.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' parameter")
    
    try:
        sent_message = await telegram_bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=message,
            parse_mode="MarkdownV2" if params.get("parse_mode") == "MarkdownV2" else "Markdown"
        )
        
        return {
            "success": True,
            "message_id": sent_message.message_id,
            "chat_id": sent_message.chat_id,
            "text": sent_message.text
        }
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")





# --- MCP Tools Registry ---
TOOLS = {
    "send_message": {
        "handler": handle_send_message,
        "schema": {
            "name": "send_message",
            "description": "Send a text message via Telegram",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message text to send"
                    },
                    "parse_mode": {
                        "type": "string",
                        "enum": ["Markdown", "MarkdownV2", "HTML"],
                        "description": "Text formatting mode",
                        "default": "Markdown"
                    }
                },
                "required": ["message"]
            }
        }
    }
}


# --- MCP Message Handlers ---
async def handle_initialize(params: Dict[str, Any], session: SSESession) -> Dict[str, Any]:
    """Handle MCP initialize request"""
    session.initialized = True
    logging.info(f"Session {session.session_id} initialized")
    
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {}
        },
        "serverInfo": {
            "name": "telegram-mcp-server",
            "version": "1.0.0"
        }
    }


async def handle_tools_list(params: Dict[str, Any], session: SSESession) -> Dict[str, Any]:
    """Handle tools/list request"""
    tools = [tool["schema"] for tool in TOOLS.values()]
    return {"tools": tools}


async def handle_tools_call(params: Dict[str, Any], session: SSESession) -> Dict[str, Any]:
    """Handle tools/call request"""
    tool_name = params.get("name")
    tool_params = params.get("arguments", {})
    
    if tool_name not in TOOLS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
    
    handler = TOOLS[tool_name]["handler"]
    result = await handler(tool_params)
    
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, indent=2)
            }
        ]
    }


# --- MCP Request Router ---
async def handle_mcp_request(request: JSONRPCRequest, session: SSESession) -> Optional[Dict[str, Any]]:
    """Route MCP requests to appropriate handlers"""
    try:
        if request.method == "initialize":
            result = await handle_initialize(request.params or {}, session)
        elif request.method == "tools/list":
            result = await handle_tools_list(request.params or {}, session)
        elif request.method == "tools/call":
            result = await handle_tools_call(request.params or {}, session)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {request.method}"
                }
            }
        
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": result
        }
    
    except HTTPException as e:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": e.status_code,
                "message": e.detail
            }
        }
    except Exception as e:
        logging.error(f"Error handling MCP request {request.method}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }


# --- FastAPI Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Starting Telegram MCP Server...")
    
    if not await initialize_telegram():
        logging.error("Failed to initialize Telegram bot")
        sys.exit(1)
    
    logging.info(f"Server starting on {settings.host}:{settings.port}")
    yield
    
    # Shutdown
    logging.info("Shutting down...")
    for session in sessions.values():
        session.close()


# --- FastAPI App ---
app = FastAPI(
    title="Telegram MCP Server",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- SSE Event Stream ---
async def sse_event_stream(session: SSESession, base_url: str):
    """Generate SSE events for a session"""
    try:
        # Send initial endpoint event
        message_endpoint = f"{base_url}/message?sessionId={session.session_id}"
        yield f"event: endpoint\ndata: {message_endpoint}\n\n"
        
        # Start notification handler
        async def handle_notifications():
            while not session.closed:
                try:
                    notification = await asyncio.wait_for(
                        session.notification_queue.get(), timeout=1.0
                    )
                    if hasattr(notification, 'model_dump_json'):
                        event_data = notification.model_dump_json()
                    else:
                        event_data = json.dumps(notification)
                    await session.send_event(f"event: message\ndata: {event_data}\n\n")
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logging.error(f"Error handling notification: {e}")
                    break
        
        # Start notification handler task
        notification_task = asyncio.create_task(handle_notifications())
        
        # Main event loop
        while not session.closed:
            try:
                # Wait for events with timeout for keep-alive
                event = await asyncio.wait_for(session.event_queue.get(), timeout=15.0)
                yield event
            except asyncio.TimeoutError:
                # Send keep-alive
                yield ": keep-alive\n\n"
            except Exception as e:
                logging.error(f"Error in SSE stream: {e}")
                break
        
        # Clean up
        notification_task.cancel()
        try:
            await notification_task
        except asyncio.CancelledError:
            pass
        
    except Exception as e:
        logging.error(f"SSE stream error: {e}")
    finally:
        session.close()
        if session.session_id in sessions:
            del sessions[session.session_id]


# --- Endpoints ---
@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE endpoint for MCP clients"""
    session_id = str(uuid.uuid4())
    session = SSESession(session_id)
    sessions[session_id] = session
    
    base_url = f"{request.url.scheme}://{request.url.netloc}"
    
    logging.info(f"New SSE connection: {session_id}")
    
    return StreamingResponse(
        sse_event_stream(session, base_url),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.post("/message")
async def message_endpoint(
    request: Request,
    sessionId: str = Query(..., description="Session ID")
):
    """Message endpoint for MCP requests"""
    if sessionId not in sessions:
        raise HTTPException(status_code=400, detail="Invalid session ID")
    
    session = sessions[sessionId]
    if session.closed:
        raise HTTPException(status_code=400, detail="Session closed")
    
    try:
        # Parse JSON-RPC request
        body = await request.json()
        mcp_request = JSONRPCRequest(**body)
        
        # Handle the request
        response = await handle_mcp_request(mcp_request, session)
        
        # Send response via SSE if it exists
        if response:
            response_data = json.dumps(response)
            event = f"event: message\ndata: {response_data}\n\n"
            await session.send_event(event)
        
        return {"status": "accepted"}
        
    except Exception as e:
        logging.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with server info"""
    return {
        "name": "Telegram MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "sse": "/sse",
            "message": "/message"
        }
    }


# --- Main ---
if __name__ == "__main__":
    # Setup logging
    log_level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run server
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level="debug" if settings.debug else "info",
        reload=False
    )
