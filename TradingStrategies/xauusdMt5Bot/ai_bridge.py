"""
AI Bridge for MQL5 Expert Advisor
=================================

This script monitors the MQL5/Files/ folder for trading analysis requests
from the MQL5 EA, calls Ollama local LLM API, and writes the response back.

Architecture:
    MQL5 EA -> ai_request.txt -> This Script -> Ollama API -> ai_response.txt -> MQL5 EA

Usage:
    pip install requests watchdog
    python ai_bridge.py
"""

import os
import time
import logging
import requests
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === Configuration ===

# Path to MT5 Files folder (adjust to your MT5 installation)
MT5_FILES_PATH = os.path.join(
    os.environ.get("MT5_PATH", "C:\\Program Files\\MetaTrader 5"),
    "MQL5",
    "Files"
)

# Ollama configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")  # or "mistral", "codellama", etc.

# File names
REQUEST_FILE = "ai_request.txt"
RESPONSE_FILE = "ai_response.txt"
ERROR_FILE = "ai_error.txt"

# Timeout settings
REQUEST_TIMEOUT = 60  # Seconds to wait for LLM response

# === Logging Setup ===

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ai_bridge.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# === Ollama API Client ===

class OllamaTradingAnalyst:
    """Analyzes market data and provides trading decisions using Ollama LLM."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model

    def analyze_market(self, market_data: str) -> dict:
        """
        Send market data to Ollama and get trading decision.

        Args:
            market_data: Formatted market data string

        Returns:
            dict with keys: signal, confidence, reasoning, sl, tp, risk
        """
        prompt = self._build_prompt(market_data)

        try:
            logger.info(f"Calling Ollama API at {self.base_url}...")

            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 500
                    }
                },
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()
            result = response.json()
            answer = result.get("response", "")

            logger.info(f"Ollama response received ({len(answer)} chars)")
            return self._parse_response(answer)

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama. Is it running?")
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reasoning": "Ollama not running. Start with: ollama serve",
                "sl": 0,
                "tp": 0,
                "risk": "Ollama connection failed"
            }
        except requests.exceptions.Timeout:
            logger.error(f"Ollama request timed out after {REQUEST_TIMEOUT}s")
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reasoning": f"Request timeout after {REQUEST_TIMEOUT}s",
                "sl": 0,
                "tp": 0,
                "risk": "API timeout"
            }
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return {
                "signal": "HOLD",
                "confidence": 0,
                "reasoning": f"API Error: {str(e)}",
                "sl": 0,
                "tp": 0,
                "risk": "API error occurred"
            }

    def _build_prompt(self, market_data: str) -> str:
        """Build the prompt for trading analysis."""
        return f"""You are an expert trading analyst analyzing XAUUSD (Gold) market data.

Your task is to evaluate the trading setup and provide a clear decision.

=== MARKET DATA ===
{market_data}

=== SMC STRATEGY SIGNAL ===
The MQL5 bot has detected a Smart Money Concepts (SMC) liquidity sweep signal.

=== YOUR ANALYSIS TASK ===
1. Evaluate if this is a high-quality trade setup
2. Consider the confluence of indicators (EMA, RSI, ATR)
3. Assess the risk/reward ratio
4. Check for any warning signs

=== RESPONSE FORMAT ===
You MUST respond in this EXACT format (one line per field):

SIGNAL: BUY or SELL or HOLD
CONFIDENCE: 0-100 (integer percentage)
REASONING: One sentence explaining your analysis
SL: Stop loss price level
TP: Take profit price level
RISK: Any risk warnings or "Normal" if no concerns

=== EXAMPLE RESPONSE ===
SIGNAL: BUY
CONFIDENCE: 75
REASONING: RSI oversold at 45 combined with EMA support confirms the sweep pattern
SL: 2005.00
TP: 2025.00
RISK: Normal volatility expected

=== IMPORTANT RULES ===
- Only recommend BUY or SELL if you have >60% confidence
- Otherwise recommend HOLD
- SL should be below entry for BUY, above entry for SELL
- TP should provide at least 1:1 risk/reward
- Be conservative - it's better to miss a trade than lose money

Now analyze the market data above and provide your trading decision."""

    def _parse_response(self, response_text: str) -> dict:
        """Parse LLM response into structured format."""
        result = {
            "signal": "HOLD",
            "confidence": 0,
            "reasoning": "",
            "sl": 0.0,
            "tp": 0.0,
            "risk": ""
        }

        lines = response_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith("SIGNAL:"):
                result["signal"] = line.replace("SIGNAL:", "").strip().upper()
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = int(line.replace("CONFIDENCE:", "").strip())
                except ValueError:
                    result["confidence"] = 0
            elif line.startswith("REASONING:"):
                result["reasoning"] = line.replace("REASONING:", "").strip()
            elif line.startswith("SL:"):
                try:
                    result["sl"] = float(line.replace("SL:", "").strip())
                except ValueError:
                    result["sl"] = 0.0
            elif line.startswith("TP:"):
                try:
                    result["tp"] = float(line.replace("TP:", "").strip())
                except ValueError:
                    result["tp"] = 0.0
            elif line.startswith("RISK:"):
                result["risk"] = line.replace("RISK:", "").strip()

        return result


# === File Handler ===

class MQL5FileHandler(FileSystemEventHandler):
    """Monitors MQL5 Files folder for request files."""

    def __init__(self, analyst: OllamaTradingAnalyst):
        super().__init__()
        self.analyst = analyst
        self.request_path = os.path.join(MT5_FILES_PATH, REQUEST_FILE)
        self.response_path = os.path.join(MT5_FILES_PATH, RESPONSE_FILE)
        self.error_path = os.path.join(MT5_FILES_PATH, ERROR_FILE)
        self.processing = False

    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return

        if os.path.basename(event.src_path) == REQUEST_FILE:
            logger.info(f"Request file detected: {event.src_path}")
            self.process_request(event.src_path)

    def on_modified(self, event):
        """Handle file modifications."""
        if event.is_directory:
            return

        if os.path.basename(event.src_path) == REQUEST_FILE:
            if not self.processing:
                logger.info(f"Request file modified: {event.src_path}")
                self.process_request(event.src_path)

    def process_request(self, filepath: str):
        """Process the request file and generate response."""
        self.processing = True

        try:
            # Wait briefly to ensure file is fully written
            time.sleep(0.5)

            # Read request data
            if not os.path.exists(filepath):
                logger.warning("Request file disappeared")
                return

            with open(filepath, 'r', encoding='utf-8') as f:
                market_data = f.read()

            logger.info(f"Read market data ({len(market_data)} chars)")

            if len(market_data) < 10:
                logger.warning("Request data too short, skipping")
                self.write_error("Empty or invalid request data")
                return

            # Analyze with Ollama
            logger.info("Calling Ollama API...")
            start_time = time.time()
            decision = self.analyst.analyze_market(market_data)
            elapsed = time.time() - start_time
            logger.info(f"Ollama responded in {elapsed:.2f}s")

            # Write response
            self.write_response(decision)

            # Cleanup request file
            try:
                os.remove(filepath)
                logger.info("Cleaned up request file")
            except Exception as e:
                logger.warning(f"Failed to remove request file: {e}")

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            self.write_error(str(e))

        finally:
            self.processing = False

    def write_response(self, decision: dict):
        """Write AI decision to response file for MQL5 to read."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        response_text = f"""AI_RESPONSE_TIMESTAMP: {timestamp}
SIGNAL: {decision['signal']}
CONFIDENCE: {decision['confidence']}
REASONING: {decision['reasoning']}
SL: {decision['sl']}
TP: {decision['tp']}
RISK: {decision['risk']}
"""

        # Write response file
        with open(self.response_path, 'w', encoding='utf-8') as f:
            f.write(response_text)

        logger.info(f"Response written: {decision['signal']} ({decision['confidence']}% confidence)")

    def write_error(self, error_message: str):
        """Write error to error file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        error_text = f"""AI_ERROR_TIMESTAMP: {timestamp}
ERROR: {error_message}
"""

        with open(self.error_path, 'w', encoding='utf-8') as f:
            f.write(error_text)

        logger.error(f"Error written to file: {error_message}")


# === Main Entry Point ===

def main():
    """Start the AI bridge service."""
    logger.info("=" * 50)
    logger.info("MQL5 AI Bridge Service Starting (Ollama)")
    logger.info("=" * 50)
    logger.info(f"MT5 Files Path: {MT5_FILES_PATH}")
    logger.info(f"Ollama URL: {OLLAMA_BASE_URL}")
    logger.info(f"Ollama Model: {OLLAMA_MODEL}")

    # Verify MT5 path exists
    if not os.path.exists(MT5_FILES_PATH):
        logger.error(f"MT5 Files path does not exist: {MT5_FILES_PATH}")
        logger.info("Set MT5_PATH environment variable or update MT5_FILES_PATH")
        logger.info("Example: set MT5_PATH=C:\\Program Files\\MetaTrader 5")
        return

    # Initialize analyst
    analyst = OllamaTradingAnalyst(OLLAMA_BASE_URL, OLLAMA_MODEL)

    # Setup file watcher
    event_handler = MQL5FileHandler(analyst)
    observer = Observer()
    observer.schedule(event_handler, MT5_FILES_PATH, recursive=False)
    observer.start()

    logger.info(f"Watching: {MT5_FILES_PATH}")
    logger.info("Waiting for ai_request.txt files...")
    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping AI Bridge Service...")
        observer.stop()
        observer.join()
        logger.info("AI Bridge Service stopped")


if __name__ == "__main__":
    main()
