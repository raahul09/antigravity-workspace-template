"""Signal parsing module for Telegram messages.

Contains regex patterns for standard formatted signals, and a local LLM parser
using Ollama for unstructured or conversational signal text.
"""

import re
import json
import logging
import requests
from typing import Optional, Dict, Any

from config import config

logger = logging.getLogger(__name__)


def clean_symbol(symbol: str) -> str:
    """Normalize common trading symbols to match MT5 standards.

    Args:
        symbol: Raw parsed symbol string.

    Returns:
        Normalized symbol string (e.g., GOLD -> XAUUSD).
    """
    sym = symbol.strip().upper().replace("/", "")
    # Normalize gold naming
    if sym in ["GOLD", "XAU", "XAUUSD.PRO", "XAUUSDM"]:
        return "XAUUSD"
    # Normalize silver
    if sym in ["SILVER", "XAG", "XAGUSD"]:
        return "XAGUSD"
    return sym


def build_keyword_regex(keywords_str: str, is_tp: bool = False) -> str:
    """Build a regex pattern string from a comma-separated list of keywords.

    Args:
        keywords_str: Comma-separated keyword list.
        is_tp: If True, allows optional target numerical suffixes (e.g. TP1).

    Returns:
        Regex pattern string representing the alternation.
    """
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    # Sort by length descending to match longer keywords first
    keywords.sort(key=len, reverse=True)
    
    patterns = []
    for k in keywords:
        # Escape characters and replace literal spaces with \s* to support multiple spaces
        pat = re.escape(k).replace(r"\ ", r"\s*")
        if is_tp:
            pat += r"(?:\s*[1-9])?"
        patterns.append(pat)
        
    return "|".join(patterns)


def parse_signal_regex(text: str) -> Optional[Dict[str, Any]]:
    """Parse signal using deterministic regex patterns.

    Args:
        text: Raw Telegram message text.

    Returns:
        Dict containing action, symbol, entry, sl, tp, or None if invalid.
    """
    text_upper = text.upper()

    # Determine Action: BUY / SELL
    action = None
    if re.search(r"\b(BUY|LONG)\b", text_upper):
        action = "BUY"
    elif re.search(r"\b(SELL|SHORT)\b", text_upper):
        action = "SELL"

    if not action:
        return None

    # Find Symbol: e.g., XAUUSD, EURUSD, GBPUSD, GOLD
    # Matches words with letters and optional slashes (e.g. EUR/USD or XAUUSD)
    symbol_match = re.search(r"\b([A-Z]{3}/?[A-Z]{3}|GOLD|SILVER)\b", text_upper)
    symbol = clean_symbol(symbol_match.group(1)) if symbol_match else config.default_symbol

    # Dynamic regex builders
    sl_pat_str = build_keyword_regex(config.sl_keywords)
    tp_pat_str = build_keyword_regex(config.tp_keywords, is_tp=True)
    entry_pat_str = build_keyword_regex(config.entry_keywords)

    # Find Stop Loss (SL) - Required
    sl_match = re.search(
        rf"\b(?:{sl_pat_str})(?!\w)\s*(?:\)|\])?\s*(?::|-|=)?\s*(\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?)", 
        text_upper
    )
    if not sl_match:
        logger.warning("Failed to parse required Stop Loss (SL) via regex")
        return None
    sl = float(sl_match.group(1).replace(",", ""))

    # Find Take Profit (TP) - Optional
    tp_match = re.search(
        rf"\b(?:{tp_pat_str})(?!\w)\s*(?:\)|\])?\s*(?::|-|=)?\s*(\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?)", 
        text_upper
    )
    tp = float(tp_match.group(1).replace(",", "")) if tp_match else None

    # Find Entry Price - Optional (falls back to current market price if absent)
    entry_match = re.search(
        rf"(?:{entry_pat_str})(?!\w)\s*(?:\)|\])?\s*(?::|-|=)?\s*(\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?)", 
        text_upper
    )
    entry = None
    if entry_match:
        entry = float(entry_match.group(1).replace(",", ""))
    else:
        # Check if the entry price follows the action keyword directly (or with a symbol in between)
        # e.g., "sell 4571" or "buy gold 2420"
        action_entry_match = re.search(
            r"\b(?:BUY|SELL|LONG|SHORT)\s+(?:[A-Z]{3}/?[A-Z]{3}|GOLD|SILVER)?\s*(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)",
            text_upper
        )
        if action_entry_match:
            entry = float(action_entry_match.group(1).replace(",", ""))

    return {
        "action": action,
        "symbol": symbol,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "parser": "regex"
    }


def parse_signal_llm(text: str) -> Optional[Dict[str, Any]]:
    """Parse conversational/unstructured signals using a local Ollama LLM.

    Args:
        text: Raw Telegram message text.

    Returns:
        Dict containing action, symbol, entry, sl, tp, or None if invalid.
    """
    prompt = f"""You are a precise trading signal parsing engine.
Your task is to parse the following trading signal text and extract the details in JSON format.

=== SIGNAL TEXT ===
{text}

=== REQUIRED JSON OUTPUT ===
Respond ONLY with a valid JSON object matching this schema. Do not include markdown code blocks, explanation, or extra characters.

{{
  "action": "BUY" or "SELL" or null,
  "symbol": "e.g. XAUUSD" or null,
  "entry": float_or_null,
  "sl": float_or_null,
  "tp": float_or_null
}}

Rules:
1. "action" must be "BUY" or "SELL" (or null if action is not specified or unclear).
2. "symbol" must be normalized (e.g. GOLD, XAU -> "XAUUSD").
3. "sl" is the stop loss and is MANDATORY. If missing, return null for "sl".
4. "tp" is the take profit. If multiple TPs are provided, use the first TP target.
5. If the signal is not a valid trade alert, return all fields as null.
"""

    try:
        response = requests.post(
            f"{config.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": config.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0
                }
            },
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        raw_response = result.get("response", "").strip()
        
        # Clean any accidental markdown code fences
        clean_json_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response, flags=re.MULTILINE).strip()
        data = json.loads(clean_json_str)

        # Validate structured data
        action = data.get("action")
        sl = data.get("sl")
        if action not in ["BUY", "SELL"] or sl is None:
            logger.warning(f"LLM parser returned invalid/incomplete payload: {data}")
            return None

        return {
            "action": action,
            "symbol": clean_symbol(data.get("symbol") or config.default_symbol),
            "entry": float(data["entry"]) if data.get("entry") is not None else None,
            "sl": float(sl),
            "tp": float(data["tp"]) if data.get("tp") is not None else None,
            "parser": f"llm({config.ollama_model})"
        }
    except Exception as e:
        logger.error(f"Error parsing signal via local LLM: {e}")
        return None


def parse_signal(text: str) -> Optional[Dict[str, Any]]:
    """Parse Telegram message text into structured signal payload.

    Args:
        text: Raw Telegram message text.

    Returns:
        Structured signal details or None if invalid.
    """
    # 1. Try regex first (fast, deterministic, zero-resource)
    signal = parse_signal_regex(text)
    if signal:
        return signal

    # 2. Fall back to LLM if enabled and regex failed
    if config.use_llm_parser:
        logger.info("Regex parsing failed; falling back to local LLM parser...")
        return parse_signal_llm(text)

    return None
