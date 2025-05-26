# MCP Telegram Server

🤖 A Model Context Protocol (MCP) server that provides Telegram messaging capabilities via Server-Sent Events (SSE). Send messages to Telegram through any MCP-compatible client like Cursor, Claude Desktop, or custom applications.

## Features

- **🔌 SSE-based MCP Server** - Modern event-driven architecture
- **📱 Telegram Integration** - Send text messages with Markdown formatting
- **🐳 Docker Ready** - Containerized for easy deployment
- **🔒 Privacy First** - Bot token and chat ID configured via environment variables
- **⚡ Real-time** - Bidirectional communication via Server-Sent Events
- **🛡️ Production Ready** - Health checks, logging, and auto-restart

## Quick Start with Docker

### 1. Setup Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Save the bot token provided

### 2. Get Your Chat ID

Send a message to your bot, then visit:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```
Look for `chat.id` in the response.

### 3. Configure Environment

Create a `.env` file:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Run with Docker Compose

Create `docker-compose.yml`:
```yaml
services:
  telegram-mcp:
    image: mcp-telegram-server
    build: .
    ports:
      - "8008:8008"
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - HOST=0.0.0.0
      - PORT=8008
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8008/"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Start the server:
```bash
docker-compose up -d
```

## MCP Client Configuration

### Cursor IDE

Add to your MCP settings:
```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8008/sse"
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "telegram": {
      "url": "http://localhost:8008/sse"
    }
  }
}
```

## Available Tools

### notify\_with\_telegram:text
Send a text message to your configured Telegram chat using basic HTML formatting.

**Parameters:**
- `message` (required): The text message to send. Can include supported HTML tags.

**Example:**
```json
{
  "message": "Hello from MCP! 🚀\n\n<b>Bold text</b> and <i>italic text</i>. More info: <a href=\"http://www.example.com/\">example.com</a>. Remember to use &lt; &gt; &amp; for special characters like this: 5 &gt; 3."
}
```

### Supported HTML Formatting

When sending messages, you can use the following HTML tags for formatting. Make sure to properly close all tags and escape special characters (`<`, `>`, `&`) within your text content and `href` attributes using `&lt;`, `&gt;`, and `&amp;` respectively.

- **Bold:**
  `<b>bold text</b>`
  `<strong>bold text</strong>`

- **Italic:**
  `<i>italic text</i>`
  `<em>italic text</em>`

- **Underline:**
  `<u>underlined text</u>`
  `<ins>underlined text</ins>`

- **Strikethrough:**
  `<s>strikethrough text</s>`
  `<strike>strikethrough text</strike>`
  `<del>strikethrough text</del>`

- **Spoiler:**
  `<span class="tg-spoiler">spoiler text</span>`
  `<tg-spoiler>spoiler text</tg-spoiler>`

- **Inline Link:**
  `<a href="URL_HERE">link text</a>`
  Example: `<a href="https://telegram.org">Telegram</a>`

- **Inline Code:**
  `<code>inline fixed-width code</code>`
  Example: `<code>my_variable = 10;</code>`

- **Pre-formatted Code Block:**
  `<pre>multi-line
fixed-width code block</pre>`

- **Pre-formatted Code Block (with language specification):**
  `<pre><code class="language-yourlanguage">your code here</code></pre>`
  Example: `<pre><code class="language-python">def hello():
  print("Hello, HTML!")</code></pre>`

**Nesting and Tag Restrictions:**
- Tags must be correctly nested (e.g., `<b><i>bold italic</i></b>`).
- `<b>`, `<i>`, `<u>`, `<s>`, and spoiler tags can contain and be part of other entities, except for `<pre>` and `<code>`.
- Other entities (like `<a>`, `<code>`, `<pre>`) cannot contain each other.
- Only the HTML tags listed above are supported by Telegram.

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from BotFather | ✅ Yes | - |
| `TELEGRAM_CHAT_ID` | Target chat ID for messages | ✅ Yes | - |
| `HOST` | Server bind address | No | `127.0.0.1` |
| `PORT` | Server port | No | `8008` |
| `DEBUG` | Enable debug logging | No | `false` |

## Docker Commands

### Build and Run
```bash
# Build image
docker build -t mcp-telegram-server .

# Run container
docker run -d \
  --name mcp-telegram-server \
  -p 8008:8008 \
  --env-file .env \
  mcp-telegram-server
```

### Management
```bash
# View logs
docker logs -f mcp-telegram-server

# Restart server
docker restart mcp-telegram-server

# Stop server
docker stop mcp-telegram-server

# Remove container
docker rm mcp-telegram-server
```

### With Docker Compose
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## API Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/` | GET | Server info and health check |
| `/sse` | GET | SSE endpoint for MCP clients |
| `/message` | POST | JSON-RPC message endpoint |

## Testing

Test the server is working:
```bash
# Health check
curl http://localhost:8008/

# Expected response:
{
  "name": "Telegram MCP Server",
  "version": "1.0.0",
  "endpoints": {
    "sse": "/sse",
    "message": "/message"
  }
}
```

## Development

### Local Development
```bash
# Clone repository
git clone <repository-url>
cd mcp-telegram

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your credentials

# Run server
python main.py
```

### Project Structure
```
mcp-telegram/
├── main.py              # Main server application
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
├── .env                # Environment variables (create from env.example)
├── env.example         # Environment template
└── README.md           # This file
```

## Security Considerations

- **Environment Variables**: Never commit `.env` files to version control
- **Network Access**: The server runs on all interfaces (`0.0.0.0`) when containerized
- **Bot Token**: Keep your Telegram bot token secure and rotate regularly
- **Chat ID**: Only the configured chat ID can receive messages

## Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker logs mcp-telegram-server

# Common causes:
# - Missing .env file
# - Invalid bot token
# - Invalid chat ID
```

**MCP client can't connect:**
```bash
# Verify server is running
curl http://localhost:8008/

# Check SSE endpoint
curl -N -H "Accept: text/event-stream" http://localhost:8008/sse
```

**Messages not sending:**
- Verify bot token is correct
- Confirm chat ID is valid (try both positive and negative values for groups)
- Check that the bot can send messages to the target chat

## License

MIT License - see LICENSE file for details.

## Support

- 🐛 Issues: [GitHub Issues](link-to-issues)
- 📖 Documentation: [GitHub Wiki](link-to-wiki)
- 💬 Discussions: [GitHub Discussions](link-to-discussions) 