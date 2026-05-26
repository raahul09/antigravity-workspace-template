"""Licensing Manager.

Handles decoding, verifying, and saving license keys. Uses cryptographic 
HMAC-SHA256 signature validation completely offline.
"""

import os
import hmac
import hashlib
import base64
import datetime
import logging
import subprocess
import uuid
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

SECRET_SALT = "groot_trade_secret_license_salt_9988"
LICENSE_FILE = ".license"


def get_machine_id() -> str:
    """Retrieve a unique, stable hardware fingerprint for Windows."""
    try:
        # Query Windows Management Instrumentation for motherboard UUID
        cmd = "wmic csproduct get uuid"
        output = subprocess.check_output(cmd, shell=True).decode().split()
        if len(output) >= 2:
            raw_id = output[1].strip()
            if raw_id and "uuid" not in raw_id.lower() and len(raw_id) > 5:
                return hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:16].upper()
    except Exception as e:
        logger.warning(f"Could not retrieve WMI motherboard UUID: {e}")
    
    # Fallback to hashed MAC address
    mac = str(uuid.getnode())
    return hashlib.sha256(mac.encode('utf-8')).hexdigest()[:16].upper()


def verify_license_key(key: str) -> Tuple[bool, str, str]:
    """Decode and cryptographically verify a hardware-bound license key.

    Args:
        key: Base64 encoded license key string.

    Returns:
        Tuple[bool, reason/email, expiry_date]:
            - bool: True if license is valid, False otherwise.
            - email: Holder email if valid, or reason string if invalid.
            - expiry: Expiration date string (YYYY-MM-DD) if valid, otherwise empty.
    """
    if not key:
        return False, "License key is empty", ""

    try:
        # 1. Base64 decode the key
        decoded_bytes = base64.b64decode(key.encode('utf-8'), validate=True)
        decoded_str = decoded_bytes.decode('utf-8')
        
        # 2. Split into segments: email | expiry | machine_id | signature
        parts = decoded_str.split("|")
        if len(parts) != 4:
            return False, "Invalid license key format (must contain 4 segments)", ""
            
        email, expiry_str, machine_id, signature = parts
        email = email.strip()
        expiry_str = expiry_str.strip()
        machine_id = machine_id.strip()
        signature = signature.strip()
        
        if not email or not expiry_str or not machine_id or not signature:
            return False, "Malformed license segments", ""

        # 3. Verify signature
        message = f"{email}|{expiry_str}|{machine_id}".encode('utf-8')
        expected_sig = hmac.new(
            SECRET_SALT.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return False, "License key signature mismatch (tempered or invalid)", ""

        # 4. Verify machine ID matches current local computer ID
        current_id = get_machine_id()
        if machine_id != current_id:
            return False, f"License is locked to another computer (ID: {machine_id})", ""

        # 5. Check expiration date
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        
        if expiry_date < today:
            return False, f"License has expired on {expiry_str}", ""
            
        return True, email, expiry_str

    except base64.binascii.Error:
        return False, "License key is not a valid base64 string", ""
    except ValueError as e:
        return False, f"Invalid date format in key: {e}", ""
    except Exception as e:
        return False, f"Unexpected error during verification: {str(e)}", ""


def save_license_key(key: str) -> bool:
    """Save the license key to the local license storage file.

    Args:
        key: Base64 encoded license key string.

    Returns:
        bool: True if key is valid and saved, False otherwise.
    """
    is_valid, email_or_reason, expiry = verify_license_key(key)
    if not is_valid:
        logger.error(f"Cannot save invalid license key: {email_or_reason}")
        return False
        
    try:
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            f.write(key.strip())
        logger.info(f"Saved valid license key for {email_or_reason} expiring on {expiry}")
        return True
    except Exception as e:
        logger.error(f"Failed to write license file: {e}")
        return False


def load_license_key() -> str:
    """Load the license key from local license storage.

    Returns:
        str: Loaded license key, or empty string.
    """
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.error(f"Failed to read license file: {e}")
    return ""


def get_license_status() -> Dict[str, Any]:
    """Retrieve detailed status of the current license.

    Returns:
        Dict: License status properties.
    """
    key = load_license_key()
    if not key:
        return {
            "active": False,
            "licensee": "None",
            "expiry": "None",
            "days_remaining": 0,
            "message": "Activation required. No license key found."
        }
        
    is_valid, email_or_reason, expiry_str = verify_license_key(key)
    if not is_valid:
        return {
            "active": False,
            "licensee": "None",
            "expiry": "None",
            "days_remaining": 0,
            "message": f"License is inactive: {email_or_reason}"
        }
        
    expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d").date()
    today = datetime.date.today()
    days_rem = (expiry_date - today).days
    
    return {
        "active": True,
        "licensee": email_or_reason,
        "expiry": expiry_str,
        "days_remaining": max(0, days_rem),
        "message": f"Active license for {email_or_reason} ({days_rem} days remaining)"
    }
