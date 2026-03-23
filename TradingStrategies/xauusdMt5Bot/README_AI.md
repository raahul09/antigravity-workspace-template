# XOS SMC AI EA - Setup Guide

## Overview

This guide walks you through setting up AI-powered trading with the **XOS SMC AI Expert Advisor**. The system combines Smart Money Concepts (SMC) strategy with Anthropic Claude AI for trade confirmation.

## Architecture

```
MT5 Terminal (MQL5 EA)
    │
    │ Writes: ai_request.txt
    │ Reads:  ai_response.txt
    │
    ▼
Python AI Bridge (ai_bridge.py)
    │
    │ Calls Claude API
    │
    ▼
Anthropic Claude AI
```

---

## Prerequisites

### 1. Python Installation

Download and install Python 3.8+ from: https://www.python.org/downloads/

During installation, check: **✓ Add Python to PATH**

### 2. Anthropic API Key

1. Visit: https://console.anthropic.com
2. Sign up / Log in
3. Go to **API Keys** section
4. Click **Create Key**
5. Copy your key (starts with `sk-ant-...`)
6. **Important:** Save it securely - you can only see it once!

### 3. MT5 Terminal

Ensure MetaTrader 5 is installed and you have an active broker account.

---

## Installation Steps

### Step 1: Install Python Dependencies

Open Command Prompt (cmd) and run:

```bash
pip install anthropic watchdog
```

Verify installation:

```bash
pip show anthropic
pip show watchdog
```

### Step 2: Configure API Key

**Option A: Environment Variable (Recommended)**

```bash
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Option B: Edit ai_bridge.py**

Open `ai_bridge.py` and update line 24:

```python
ANTHROPIC_API_KEY = "sk-ant-your-actual-key-here"
```

### Step 3: Configure MT5 Path (If Needed)

By default, the bridge looks for MT5 at:
```
C:\Program Files\MetaTrader 5
```

If your MT5 is installed elsewhere, set the environment variable:

```bash
set MT5_PATH=C:\Your\MT5\Path
```

### Step 4: Copy EA Files to MT5

1. **Copy the EA:**
   - Copy `xos_smc_ai_ea.mq5` to:
     ```
     <MT5_Install>\MQL5\Experts\
     ```

2. **Compile in MetaEditor:**
   - Open MetaEditor (F4 in MT5)
   - Open `xos_smc_ai_ea.mq5`
   - Press F7 to compile
   - Verify: 0 errors, 0 warnings

---

## Running the System

### Step 1: Start the AI Bridge

Open Command Prompt in the `xauusdMt5Bot` folder:

```bash
cd D:\AntiGravity WorkSpace\antigravity-workspace-template\TradingStrategies\xauusdMt5Bot
python ai_bridge.py
```

You should see:

```
2024-03-23 17:00:00 - INFO - ==================================================
2024-03-23 17:00:00 - INFO - MQL5 AI Bridge Service Starting
2024-03-23 17:00:00 - INFO - ==================================================
2024-03-23 17:00:00 - INFO - MT5 Files Path: C:\Program Files\MetaTrader 5\MQL5\Files
2024-03-23 17:00:00 - INFO - Claude Model: claude-sonnet-4-5-20250929
2024-03-23 17:00:00 - INFO - Watching: C:\Program Files\MetaTrader 5\MQL5\Files
2024-03-23 17:00:00 - INFO - Waiting for ai_request.txt files...
2024-03-23 17:00:00 - INFO - Press Ctrl+C to stop
```

**Keep this window open** - the bridge runs continuously.

### Step 2: Attach EA to Chart in MT5

1. Open MT5 terminal
2. Load **XAUUSD** chart (M15 timeframe recommended)
3. In Navigator → Expert Advisors, find `xos_smc_ai_ea`
4. Drag onto the XAUUSD chart
5. In the settings dialog:
   - **Common** tab: ✓ Allow Algo Trading, ✓ Allow DLL imports
   - **Inputs** tab: Configure as needed (see below)
6. Click **OK**
7. Enable **AutoTrading** (green button in toolbar)

### Step 3: Verify Connection

**In MT5 Experts tab**, you should see:

```
[XOS SMC AI] === XOS SMC AI EA Initialized ===
[XOS SMC AI] Symbol: XAUUSD | Risk: 2.00%
[XOS SMC AI] AI Enabled: YES
[XOS SMC AI] File paths initialized
```

**When a trade setup occurs:**

```
[XOS SMC AI] BULLISH SWEEP DETECTED at 2015.50
[XOS SMC AI] AI request sent, waiting for response...
[XOS SMC AI] AI Response: BUY (Confidence: 75%)
[XOS SMC AI] Reasoning: RSI oversold + EMA support confluence
[XOS SMC AI] AI confirmation received - executing trade
[XOS SMC AI] BUY executed. Lot: 0.15 SL: 2005.00 TP: 2025.00
```

---

## Configuration Options

### EA Input Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `inpEnableAI` | true | Enable AI confirmation |
| `inpAIConfidenceMin` | 60 | Minimum AI confidence % to trade |
| `inpAITimeoutSec` | 30 | Max seconds to wait for AI response |
| `inpRiskPercent` | 2.0 | Risk per trade (%) |
| `inpRewardToRisk` | 1.0 | Take profit R:R multiple |
| `inpUseTrailingStop` | true | Enable trailing stop |
| `inpBreakEvenPoints` | 50 | Points for break-even move |

### AI Bridge Configuration

Edit `ai_bridge.py` to customize:

```python
ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"  # Change model
RESPONSE_TIMEOUT_SECONDS = 30                   # API timeout
```

---

## Testing

### Test 1: Verify File I/O

1. Create a test request file manually:
   ```
   C:\Program Files\MetaTrader 5\MQL5\Files\ai_request.txt
   ```
   Content:
   ```
   Symbol: XAUUSD
   Price: 2015.50
   RSI: 45.0
   ```

2. Check if `ai_response.txt` appears within 5 seconds

3. Read the response - should contain SIGNAL, CONFIDENCE, etc.

### Test 2: Paper Trading

1. Use a **Demo account** in MT5
2. Run the system for 1-2 weeks
3. Monitor:
   - Win rate
   - AI accuracy
   - API costs

### Test 3: Adjust AI Confidence

- If too many losing trades: Increase `inpAIConfidenceMin` to 70-80%
- If missing good trades: Decrease to 50-55%

---

## Troubleshooting

### AI Bridge Won't Start

**Error: ANTHROPIC_API_KEY not set**

```bash
set ANTHROPIC_API_KEY=sk-ant-your-key
python ai_bridge.py
```

**Error: MT5 Files path does not exist**

```bash
set MT5_PATH=C:\Your\Actual\MT5\Path
python ai_bridge.py
```

### No AI Response

1. Check `ai_bridge.log` for errors
2. Verify API key is valid
3. Check internet connection
4. Test API manually:
   ```python
   from anthropic import Anthropic
   client = Anthropic(api_key="sk-ant-...")
   response = client.messages.create(...)
   print(response)
   ```

### EA Shows "AI OFFLINE"

1. Ensure Python bridge is running
2. Check Experts log for file path errors
3. Verify `MQL5/Files/` folder is accessible

### Compilation Errors

- Ensure MT5 is updated to latest version
- Check all `#include` paths are valid
- Use MetaEditor from the same MT5 instance

---

## API Costs

**Anthropic Claude Pricing** (as of 2024):

| Model | Cost per 1K tokens | ~Cost per signal |
|-------|-------------------|------------------|
| Claude 3.5 Sonnet | $0.003 | ~$0.005 |
| Claude 3 Opus | $0.015 | ~$0.02 |

**Example: 50 signals/day**
- Claude 3.5 Sonnet: ~$0.25/day = ~$7.50/month
- Claude 3 Opus: ~$1.00/day = ~$30/month

**Tip:** Start with Claude 3.5 Sonnet - best value for trading analysis.

---

## Best Practices

1. **Start on Demo:** Never test new systems on live accounts first

2. **Monitor API Usage:** Check Anthropic console for usage limits

3. **Keep Bridge Running:** Start AI bridge before MT5 each day

4. **Review AI Reasoning:** Don't blindly follow - read the analysis

5. **Adjust Parameters:** Tune confidence threshold based on performance

6. **Backup Config:** Save your working parameter sets

7. **Log Analysis:** Review `ai_bridge.log` weekly for patterns

---

## Security Notes

- **Never commit API keys** to git or share publicly
- Use **environment variables** for keys in production
- Store backup keys in password manager
- Monitor API usage for unusual activity

---

## Support Files

| File | Purpose |
|------|---------|
| `ai_bridge.py` | Python bridge script |
| `xos_smc_ai_ea.mq5` | MQL5 Expert Advisor |
| `ai_bridge.log` | Bridge logs (auto-created) |
| `ai_request.txt` | EA → Bridge (auto-created) |
| `ai_response.txt` | Bridge → EA (auto-created) |
| `ai_error.txt` | Error messages (auto-created) |

---

## Quick Start Checklist

- [ ] Python 3.8+ installed
- [ ] `pip install anthropic watchdog` completed
- [ ] Anthropic API key obtained
- [ ] API key set in environment or config
- [ ] EA copied to `MQL5/Experts/`
- [ ] EA compiled with 0 errors
- [ ] AI bridge started (Python window open)
- [ ] EA attached to XAUUSD chart
- [ ] AutoTrading enabled (green)
- [ ] Experts log shows "AI Enabled: YES"
- [ ] Test signal received and executed

---

**Ready to trade with AI confirmation!**

For issues, check logs first:
- MT5: Experts tab + Journal tab
- Bridge: `ai_bridge.log` file
