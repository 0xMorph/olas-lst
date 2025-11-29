#!/usr/bin/env python3
import sys
import math
import argparse
from datetime import datetime, timezone

from web3 import Web3

# ==== DEFAULT CONFIG ====

DEFAULT_RPC_URL = ""
STOLAS_ADDRESS = "0xab4c5bb0797ca25e93a4af2e8fecd7fcac0f2c9b"

# APR window — 7 days (same logic as used on the frontend)
LOOKBACK_DAYS = 7
LOOKBACK_SECONDS = LOOKBACK_DAYS * 24 * 60 * 60

# Minimal ABI we need from stOLAS
STOLAS_ABI = [
    {
        "inputs": [],
        "name": "totalAssets",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


# ==== HELPERS ====


def to_datetime(ts: int) -> datetime:
    """Convert unix timestamp to timezone-aware UTC datetime."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def find_block_by_timestamp(w3: Web3, target_ts: int) -> int:
    """
    Binary search for the first block whose timestamp >= target_ts.

    Returns:
        Block number such that block.timestamp >= target_ts and
        is as close as possible to target_ts.
    """
    latest = w3.eth.block_number
    low = 1  # skip genesis
    high = latest
    best = latest

    while low <= high:
        mid = (low + high) // 2
        block = w3.eth.get_block(mid)
        ts = block["timestamp"]

        if ts >= target_ts:
            best = mid
            high = mid - 1
        else:
            low = mid + 1

    return best


def get_pps_at_block(contract, block_number: int) -> float:
    """
    Compute PPS (price per share) at a given block.

    PPS = totalAssets / totalSupply

    Returns:
        PPS as a float (OLAS per 1 stOLAS).

    Note:
        For APR we only care about the ratio PPS_now / PPS_past,
        so using float here is fine.
    """
    total_assets = contract.functions.totalAssets().call(block_identifier=block_number)
    total_supply = contract.functions.totalSupply().call(block_identifier=block_number)

    if total_supply == 0:
        raise RuntimeError(f"totalSupply == 0 at block {block_number}, PPS undefined")

    pps = total_assets / total_supply
    return pps


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute stOLAS APR based on PPS change over last 7 days."
    )
    parser.add_argument(
        "--rpc",
        "-r",
        dest="rpc_url",
        type=str,
        default=DEFAULT_RPC_URL,
        help=f"RPC URL (default: {DEFAULT_RPC_URL})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    rpc_url = args.rpc_url

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        print(f"Error: cannot connect to RPC: {rpc_url}", file=sys.stderr)
        sys.exit(1)

    print(f"Connected to chain via RPC: {rpc_url}")
    print(f"Latest block number: {w3.eth.block_number}")

    stolas = w3.eth.contract(
        address=Web3.to_checksum_address(STOLAS_ADDRESS),
        abi=STOLAS_ABI,
    )

    # Current block and timestamp
    latest_block = w3.eth.get_block("latest")
    latest_number = latest_block["number"]
    latest_ts = latest_block["timestamp"]
    latest_dt = to_datetime(latest_ts)

    # Target timestamp "LOOKBACK_DAYS days ago"
    target_ts = latest_ts - LOOKBACK_SECONDS
    target_dt = to_datetime(target_ts)

    print(f"Latest block: {latest_number} at {latest_dt.isoformat()}")
    print(
        f"Target timestamp (~{LOOKBACK_DAYS} days ago): "
        f"{target_dt.isoformat()} (unix {target_ts})"
    )

    # Find closest block to target_ts
    past_block_num = find_block_by_timestamp(w3, target_ts)
    past_block = w3.eth.get_block(past_block_num)
    past_ts_actual = past_block["timestamp"]
    past_dt_actual = to_datetime(past_ts_actual)

    print(
        f"Past block (>= target_ts): {past_block_num} "
        f"at {past_dt_actual.isoformat()}"
    )

    # PPS now and PPS in the past
    pps_now = get_pps_at_block(stolas, latest_number)
    pps_past = get_pps_at_block(stolas, past_block_num)

    if pps_past == 0:
        raise RuntimeError("pps_past == 0, APR cannot be computed")

    change_ratio = pps_now / pps_past  # >1 if PPS increased
    change_pct = (change_ratio - 1.0) * 100

    # APR version 1: strictly using 7-day window as on the frontend
    yearly_factor_7d = 365.0 / LOOKBACK_DAYS
    apr_7d_window = (change_ratio - 1.0) * yearly_factor_7d * 100.0

    # APR version 2: using the exact time interval between blocks
    dt_seconds = latest_ts - past_ts_actual
    if dt_seconds <= 0:
        raise RuntimeError("Non-positive time interval between blocks")

    days_interval = dt_seconds / (24 * 60 * 60)
    yearly_factor_real = 365.0 / days_interval
    apr_real = (change_ratio - 1.0) * yearly_factor_real * 100.0

    print("\n===== PPS DATA =====")
    print(f"PPS now : {pps_now:.18f} OLAS per stOLAS")
    print(f"PPS past: {pps_past:.18f} OLAS per stOLAS")
    print(f"Relative change over window: {change_pct:.6f}%")

    print("\n===== APR (front-end style, 7-day window) =====")
    print(f"APR_7d_window ≈ {apr_7d_window:.6f}%")

    print("\n===== APR (using exact time delta between blocks) =====")
    print(f"Window length (days): {days_interval:.6f}")
    print(f"APR_real ≈ {apr_real:.6f}%")

    print("\nNote:")
    print("- APR_7d_window corresponds to the formula used on the front-end (fixed 7-day window).")
    print("- APR_real is a sanity-check using the exact time delta between past and latest blocks.")


if __name__ == "__main__":
    main()

