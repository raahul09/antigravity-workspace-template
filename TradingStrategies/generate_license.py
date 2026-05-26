"""License Key Generator Tool.

Run this script to generate cryptographically signed base64 license keys
for your bot buyers.

Usage:
    python generate_license.py --email customer@example.com --days 30
"""

import argparse
import datetime
import hmac
import hashlib
import base64
import sys

SECRET_SALT = "groot_trade_secret_license_salt_9988"

def generate_key(email: str, days: int, machine_id: str) -> str:
    """Generate a signed hardware-bound offline license key.

    Args:
        email: Buyer's email or username.
        days: Days until the key expires.
        machine_id: Hardware fingerprint string of target machine.

    Returns:
        str: Base64-encoded license key.
    """
    email_clean = email.strip()
    mid_clean = machine_id.strip().upper()
    
    # Calculate expiry date
    expiry_date = datetime.date.today() + datetime.timedelta(days=days)
    expiry_str = expiry_date.strftime("%Y-%m-%d")
    
    # Compute signature
    message = f"{email_clean}|{expiry_str}|{mid_clean}".encode('utf-8')
    sig = hmac.new(
        SECRET_SALT.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    
    # Combine components and encode to Base64
    raw_key = f"{email_clean}|{expiry_str}|{mid_clean}|{sig}"
    encoded_key = base64.b64encode(raw_key.encode('utf-8')).decode('utf-8')
    return encoded_key

def main():
    parser = argparse.ArgumentParser(description="GrootTrade Hardware-Bound License Key Generator")
    parser.add_argument("--email", required=True, help="Licensee email address or name")
    parser.add_argument("--machine-id", required=True, help="Licensee machine hardware ID (e.g. from Tool Activation tab)")
    parser.add_argument("--days", type=int, default=30, help="Days of validity (default: 30)")
    args = parser.parse_args()
    
    if args.days <= 0:
        print("Error: Validity days must be positive.", file=sys.stderr)
        sys.exit(1)
        
    key = generate_key(args.email, args.days, args.machine_id)
    
    expiry_date = datetime.date.today() + datetime.timedelta(days=args.days)
    expiry_str = expiry_date.strftime("%Y-%m-%d")
    
    print("=" * 70)
    print("GROOTTRADE SECURE LICENSE KEY GENERATOR")
    print("=" * 70)
    print(f"License Holder: {args.email}")
    print(f"Target Machine: {args.machine_id.upper()}")
    print(f"Expiry Date:    {expiry_str} ({args.days} days from today)")
    print("-" * 70)
    print("COPY & SEND THIS KEY TO THE USER:")
    print(key)
    print("=" * 70)

if __name__ == "__main__":
    main()
