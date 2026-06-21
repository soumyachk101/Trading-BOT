"""Real Exchange API client for production execution.

Handles HMAC SHA256 request signing for Binance Spot/Futures, time-offset
synchronization, and Alpaca REST API orders for Stock trading.
"""
from __future__ import annotations

import hmac
import hashlib
import time
import urllib.parse
import requests
import logging

logger = logging.getLogger("honest-bot.real_exchange")

BINANCE_SPOT_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"


# --- BINANCE SIGNATURES & TIME SYNC ---

def get_binance_time_offset(is_futures: bool = False) -> int:
    """Compute time offset (ms) between local server and Binance servers.

    Prevents 'timestamp outside recvWindow' rejection errors.
    """
    base = BINANCE_FUTURES_BASE if is_futures else BINANCE_SPOT_BASE
    endpoint = "/fapi/v1/time" if is_futures else "/api/v3/time"
    try:
        t_before = int(time.time() * 1000)
        res = requests.get(base + endpoint, timeout=5.0)
        t_after = int(time.time() * 1000)
        
        server_time = res.json()["serverTime"]
        # Estimate roundtrip latency mid-point
        rtt_mid = (t_after - t_before) // 2
        local_time_est = t_before + rtt_mid
        offset = server_time - local_time_est
        return offset
    except Exception as e:
        logger.warning(f"Failed to fetch time offset from Binance: {e}. Using 0.")
        return 0


def binance_signed_request(
    method: str,
    endpoint: str,
    params: dict,
    api_key: str,
    api_secret: str,
    is_futures: bool = False,
) -> dict:
    """Send a signed HMAC SHA256 request to Binance REST API."""
    base = BINANCE_FUTURES_BASE if is_futures else BINANCE_SPOT_BASE
    url = base + endpoint
    
    # 1. Inject timestamp synced with server offset
    offset = get_binance_time_offset(is_futures)
    params["timestamp"] = int(time.time() * 1000) + offset
    params["recvWindow"] = 6000  # 6-second window for latency safety
    
    # 2. Build and sign query string
    query_str = urllib.parse.urlencode(params)
    signature = hmac.new(
        api_secret.encode("utf-8"),
        query_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    # 3. Compile final request
    full_url = f"{url}?{query_str}&signature={signature}"
    headers = {
        "X-MBX-APIKEY": api_key,
        "User-Agent": "honest-production-bot/1.0"
    }
    
    # 4. Perform HTTP request
    if method.upper() == "POST":
        resp = requests.post(full_url, headers=headers, timeout=10.0)
    elif method.upper() == "GET":
        resp = requests.get(full_url, headers=headers, timeout=10.0)
    elif method.upper() == "DELETE":
        resp = requests.delete(full_url, headers=headers, timeout=10.0)
    else:
        raise ValueError(f"Unsupported request method: {method}")
        
    if resp.status_code != 200:
        raise ValueError(f"Binance API returned error {resp.status_code}: {resp.text}")
        
    return resp.json()


# --- REAL TRANSACTION PLACEMENTS ---

def execute_real_binance_spot(
    symbol: str,
    side: str,
    qty: float,
    api_key: str,
    api_secret: str,
) -> dict:
    """Place a real Spot Market Order on Binance.

    Matches the output structure of execute_spot_market_order.
    """
    params = {
        "symbol": symbol.upper(),
        "side": side.upper(),
        "type": "MARKET",
        "quantity": f"{qty:.6f}",  # adjust precision as needed per asset specs
    }
    # For spot buying, we might want to specify quoteOrderQty to buy exact cash values
    res = binance_signed_request("POST", "/api/v3/order", params, api_key, api_secret, is_futures=False)
    
    # Extract execution price. Binance market orders return fill rates inside 'fills' list
    fills = res.get("fills", [])
    if fills:
        # Weighted average fill price
        total_qty = sum(float(f["qty"]) for f in fills)
        total_cost = sum(float(f["price"]) * float(f["qty"]) for f in fills)
        fill_price = total_cost / total_qty if total_qty > 0 else 0.0
        total_fee = sum(float(f["commission"]) for f in fills if f.get("commissionAsset") == "BNB" or f.get("commissionAsset") == symbol) # simplify
    else:
        fill_price = float(res.get("price", 0.0))
        total_fee = 0.0

    return {
        "price": fill_price,
        "qty": float(res.get("executedQty", qty)),
        "fee_usd": total_fee * fill_price, # rough approximation
        "raw_response": res,
    }


def execute_real_binance_perp(
    symbol: str,
    side: str,
    qty: float,
    leverage: float,
    api_key: str,
    api_secret: str,
) -> dict:
    """Place a real Perpetual Futures Market Order on Binance USDⓈ-M.

    First adjusts the leverage, then submits the market order.
    """
    symbol = symbol.upper()
    
    # 1. Adjust leverage first (ignored if already set, but safe to send)
    try:
        binance_signed_request(
            "POST",
            "/fapi/v1/leverage",
            {"symbol": symbol, "leverage": int(leverage)},
            api_key,
            api_secret,
            is_futures=True
        )
    except Exception as e:
        logger.info(f"Could not change leverage to {leverage} (might be already set): {e}")

    # 2. Place market order
    params = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "MARKET",
        "quantity": f"{qty:.3f}",
    }
    res = binance_signed_request("POST", "/fapi/v1/order", params, api_key, api_secret, is_futures=True)
    
    fill_price = float(res.get("avgPrice", 0.0))
    if fill_price == 0.0:
        # Fallback to current ticker price if avgPrice is not returned
        ticker_res = requests.get(f"{BINANCE_FUTURES_BASE}/fapi/v1/ticker/price?symbol={symbol}")
        fill_price = float(ticker_res.json()["price"])

    return {
        "price": fill_price,
        "qty": float(res.get("executedQty", qty)),
        "raw_response": res,
    }


def execute_real_alpaca_stock(
    symbol: str,
    side: str,
    qty: float,
    api_key: str,
    api_secret: str,
    is_paper: bool = True,
) -> dict:
    """Place a real Stock Market Order on Alpaca."""
    base_url = "https://paper-api.alpaca.markets" if is_paper else "https://api.alpaca.markets"
    url = f"{base_url}/v2/orders"
    
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
        "Content-Type": "application/json",
        "User-Agent": "honest-production-bot/1.0"
    }
    
    payload = {
        "symbol": symbol.upper(),
        "qty": float(qty),
        "side": side.lower(),
        "type": "market",
        "time_in_force": "day"
    }
    
    resp = requests.post(url, json=payload, headers=headers, timeout=10.0)
    if resp.status_code not in (200, 201):
        raise ValueError(f"Alpaca API returned error {resp.status_code}: {resp.text}")
        
    res = resp.json()
    
    # Alpaca fills are processed asynchronously. For market order safety in live run:
    # We query the order fill details or fall back to the estimated market price
    order_id = res["id"]
    time.sleep(1.0)  # brief pause to allow fill processing
    
    fill_price = 0.0
    try:
        status_resp = requests.get(f"{base_url}/v2/orders/{order_id}", headers=headers, timeout=5.0)
        status_res = status_resp.json()
        fill_price = float(status_res.get("filled_avg_price", 0.0) or 0.0)
    except Exception:
        pass
        
    return {
        "price": fill_price,
        "qty": float(res.get("qty", qty)),
        "order_id": order_id,
        "raw_response": res,
    }


# --- BALANCE QUERY UTILITIES ---

def fetch_real_balances(
    binance_key: str | None,
    binance_secret: str | None,
    alpaca_key: str | None,
    alpaca_secret: str | None,
    alpaca_is_paper: bool = True
) -> dict[str, float]:
    """Retrieve real-time cash balances from active exchanges."""
    balances = {"cash": 0.0}
    
    # 1. Fetch Binance USD-M futures wallet balance (representing crypto cash pool)
    if binance_key and binance_secret:
        try:
            res = binance_signed_request(
                "GET", "/fapi/v2/account", {}, binance_key, binance_secret, is_futures=True
            )
            # Find free USDT or account balance
            balances["cash"] += float(res.get("availableBalance", 0.0))
        except Exception as e:
            logger.warning(f"Could not fetch Binance balances: {e}")
            
    # 2. Fetch Alpaca cash balance (representing stock cash pool)
    if alpaca_key and alpaca_secret:
        try:
            base_url = "https://paper-api.alpaca.markets" if alpaca_is_paper else "https://api.alpaca.markets"
            headers = {
                "APCA-API-KEY-ID": alpaca_key,
                "APCA-API-SECRET-KEY": alpaca_secret
            }
            res = requests.get(f"{base_url}/v2/account", headers=headers, timeout=5.0).json()
            balances["cash"] += float(res.get("cash", 0.0))
        except Exception as e:
            logger.warning(f"Could not fetch Alpaca balances: {e}")
            
    return balances
