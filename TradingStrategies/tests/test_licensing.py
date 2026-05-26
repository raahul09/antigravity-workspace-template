"""Tests for the Licensing System.

Verifies that license keys are correctly generated, validated, stored, and 
rejected if expired or tampered with.
"""

import os
import sys
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch

# Provide access to the telegram_to_mt5_bot modules
current_dir = Path(__file__).resolve().parent
bot_dir = current_dir.parent / 'telegram_to_mt5_bot'
if str(bot_dir) not in sys.path:
    sys.path.insert(0, str(bot_dir))

sys.path.insert(0, str(current_dir.parent))

import license_manager
from generate_license import generate_key

TEST_LICENSE_FILE = ".test_license"


@pytest.fixture(autouse=True)
def setup_test_license():
    """Redirect license manager storage file to a test location."""
    original_file = license_manager.LICENSE_FILE
    license_manager.LICENSE_FILE = TEST_LICENSE_FILE
    
    yield
    
    # Clean up test file if created
    license_manager.LICENSE_FILE = original_file
    if os.path.exists(TEST_LICENSE_FILE):
        try:
            os.remove(TEST_LICENSE_FILE)
        except Exception:
            pass


def test_license_generation_and_verification():
    """Verify that a valid license key generates and validates successfully."""
    email = "client_A@email.com"
    days = 10
    
    # 1. Generate key
    key = generate_key(email, days)
    assert key != ""
    
    # 2. Verify key
    is_valid, licensee, expiry_str = license_manager.verify_license_key(key)
    assert is_valid is True
    assert licensee == email
    
    expected_expiry = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    assert expiry_str == expected_expiry


def test_expired_license_rejection():
    """Verify that an expired license key is correctly rejected."""
    email = "expired_user@email.com"
    # Generate an expired key manually by overriding signature and expiry date
    import hmac
    import hashlib
    import base64
    
    past_expiry = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    message = f"{email}|{past_expiry}".encode('utf-8')
    sig = hmac.new(
        license_manager.SECRET_SALT.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    
    raw_key = f"{email}|{past_expiry}|{sig}"
    key = base64.b64encode(raw_key.encode('utf-8')).decode('utf-8')
    
    # Verify key
    is_valid, reason, _ = license_manager.verify_license_key(key)
    assert is_valid is False
    assert "expired" in reason.lower()


def test_tampered_license_rejection():
    """Verify that any tampering or signature mismatch is detected."""
    email = "hacker@email.com"
    key = generate_key(email, 30)
    
    # Decode and tamper with the date
    import base64
    decoded = base64.b64decode(key.encode()).decode()
    parts = decoded.split("|")
    
    # Change date but keep old signature
    parts[1] = "2099-12-31" 
    tampered_raw = "|".join(parts)
    tampered_key = base64.b64encode(tampered_raw.encode()).decode()
    
    # Verify tampered key
    is_valid, reason, _ = license_manager.verify_license_key(tampered_key)
    assert is_valid is False
    assert "signature mismatch" in reason.lower()


def test_license_status_inactive():
    """Verify license status reports when no key is loaded or key is invalid."""
    # Ensure no file exists
    if os.path.exists(TEST_LICENSE_FILE):
        os.remove(TEST_LICENSE_FILE)
        
    status = license_manager.get_license_status()
    assert status["active"] is False
    assert status["licensee"] == "None"
    
    # Save dummy key
    with open(TEST_LICENSE_FILE, "w") as f:
        f.write("invalid_base64_string_here")
        
    status = license_manager.get_license_status()
    assert status["active"] is False
    assert "inactive" in status["message"].lower()


def test_license_save_and_load():
    """Verify saving and loading of license keys."""
    key = generate_key("save_load_test@email.com", 15)
    
    success = license_manager.save_license_key(key)
    assert success is True
    
    loaded = license_manager.load_license_key()
    assert loaded == key
    
    status = license_manager.get_license_status()
    assert status["active"] is True
    assert status["licensee"] == "save_load_test@email.com"
    assert status["days_remaining"] == 15
