"""Browser Dashboard for the Paper Trading Bot.

Serves a premium glassmorphic web dashboard showing live portfolio status,
open positions, recent trade history, and an auditable ledger.
Supports interactive controls for pausing/resuming, updating configs, and placing manual orders.
"""
from __future__ import annotations

import http.server
import json
import logging
import threading
import urllib.request
import urllib.parse
import datetime as dt
import hashlib
from typing import Callable, Dict
from tradingbot import config
from tradingbot import prices
from tradingbot.engine import HonestEngine

logger = logging.getLogger("honest-bot.dashboard")

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AlgoForge Terminal | Live Dashboard</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #080b10;
            --card-bg: rgba(13, 20, 30, 0.45);
            --border-color: rgba(88, 166, 255, 0.12);
            --border-hover: rgba(88, 166, 255, 0.3);
            --text-main: #f0f6fc;
            --text-muted: #8b949e;
            --accent-green: #3fb950;
            --accent-green-glow: rgba(63, 185, 80, 0.2);
            --accent-red: #f85149;
            --accent-red-glow: rgba(248, 81, 73, 0.2);
            --accent-blue: #58a6ff;
            --accent-glow: rgba(88, 166, 255, 0.15);
            --font-main: 'Outfit', sans-serif;
            --font-mono: 'Space Grotesk', sans-serif;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: var(--font-main);
            background-color: var(--bg-color);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: radial-gradient(circle at 5% 5%, rgba(88, 166, 255, 0.08) 0%, transparent 40%),
                              radial-gradient(circle at 95% 95%, rgba(63, 185, 80, 0.08) 0%, transparent 45%);
        }

        /* Top Header */
        header {
            padding: 16px 5%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            background: rgba(8, 11, 16, 0.85);
            backdrop-filter: blur(16px);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-logo {
            font-family: var(--font-mono);
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(95deg, var(--accent-blue), #bb86fc, var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: -0.5px;
        }

        .header-status {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .status-badge {
            background-color: rgba(88, 166, 255, 0.08);
            color: var(--accent-blue);
            padding: 6px 14px;
            border-radius: 30px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(63, 185, 80, 0.5); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(63, 185, 80, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(63, 185, 80, 0); }
        }

        /* Tabs Selection Panel */
        .tabs-container {
            display: flex;
            gap: 12px;
            background: rgba(22, 27, 34, 0.4);
            border: 1px solid var(--border-color);
            padding: 6px;
            border-radius: 12px;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 8px 18px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.25s ease;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.03);
        }

        .tab-btn.active {
            color: #ffffff;
            background: rgba(88, 166, 255, 0.15);
            border: 1px solid rgba(88, 166, 255, 0.25);
            box-shadow: 0 0 12px rgba(88, 166, 255, 0.1);
        }

        /* Layout Grid */
        main {
            flex: 1;
            padding: 32px 5%;
            max-width: 1600px;
            width: 100%;
            margin: 0 auto;
        }

        .tab-content {
            display: none;
            animation: fadeIn 0.35s ease;
        }

        .tab-content.active {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
        }

        .tab-content.single-col.active {
            grid-template-columns: 1fr;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Glassmorphic Cards */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(20px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }

        .card:hover {
            border-color: var(--border-hover);
            box-shadow: 0 8px 32px 0 rgba(88, 166, 255, 0.04);
        }

        .section-title {
            font-family: var(--font-mono);
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 4px solid var(--accent-blue);
            padding-left: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--accent-blue);
        }

        /* Metrics grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
            grid-column: span 2;
        }

        .metric-card {
            background: linear-gradient(135deg, rgba(13, 20, 30, 0.8) 0%, rgba(8, 11, 16, 0.8) 100%);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            position: relative;
            overflow: hidden;
        }

        .metric-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 100%; height: 3px;
            background: linear-gradient(90deg, transparent, var(--accent-blue), transparent);
        }

        .metric-label {
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .metric-value {
            font-family: var(--font-mono);
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }

        .metric-sub {
            font-size: 12px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .up { color: var(--accent-green); }
        .down { color: var(--accent-red); }

        /* Tables */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }

        th, td {
            padding: 14px 16px;
            border-bottom: 1px solid rgba(88, 166, 255, 0.08);
        }

        th {
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.8px;
            background: rgba(88, 166, 255, 0.02);
        }

        tr:hover td {
            background: rgba(88, 166, 255, 0.01);
        }

        tr:last-child td {
            border-bottom: none;
        }

        /* Form Controls */
        .form-group {
            margin-bottom: 20px;
        }

        .form-group label {
            display: block;
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 8px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .form-control, select {
            width: 100%;
            background: rgba(8, 11, 16, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 14px;
            color: var(--text-main);
            font-family: var(--font-main);
            font-size: 14px;
            transition: all 0.3s ease;
        }

        .form-control:focus, select:focus {
            border-color: var(--accent-blue);
            outline: none;
            box-shadow: 0 0 10px rgba(88, 166, 255, 0.15);
        }

        /* Order Form specific styles */
        .side-selector {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
        }

        .side-btn {
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
            font-weight: 700;
            cursor: pointer;
            text-align: center;
            background: rgba(8, 11, 16, 0.4);
            color: var(--text-muted);
            transition: all 0.25s ease;
        }

        .side-btn.active.buy {
            background: var(--accent-green-glow);
            color: var(--accent-green);
            border-color: var(--accent-green);
            box-shadow: 0 0 12px rgba(63, 185, 80, 0.15);
        }

        .side-btn.active.sell {
            background: var(--accent-red-glow);
            color: var(--accent-red);
            border-color: var(--accent-red);
            box-shadow: 0 0 12px rgba(248, 81, 73, 0.15);
        }

        .btn-submit {
            width: 100%;
            padding: 14px;
            border-radius: 8px;
            border: none;
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }

        .btn-submit.buy {
            background: var(--accent-green);
            color: #ffffff;
        }

        .btn-submit.sell {
            background: var(--accent-red);
            color: #ffffff;
        }

        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }

        /* Toggle Switches */
        .toggle-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px;
            border-radius: 10px;
            background: rgba(255,255,255,0.01);
            border: 1px solid rgba(88, 166, 255, 0.05);
        }

        .switch {
            position: relative;
            display: inline-block;
            width: 48px;
            height: 24px;
        }

        .switch input { opacity: 0; width: 0; height: 0; }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: rgba(255,255,255,0.1);
            transition: .4s;
            border-radius: 24px;
            border: 1px solid rgba(255,255,255,0.1);
        }

        .slider:before {
            position: absolute;
            content: "";
            height: 16px; width: 16px;
            left: 3px; bottom: 3px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }

        input:checked + .slider {
            background-color: var(--accent-blue);
        }

        input:checked + .slider:before {
            transform: translateX(24px);
        }

        /* Badges */
        .badge-type {
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        .badge-spot { background-color: rgba(88, 166, 255, 0.12); color: var(--accent-blue); }
        .badge-stock { background-color: rgba(255, 191, 0, 0.12); color: #ffbf00; }
        .badge-perp { background-color: rgba(187, 134, 252, 0.12); color: #bb86fc; }

        .badge-action {
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
            font-size: 11px;
        }
        .badge-buy { background-color: rgba(63, 185, 80, 0.15); color: var(--accent-green); }
        .badge-sell { background-color: rgba(248, 81, 73, 0.15); color: var(--accent-red); }

        /* Search input & CSV Button */
        .ledger-toolbar {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 20px;
        }

        .btn-action {
            background: rgba(88, 166, 255, 0.1);
            border: 1px solid var(--border-color);
            color: var(--accent-blue);
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 600;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.25s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-action:hover {
            background: rgba(88, 166, 255, 0.18);
            border-color: var(--accent-blue);
        }

        .chart-container {
            height: 320px;
            position: relative;
        }

        .no-data {
            color: var(--text-muted);
            text-align: center;
            padding: 40px 0;
            font-style: italic;
        }

        /* Sliders */
        .range-value {
            font-family: var(--font-mono);
            font-weight: 700;
            color: var(--accent-blue);
        }

        /* News Sentiment Badge Styles */
        .badge-sentiment {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            font-family: var(--font-mono);
        }
        .sentiment-positive {
            background: rgba(63, 185, 80, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(63, 185, 80, 0.3);
            box-shadow: 0 0 8px rgba(63, 185, 80, 0.1);
        }
        .sentiment-negative {
            background: rgba(248, 81, 73, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(248, 81, 73, 0.3);
            box-shadow: 0 0 8px rgba(248, 81, 73, 0.1);
        }
        .sentiment-neutral {
            background: rgba(139, 148, 158, 0.15);
            color: var(--text-muted);
            border: 1px solid rgba(139, 148, 158, 0.3);
        }
        .news-item {
            padding: 10px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 8px;
            transition: all 0.2s ease;
            margin-bottom: 8px;
        }
        .news-item:hover {
            background: rgba(255, 255, 255, 0.05);
            border-color: var(--accent-blue);
        }
        .news-title {
            font-size: 13px;
            font-weight: 500;
            color: var(--text-main);
            margin-bottom: 6px;
            line-height: 1.4;
        }
        .news-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>

    <header>
        <div class="header-logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            ALGOFORGE TERMINAL
        </div>

        <div class="tabs-container">
            <button class="tab-btn active" onclick="switchTab('dashboard-tab')">Dashboard</button>
            <button class="tab-btn" onclick="switchTab('trader-tab')">Manual Trader</button>
            <button class="tab-btn" onclick="switchTab('settings-tab')">Risk Settings</button>
            <button class="tab-btn" onclick="switchTab('ledger-tab')">Audit Ledger</button>
        </div>

        <div class="header-status">
            <div class="status-badge">
                <span class="status-dot" id="status-dot-element"></span>
                <span id="bot-mode-badge">Active Engine</span>
            </div>
        </div>
    </header>

    <main>
        <!-- Metrics Panel (Shown globally above tabs) -->
        <div class="metrics-grid">
            <div class="metric-card">
                <span class="metric-label">Portfolio Value</span>
                <span class="metric-value" id="val-portfolio">$10,000.00</span>
                <span class="metric-sub up" id="val-change">+0.00%</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">Cash Reserve</span>
                <span class="metric-value" id="val-cash">$10,000.00</span>
                <span class="metric-sub" style="color:var(--text-muted)">USD / USDT Available</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">Execution Count</span>
                <span class="metric-value" id="val-trades">0</span>
                <span class="metric-sub" style="color:var(--accent-blue)">Standard VIP0 rate</span>
            </div>
            <div class="metric-card">
                <span class="metric-label">System Control Status</span>
                <span class="metric-value" id="val-status">RUNNING</span>
                <span class="metric-sub" style="color:var(--text-muted)" id="val-safety-resets">Resets: 0</span>
            </div>
        </div>

        <!-- 1. DASHBOARD TAB -->
        <div id="dashboard-tab" class="tab-content active">
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <div class="card">
                    <h2 class="section-title">Equity performance</h2>
                    <div class="chart-container">
                        <canvas id="equityChart"></canvas>
                    </div>
                </div>

                <div class="card">
                    <h2 class="section-title">Active holdings & margins</h2>
                    <div style="overflow-x: auto;">
                        <table id="positions-table">
                            <thead>
                                <tr>
                                    <th>Asset / Symbol</th>
                                    <th>Asset Type</th>
                                    <th>Size / Qty</th>
                                    <th>Average Entry</th>
                                    <th>Allocated value</th>
                                </tr>
                            </thead>
                            <tbody id="positions-body">
                                <tr>
                                    <td colspan="5" class="no-data">No positions held currently.</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Dashboard Sidebar -->
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <div class="card">
                    <h2 class="section-title">Live tickers</h2>
                    <div style="display: flex; flex-direction: column; gap: 14px;">
                        <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); border-radius: 8px;">
                            <span style="font-weight:600; color:var(--text-muted);">BTCUSDT Spot</span>
                            <span id="obs-btc-spot" style="color:var(--accent-blue); font-family:var(--font-mono); font-weight:700;">Loading...</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); border-radius: 8px;">
                            <span style="font-weight:600; color:var(--text-muted);">BTCUSDT Perpetual</span>
                            <span id="obs-btc-perp" style="color:var(--accent-blue); font-family:var(--font-mono); font-weight:700;">Loading...</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; padding: 12px; background: rgba(255,255,255,0.01); border: 1px solid rgba(255,255,255,0.03); border-radius: 8px;">
                            <span style="font-weight:600; color:var(--text-muted);">AAPL Stock</span>
                            <span id="obs-aapl" style="color:var(--accent-blue); font-family:var(--font-mono); font-weight:700;">Loading...</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h2 class="section-title">Mode configuration</h2>
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        <div style="display: flex; justify-content: space-between; font-size: 14px;">
                            <span style="color:var(--text-muted)">Live Trading Mode:</span>
                            <span id="live-mode-status" style="font-weight:700; color:var(--accent-red)">DISABLED (Paper Mode)</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; font-size: 14px;">
                            <span style="color:var(--text-muted)">Alpaca Context:</span>
                            <span id="alpaca-context" style="font-weight:600;">Paper API</span>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <h2 class="section-title">Live news & sentiment</h2>
                    <div id="news-hud-container" style="display: flex; flex-direction: column; gap: 12px; max-height: 350px; overflow-y: auto; padding-right: 4px;">
                        <div class="no-data">Fetching news updates...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 2. MANUAL TRADER TAB -->
        <div id="trader-tab" class="tab-content">
            <div class="card">
                <h2 class="section-title">Interactive Order Ticket</h2>
                
                <div class="side-selector">
                    <div class="side-btn active buy" id="side-buy" onclick="selectSide('BUY')">BUY / LONG</div>
                    <div class="side-btn sell" id="side-sell" onclick="selectSide('SELL')">SELL / SHORT</div>
                </div>

                <div class="form-group">
                    <label for="order-asset-type">Asset Class</label>
                    <select id="order-asset-type" onchange="adjustAssetForm()">
                        <option value="SPOT">SPOT (Crypto)</option>
                        <option value="STOCK">STOCK (Alpaca)</option>
                        <option value="PERP">PERP FUTURES (Binance)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="order-symbol">Symbol</label>
                    <select id="order-symbol">
                        <!-- Populated dynamically based on asset type -->
                    </select>
                </div>

                <div class="form-group" id="group-leverage" style="display:none;">
                    <label for="order-leverage">Leverage: <span class="range-value" id="val-leverage">5x</span></label>
                    <input type="range" id="order-leverage" min="1" max="25" value="5" oninput="document.getElementById('val-leverage').innerText = this.value + 'x'" style="width:100%">
                </div>

                <div class="form-group">
                    <label for="order-qty">Quantity</label>
                    <input type="number" id="order-qty" class="form-control" placeholder="Enter amount to trade" step="any">
                </div>

                <button class="btn-submit buy" id="btn-submit-order" onclick="submitManualOrder()">Submit BUY Order</button>
            </div>

            <div class="card">
                <h2 class="section-title">Manual Order Execution Safety</h2>
                <div style="font-size: 14px; line-height: 1.6; color: var(--text-muted)">
                    <p style="margin-bottom: 12px;">Manual orders bypass strategy checks but are subjected to the exact same fees, commissions, and safety regulations.</p>
                    <p style="margin-bottom: 12px;"><strong style="color:var(--text-main)">Paper Mode:</strong> Fills at simulated best bid/ask or mid price including slip.</p>
                    <p><strong style="color:var(--text-main)">Production Live Mode:</strong> Places immediate orders directly on exchange books.</p>
                </div>
            </div>
        </div>

        <!-- 3. RISK CONFIG TAB -->
        <div id="settings-tab" class="tab-content">
            <div class="card">
                <h2 class="section-title">Risk settings</h2>
                
                <div class="form-group">
                    <label for="config-kelly">Kelly fraction: <span class="range-value" id="val-config-kelly">0.25</span></label>
                    <input type="range" id="config-kelly" min="0.05" max="0.50" step="0.05" value="0.25" oninput="document.getElementById('val-config-kelly').innerText = this.value" style="width:100%;">
                </div>

                <div class="form-group">
                    <label for="config-slippage">Slippage buffer (BPS)</label>
                    <input type="number" id="config-slippage" class="form-control" min="0" max="50" step="1" value="2">
                </div>

                <button class="btn-action" onclick="saveRiskConfig()" style="width:100%; justify-content:center; padding:12px;">Save Configurations</button>
            </div>

            <div class="card" style="display:flex; flex-direction:column; gap:20px;">
                <h2 class="section-title">System switches</h2>
                
                <div class="toggle-container">
                    <div>
                        <div style="font-weight:600;">Active Strategy Engine</div>
                        <div style="font-size:12px; color:var(--text-muted);">Pause or resume strategy execution loops</div>
                    </div>
                    <label class="switch">
                        <input type="checkbox" id="toggle-pause-engine" onchange="toggleEnginePause(this.checked)">
                        <span class="slider"></span>
                    </label>
                </div>

                <button class="btn-action" onclick="resetSafetyDrawdown()" style="width:100%; justify-content:center; color:var(--accent-red); border-color:rgba(248, 81, 73, 0.2); background:rgba(248,81,73,0.05);">Reset Drawdown safety lock</button>
            </div>
        </div>

        <!-- 4. AUDIT LEDGER TAB -->
        <div id="ledger-tab" class="tab-content single-col">
            <div class="card">
                <div class="ledger-toolbar">
                    <input type="text" id="ledger-search" class="form-control" placeholder="Search symbol or action..." style="max-width:300px;" oninput="filterLedger()">
                    <button class="btn-action" onclick="downloadLedgerCSV()">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                        Export CSV Ledger
                    </button>
                </div>

                <div style="overflow-x: auto;">
                    <table id="ledger-table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Action</th>
                                <th>Asset Type</th>
                                <th>Symbol</th>
                                <th>Qty</th>
                                <th>Execution Price</th>
                                <th>Fees Paid</th>
                                <th>Verification response hash</th>
                            </tr>
                        </thead>
                        <tbody id="ledger-body">
                            <tr>
                                <td colspan="8" class="no-data">No transactions logged yet.</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </main>

    <script>
        let chartInstance = null;
        let balanceHistory = [10000.0];
        let labelHistory = ['Init'];
        let activeSide = 'BUY';
        let fullLedger = [];

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Find tab button that matches click
            const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.innerText === event.target.innerText);
            if (activeBtn) activeBtn.classList.add('active');
            
            document.getElementById(tabId).classList.add('active');
        }

        function selectSide(side) {
            activeSide = side;
            document.getElementById('side-buy').classList.remove('active');
            document.getElementById('side-sell').classList.remove('active');
            
            if (side === 'BUY') {
                document.getElementById('side-buy').classList.add('active');
                document.getElementById('btn-submit-order').className = 'btn-submit buy';
                document.getElementById('btn-submit-order').innerText = 'Submit BUY Order';
            } else {
                document.getElementById('side-sell').classList.add('active');
                document.getElementById('btn-submit-order').className = 'btn-submit sell';
                document.getElementById('btn-submit-order').innerText = 'Submit SELL Order';
            }
        }

        function adjustAssetForm() {
            const asset = document.getElementById('order-asset-type').value;
            const symSelect = document.getElementById('order-symbol');
            const levGroup = document.getElementById('group-leverage');
            
            symSelect.innerHTML = '';
            if (asset === 'SPOT') {
                symSelect.innerHTML = '<option value="BTCUSDT">BTCUSDT (Binance)</option>';
                levGroup.style.display = 'none';
            } else if (asset === 'STOCK') {
                symSelect.innerHTML = '<option value="AAPL">AAPL (Apple)</option><option value="MSFT">MSFT (Microsoft)</option>';
                levGroup.style.display = 'none';
            } else if (asset === 'PERP') {
                symSelect.innerHTML = '<option value="BTCUSDT">BTCUSDT Perpetual</option>';
                levGroup.style.display = 'block';
            }
        }

        function initChart() {
            const ctx = document.getElementById('equityChart').getContext('2d');
            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labelHistory,
                    datasets: [{
                        label: 'Valuation Curve',
                        data: balanceHistory,
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.08)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.2,
                        pointRadius: 2,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#8b949e', font: {family:'Outfit'} } },
                        y: { grid: { color: 'rgba(255, 255, 255, 0.03)' }, ticks: { color: '#8b949e', font: {family:'Outfit'} } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        async function updateDashboard() {
            try {
                const response = await fetch('/api/data');
                const data = await response.json();

                fullLedger = data.ledger;

                // 1. Update valuation & metrics
                const portfolioVal = data.portfolio_value;
                document.getElementById('val-portfolio').innerText = '$' + portfolioVal.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                document.getElementById('val-cash').innerText = '$' + data.cash.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
                document.getElementById('val-trades').innerText = data.ledger.length;

                // Configure is_paused state on settings switch
                document.getElementById('toggle-pause-engine').checked = !data.is_paused;

                // Handle server modes
                document.getElementById('val-status').innerText = data.is_paused ? 'PAUSED' : 'RUNNING';
                document.getElementById('val-status').className = 'metric-value ' + (data.is_paused ? 'down' : 'up');

                // Render live status configurations
                document.getElementById('live-mode-status').innerText = data.live_trading ? 'ENABLED (LIVE CASH)' : 'DISABLED (Paper Mode)';
                document.getElementById('live-mode-status').className = data.live_trading ? 'up' : 'down';
                document.getElementById('bot-mode-badge').innerText = data.live_trading ? 'LIVE API ROUTING' : 'PAPER SIMULATOR';
                document.getElementById('status-dot-element').style.backgroundColor = data.live_trading ? 'var(--accent-red)' : 'var(--accent-green)';

                const pnlPct = ((portfolioVal - 10000.0) / 10000.0) * 100;
                const changeEl = document.getElementById('val-change');
                changeEl.innerText = (pnlPct >= 0 ? '+' : '') + pnlPct.toFixed(2) + '%';
                changeEl.className = 'metric-sub ' + (pnlPct >= 0 ? 'up' : 'down');

                // 2. Render positions & assets
                const posBody = document.getElementById('positions-body');
                let rowsHtml = '';
                let hasHoldings = false;

                // Render Spot Holdings
                for (const [sym, qty] of Object.entries(data.spot_holdings)) {
                    if (qty > 0) {
                        hasHoldings = true;
                        rowsHtml += `<tr>
                            <td><strong>${sym}</strong></td>
                            <td><span class="badge-type badge-spot">SPOT</span></td>
                            <td>${qty.toFixed(6)}</td>
                            <td>-</td>
                            <td>Asset Position</td>
                        </tr>`;
                    }
                }

                // Render Stock Holdings
                for (const [sym, shares] of Object.entries(data.stock_holdings)) {
                    if (shares > 0) {
                        hasHoldings = true;
                        rowsHtml += `<tr>
                            <td><strong>${sym}</strong></td>
                            <td><span class="badge-type badge-stock">STOCK</span></td>
                            <td>${shares.toFixed(4)}</td>
                            <td>-</td>
                            <td>Asset Position</td>
                        </tr>`;
                    }
                }

                // Render Perpetuals Positions
                for (const [sym, pos] of Object.entries(data.perp_positions)) {
                    if (pos.size !== 0) {
                        hasHoldings = true;
                        const direction = pos.size > 0 ? 'LONG' : 'SHORT';
                        const dirClass = pos.size > 0 ? 'up' : 'down';
                        rowsHtml += `<tr>
                            <td><strong>${sym}</strong> <span class="${dirClass}" style="font-size:11px; font-weight:700;">${direction} ${pos.leverage}x</span></td>
                            <td><span class="badge-type badge-perp">PERP</span></td>
                            <td>${pos.size.toFixed(4)}</td>
                            <td>$${pos.entry_price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                            <td>$${pos.margin.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                        </tr>`;
                    }
                }

                if (hasHoldings) {
                    posBody.innerHTML = rowsHtml;
                } else {
                    posBody.innerHTML = `<tr><td colspan="5" class="no-data">No positions held currently.</td></tr>`;
                }

                // 3. Render ledger logs
                renderLedgerTable(data.ledger);

                // Update Chart Data
                let currentHist = 10000.0;
                const histVals = [10000.0];
                const histLabels = ['Init'];
                data.ledger.forEach((tx, idx) => {
                    if (tx.action === 'FUNDING' || tx.action === 'LIQUIDATION' || tx.action === 'SELL') {
                        currentHist += tx.net_cash_change;
                    }
                    histVals.push(currentHist);
                    histLabels.push('#' + (idx+1));
                });

                if (histVals[histVals.length - 1] !== portfolioVal) {
                    histVals.push(portfolioVal);
                    histLabels.push('Live');
                }

                // Update News HUD
                const newsContainer = document.getElementById('news-hud-container');
                if (data.news && data.news.length > 0) {
                    let newsHtml = '';
                    data.news.forEach(item => {
                        const score = item.sentiment_score || 0.0;
                        const label = item.sentiment_label || 'Neutral';
                        let badgeClass = 'sentiment-neutral';
                        if (label === 'Positive') badgeClass = 'sentiment-positive';
                        else if (label === 'Negative') badgeClass = 'sentiment-negative';
                        
                        const timeStr = item.published_utc ? item.published_utc.substring(11, 16) : '';
                        const queryBadge = `<span style="font-family:var(--font-mono); color:var(--accent-blue); font-size:10px; font-weight:700; margin-right:6px;">[${item.asset_query}]</span>`;
                        
                        newsHtml += `
                        <div class="news-item">
                            <div class="news-title">
                                <a href="${item.link}" target="_blank" style="color:inherit; text-decoration:none;">${item.title}</a>
                            </div>
                            <div class="news-meta">
                                <div>
                                    ${queryBadge}
                                    <span>${item.publisher}</span>
                                </div>
                                <div style="display:flex; align-items:center; gap:6px;">
                                    <span>${timeStr}</span>
                                    <span class="badge-sentiment ${badgeClass}" title="Score: ${score.toFixed(2)}">${label}</span>
                                </div>
                            </div>
                        </div>`;
                    });
                    newsContainer.innerHTML = newsHtml;
                } else {
                    newsContainer.innerHTML = `<div class="no-data">No news updates available.</div>`;
                }

                if (chartInstance) {
                    chartInstance.data.labels = histLabels;
                    chartInstance.data.datasets[0].data = histVals;
                    chartInstance.update();
                }

            } catch (err) {
                console.error("Dashboard update error:", err);
            }
        }

        function renderLedgerTable(ledger) {
            const ledgerBody = document.getElementById('ledger-body');
            if (ledger.length > 0) {
                let ledgerHtml = '';
                const reversedLedger = [...ledger].reverse();
                reversedLedger.forEach(tx => {
                    const actionBadge = tx.action === 'BUY' || tx.action === 'LONG' ? 'badge-buy' : 'badge-sell';
                    const shortHash = tx.response_hash ? tx.response_hash.substring(0, 12) + '...' : '-';
                    const fullHash = tx.response_hash || '';
                    
                    ledgerHtml += `<tr>
                        <td style="color:var(--text-muted);">${tx.timestamp.substring(11, 19)}</td>
                        <td><span class="badge-action ${actionBadge}">${tx.action}</span></td>
                        <td><span class="badge-type badge-${tx.asset_type.toLowerCase()}">${tx.asset_type}</span></td>
                        <td><strong>${tx.symbol}</strong></td>
                        <td>${tx.qty.toFixed(6)}</td>
                        <td>$${tx.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>
                        <td>$${tx.fee_usd.toFixed(4)}</td>
                        <td class="audit-hash" data-full-hash="${fullHash}" onclick="alert('Full Hash: ' + this.getAttribute('data-full-hash'))">${shortHash}</td>
                    </tr>`;
                });
                ledgerBody.innerHTML = ledgerHtml;
            } else {
                ledgerBody.innerHTML = `<tr><td colspan="8" class="no-data">No transactions logged yet.</td></tr>`;
            }
        }

        function filterLedger() {
            const query = document.getElementById('ledger-search').value.toLowerCase();
            const filtered = fullLedger.filter(tx => 
                tx.symbol.toLowerCase().includes(query) || 
                tx.action.toLowerCase().includes(query) || 
                tx.asset_type.toLowerCase().includes(query)
            );
            renderLedgerTable(filtered);
        }

        async function submitManualOrder() {
            const asset_type = document.getElementById('order-asset-type').value;
            const symbol = document.getElementById('order-symbol').value;
            const qty = parseFloat(document.getElementById('order-qty').value);
            const leverage = parseFloat(document.getElementById('order-leverage').value);

            if (isNaN(qty) || qty <= 0) {
                alert("Please enter a valid positive quantity.");
                return;
            }

            const confirmMsg = `Confirm placement of manual ${activeSide} order for ${qty} ${symbol} (${asset_type})?`;
            if (!confirm(confirmMsg)) {
                return;
            }

            try {
                const response = await fetch('/api/order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asset_type, symbol, side: activeSide, qty, leverage })
                });
                const res = await response.json();
                if (res.status === 'success') {
                    alert(`Order executed successfully! Filled at: $${res.price}`);
                    updateDashboard();
                } else {
                    alert(`Order failed: ${res.message}`);
                }
            } catch (err) {
                alert("Network error executing order: " + err);
            }
        }

        async function saveRiskConfig() {
            const kelly = parseFloat(document.getElementById('config-kelly').value);
            const slippage = parseFloat(document.getElementById('config-slippage').value);

            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ kelly_fraction: kelly, slippage_bps: slippage })
                });
                const res = await response.json();
                if (res.status === 'success') {
                    alert("Risk parameters updated successfully!");
                    updateDashboard();
                }
            } catch (err) {
                alert("Failed to update config: " + err);
            }
        }

        async function toggleEnginePause(isChecked) {
            const action = isChecked ? 'resume' : 'pause';
            try {
                await fetch('/api/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action })
                });
                updateDashboard();
            } catch (err) {
                console.error("Pause toggle failed:", err);
            }
        }

        async function resetSafetyDrawdown() {
            if (!confirm("Are you sure you want to reset the safety drawdown lock? The bot will resume strategy runs.")) {
                return;
            }
            try {
                const response = await fetch('/api/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'reset_safety' })
                });
                const res = await response.json();
                if (res.status === 'success') {
                    alert("Safety drawdown lock reset completed!");
                    updateDashboard();
                }
            } catch (err) {
                alert("Failed to reset safety: " + err);
            }
        }

        function downloadLedgerCSV() {
            if (fullLedger.length === 0) {
                alert("Ledger is empty. No data to export.");
                return;
            }

            let csvContent = "data:text/csv;charset=utf-8,";
            csvContent += "Timestamp,Action,Asset Type,Symbol,Qty,Price,Fee (USD),Response Hash\\r\\n";

            fullLedger.forEach(tx => {
                csvContent += `"${tx.timestamp}","${tx.action}","${tx.asset_type}","${tx.symbol}",${tx.qty},${tx.price},${tx.fee_usd},"${tx.response_hash}"\\r\\n`;
            });

            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", `transaction_ledger_export_${new Date().toISOString().substring(0,10)}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        // Observability live feeds
        async function updateObservability() {
            try {
                const btcSpotRes = await fetch('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT');
                const btcSpot = await btcSpotRes.json();
                document.getElementById('obs-btc-spot').innerText = '$' + parseFloat(btcSpot.price).toLocaleString(undefined, {minimumFractionDigits: 2});

                const btcPerpRes = await fetch('https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT');
                const btcPerp = await btcPerpRes.json();
                document.getElementById('obs-btc-perp').innerText = '$' + parseFloat(btcPerp.markPrice).toLocaleString(undefined, {minimumFractionDigits: 2});
                
                // AAPL
                const aaplRes = await fetch('https://query2.finance.yahoo.com/v8/finance/chart/AAPL');
                const aapl = await aaplRes.json();
                const aaplPrice = aapl.chart.result[0].meta.regularMarketPrice;
                document.getElementById('obs-aapl').innerText = '$' + parseFloat(aaplPrice).toLocaleString(undefined, {minimumFractionDigits: 2});
            } catch (e) {
                console.log("Observability update error", e);
            }
        }

        window.onload = () => {
            adjustAssetForm();
            initChart();
            updateDashboard();
            updateObservability();
            setInterval(updateDashboard, 2000);
            setInterval(updateObservability, 4000);
        };
    </script>
</body>
</html>
"""


class DashboardServer(http.server.BaseHTTPRequestHandler):
    engine_ref: HonestEngine | None = None
    prices_callback: Callable[[], Dict[str, float]] | None = None

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            current_prices = {}
            if DashboardServer.prices_callback:
                current_prices = DashboardServer.prices_callback()

            engine = DashboardServer.engine_ref
            portfolio_val = engine.get_portfolio_value(current_prices) if engine else 10000.0

            data = {
                "cash": engine.cash if engine else 10000.0,
                "portfolio_value": portfolio_val,
                "spot_holdings": engine.spot_holdings if engine else {},
                "stock_holdings": engine.stock_holdings if engine else {},
                "perp_positions": engine.perp_positions if engine else {},
                "ledger": engine.ledger if engine else [],
                "is_paused": engine.is_paused if engine else False,
                "kelly_fraction": engine.kelly_fraction if engine else 0.25,
                "slippage_bps": engine.slippage_bps if engine else 2.0,
                "live_trading": config.LIVE_TRADING,
                "news": getattr(DashboardServer, "news_cache", []),
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))

        elif self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length).decode("utf-8")
        data = json.loads(post_data)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        engine = DashboardServer.engine_ref
        if not engine:
            self.wfile.write(json.dumps({"status": "error", "message": "Engine reference missing"}).encode("utf-8"))
            return

        if self.path == "/api/control":
            action = data.get("action")
            if action == "pause":
                engine.is_paused = True
                logger.info("Bot paused via Dashboard UI Control.")
                self.wfile.write(json.dumps({"status": "success", "message": "Bot paused"}).encode("utf-8"))
            elif action == "resume":
                engine.is_paused = False
                logger.info("Bot resumed via Dashboard UI Control.")
                self.wfile.write(json.dumps({"status": "success", "message": "Bot resumed"}).encode("utf-8"))
            elif action == "reset_safety":
                engine.is_paused = False
                logger.info("Bot safety reset cleared via Dashboard UI Control.")
                self.wfile.write(json.dumps({"status": "success", "message": "Safety reset cleared"}).encode("utf-8"))
            else:
                self.wfile.write(json.dumps({"status": "error", "message": f"Unknown action: {action}"}).encode("utf-8"))

        elif self.path == "/api/config":
            kelly = data.get("kelly_fraction")
            slippage = data.get("slippage_bps")
            
            if kelly is not None:
                engine.kelly_fraction = max(0.01, min(float(kelly), 0.50))
            if slippage is not None:
                engine.slippage_bps = max(0.0, float(slippage))
                
            logger.info(f"Risk configuration updated via UI: Kelly={engine.kelly_fraction}, Slippage={engine.slippage_bps}")
            self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))

        elif self.path == "/api/order":
            asset_type = data.get("asset_type")
            symbol = data.get("symbol")
            side = data.get("side")
            qty = float(data.get("qty"))
            leverage = float(data.get("leverage", 1.0))

            try:
                tx = {}
                if asset_type == "SPOT":
                    # Get current live book ticker
                    spot_book = prices.fetch_spot_book_top(symbol)
                    tx = engine.execute_spot_market_order(symbol, side, qty, spot_book)
                elif asset_type == "STOCK":
                    price_env = prices.fetch_stock_price(symbol)
                    tx = engine.execute_stock_market_order(symbol, side, qty, price_env)
                elif asset_type == "PERP":
                    perp_prem = prices.fetch_perp_premium(symbol)
                    perp_fee = prices.fetch_perp_commission_rate(symbol)
                    tx = engine.execute_perp_market_order(symbol, side, qty, leverage, perp_prem, perp_fee)
                else:
                    raise ValueError(f"Unknown asset type: {asset_type}")

                self.wfile.write(json.dumps({"status": "success", "price": tx["price"]}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Manual order submission failed: {e}")
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode("utf-8"))
        else:
            self.wfile.write(json.dumps({"status": "error", "message": "Unknown API endpoint"}).encode("utf-8"))


def news_poll_loop():
    import time
    logger.info("Starting background news polling loop...")
    from tradingbot.sentiment import LexiconSentimentModel
    sentiment_model = LexiconSentimentModel()
    symbols_to_query = ["BTC", "AAPL"]
    while True:
        try:
            all_news = []
            seen_uuids = set()
            for sym in symbols_to_query:
                res = prices.fetch_market_news(sym)
                raw_news = res.get("news", [])
                for item in raw_news:
                    uuid = item.get("uuid")
                    if uuid and uuid not in seen_uuids:
                        seen_uuids.add(uuid)
                        title = item.get("title", "")
                        score = sentiment_model.analyze_sentiment(title)
                        label = sentiment_model.get_sentiment_label(score)
                        item["sentiment_score"] = score
                        item["sentiment_label"] = label
                        item["asset_query"] = sym
                        all_news.append(item)
            # Sort by published_time descending
            all_news.sort(key=lambda x: x.get("published_time", 0), reverse=True)
            DashboardServer.news_cache = all_news[:15]
        except Exception as e:
            logger.error(f"Error fetching news in background: {e}")
        time.sleep(60)


def start_dashboard(
    engine: HonestEngine, prices_callback: Callable[[], Dict[str, float]], port: int = 8000
) -> threading.Thread:
    """Start the dashboard server in a background thread."""
    DashboardServer.engine_ref = engine
    DashboardServer.prices_callback = prices_callback

    # Start news thread
    t_news = threading.Thread(target=news_poll_loop, daemon=True)
    t_news.start()

    server = http.server.HTTPServer(("localhost", port), DashboardServer)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"Interactive Dashboard server started at http://localhost:{port}/")
    print(f"--> Interactive Fullstack Dashboard live at: http://localhost:{port}/")
    return t
