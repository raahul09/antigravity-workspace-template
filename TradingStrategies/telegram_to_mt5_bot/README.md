# Telegram to MT5 Signal Automation Bot

A production-ready Python service that listens to a Telegram channel or group, parses incoming trading signals, and executes them instantly as market or pending orders on your **MetaTrader 5 (MT5)** terminal.

---

## Architecture

```
┌──────────────────┐      ┌───────────────┐      ┌─────────────────┐      ┌───────────────┐
│ Telegram Channel │ ───> │ Telethon Client│ ───> │ Signal Parser   │ ───> │  MT5 Terminal │
│ (Signal Source)  │      │ (listener.py) │      │ (parser.py)     │      │ (executor.py) │
└──────────────────┘      └───────────────┘      └─────────────────┘      └───────────────┘
```

The system uses **Telethon** (Telegram Client API) to authenticate with your Telegram account. It receives messages in real-time, parses them via **Regex** (deterministic) or an optional **Local LLM** (Ollama Llama 3.2), calculates dynamic lot sizes based on your account equity and Stop Loss distance (enforcing strict risk management), and routes the orders to MT5.

---

## Prerequisites

1. **Operating System**: Windows (required for the official `MetaTrader5` library).
2. **MetaTrader 5 Desktop Terminal**: Installed and logged into your broker (Demo or Live).
3. **Python 3.8+**: Installed and added to your system `PATH`.
4. **Telegram App Credentials**: `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org/) (already configured in `.env`).

---

## Installation & Setup

### Step 1: Open the bot directory
Navigate to the directory containing the bot:
```bash
cd telegram_to_mt5_bot
```

### Step 2: Install dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### Step 3: Configure the `.env` file
Open the `.env` file in the project root and fill in your MetaTrader 5 credentials and options:

```env
# MetaTrader 5 Connection Settings
XAUUSD_BOT_MT5_LOGIN=12345678                 # Your MT5 Account Login ID
XAUUSD_BOT_MT5_PASSWORD=YourPassword          # Your MT5 Account Password
XAUUSD_BOT_MT5_SERVER=Broker-ServerName       # Broker Server Name (e.g. ICMarkets-Demo)

# Telegram API credentials (HappyHootTel)
TELEGRAM_API_ID=4237617
TELEGRAM_API_HASH=d4f471d3558f6cffb45a5f2af8748c0f

# Target Chat to Monitor (Username, Invite Link or numerical Chat ID)
# Keep blank to monitor ALL chats/groups/DMs you receive messages in.
TELEGRAM_SOURCE_CHAT=@MySignalChannel

# Risk Management
TELEGRAM_BOT_DEFAULT_RISK_PERCENT=2.0        # Risks 2% of account equity per trade
TELEGRAM_BOT_MAGIC_NUMBER=888999             # Unique identifier for this bot's trades
TELEGRAM_BOT_DEFAULT_SYMBOL=XAUUSD

# AI Parsing (Optional)
# If enabled, uses a local Ollama instance to parse loose/natural language signals.
TELEGRAM_BOT_USE_LLM_PARSER=False
TELEGRAM_BOT_OLLAMA_BASE_URL=http://127.0.0.1:11434/
TELEGRAM_BOT_OLLAMA_MODEL=llama3.2
```

---

## Running the Bot

Run the main orchestrator script:
```bash
python main.py
```

### First-Time Telegram Authorization:
On the first run, the script will request your authorization in the console:
1. **Phone Number**: Enter your phone number linked to your Telegram account (including country code, e.g. `+1234567890`).
2. **Verification Code**: Enter the login code Telegram sends you.
3. **Password (if enabled)**: Enter your Two-Factor Authentication (2FA) password if you have one.

Once authenticated, a `.session` file will be created locally. Subsequent launches will sign in automatically without prompting for credentials.

---

## Signal Formatting

The default **Regex Parser** is optimized for standard forex signals. Examples of supported formats:

### Example 1: Standard structured format
```text
BUY GOLD
Entry: 2420.50
SL: 2410.00
TP: 2440.00
```

### Example 2: Short form / inline format
```text
sell XAUUSD @ 2435.0 sl:2445 tp:2420
```

### Example 3: Missing entry (executes at market Ask/Bid)
```text
long gold sl=2390 tp=2430
```

---

## Local AI Parsing (Optional)

If your signal channel writes in irregular, conversational text (e.g., *"Team, let's take a quick buy on gold here, stop loss under the recent low at 2405, targeting 2430"*), you can enable the AI parser:

1. Install [Ollama](https://ollama.com) on your PC.
2. Run `ollama run llama3.2` to download and start a local model.
3. In your `.env` file, set `TELEGRAM_BOT_USE_LLM_PARSER=True`.

The bot will now feed complex messages to Llama 3.2 to extract the structured trade details locally, for free, with zero external network leakage.

---

## Verification & Testing

1. **Run Unit Tests**:
   Ensure the parsing engine matches all variations:
   ```bash
   pytest ../tests/test_telegram_parser.py -v
   ```
2. **Use a Demo Account**:
   Always test the integration first on an MT5 Demo account.
3. **Check Logs**:
   Read `telegram_to_mt5.log` to review order calculations, parse logs, or connection issues.
