#!/usr/bin/env python3
"""
L2 Signal Executor for Strategy 020
Uses proven ATI pattern from NQ_Ninja_Trader
Runs on REBEL-ALLIANCE, executes signals in SimL2020
"""

import json
import logging
import socket
import time
from pathlib import Path
from datetime import datetime

# Paths (adjusted for Windows)
SIGNAL_FILE = Path(r"\\wsl.localhost\Ubuntu\home\rob\.openclaw\workspace\nq-l2-scalping\nt_bridge\signal_output.json")
POSITION_FILE = Path(r"C:\Users\hartw\Documents\NinjaTrader ML Bridge\position_state.json")
EXECUTIONS_FILE = Path(r"C:\Users\hartw\Documents\NinjaTrader ML Bridge\executions.csv")

# ATI Config
ATI_HOST = "127.0.0.1"
ATI_PORT = 36973
ACCOUNT = "SimL2020"
INSTRUMENT = "NQ 03-26"  # Update month as needed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("L2Executor")


class ATIClient:
    """
    TCP client for NinjaTrader 8's Automated Trading Interface.
    Copied from proven NQ_Ninja_Trader implementation.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 36973, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to the NinjaTrader ATI TCP server."""
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(self.timeout)
            self._sock.connect((self.host, self.port))
            self._connected = True
            log.info(f"✅ Connected to NinjaTrader ATI at {self.host}:{self.port}")
            return True
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            log.error(f"❌ Failed to connect to ATI: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Close the TCP connection."""
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
            self._connected = False
            log.info("Disconnected from ATI")

    def is_connected(self) -> bool:
        return self._connected

    def _ensure_connected(self) -> bool:
        """Reconnect if needed. Returns True if connected."""
        if self._connected:
            return True
        log.warning("Not connected, attempting reconnect...")
        return self.connect()

    def send(self, command: str) -> bool:
        """Send a raw ATI command string. Returns True if sent successfully."""
        if not self._ensure_connected():
            return False
        try:
            full_cmd = command.strip() + "\n"
            self._sock.sendall(full_cmd.encode("utf-8"))
            log.info(f"ATI >> {command}")
            return True
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            log.error(f"Send failed: {e}")
            self._connected = False
            return False

    def place_order(
        self,
        account: str,
        instrument: str,
        action: str,
        qty: int,
        order_type: str = "Market",
        tif: str = "GTC",
    ) -> bool:
        """
        Place an order via ATI.
        
        Format: PLACE;account;instrument;action;qty;order_type;limit_price;stop_price;
                tif;oco_id;order_id;strategy;strategy_id
        """
        parts = [
            "PLACE",
            account,
            instrument,
            action,
            str(qty),
            order_type,
            "",  # limit_price
            "",  # stop_price
            tif,
            "",  # oco_id
            "",  # order_id
            "L2_Strategy_020",  # strategy
            "",  # strategy_id
        ]
        cmd = ";".join(parts)
        return self.send(cmd)


class L2SignalExecutor:
    """Monitors signal file and executes via ATI."""
    
    def __init__(self):
        self.ati = ATIClient(ATI_HOST, ATI_PORT)
        self.last_signal_time = None
        
    def run(self):
        """Main loop: poll signal file, execute if new."""
        log.info("="*70)
        log.info("L2 SIGNAL EXECUTOR — Strategy 020")
        log.info("="*70)
        log.info(f"Signal file: {SIGNAL_FILE}")
        log.info(f"ATI: {ATI_HOST}:{ATI_PORT}")
        log.info(f"Account: {ACCOUNT}")
        log.info(f"Instrument: {INSTRUMENT}")
        log.info("="*70)
        
        # Connect to ATI
        if not self.ati.connect():
            log.error("❌ Failed to connect to NinjaTrader ATI")
            log.error("   Make sure NinjaTrader is running and ATI is enabled")
            return
        
        log.info("✅ Executor running, polling every 5 seconds...")
        
        while True:
            try:
                self.check_and_execute()
                time.sleep(5)
            except KeyboardInterrupt:
                log.info("⛔ Shutdown requested")
                self.ati.disconnect()
                break
            except Exception as e:
                log.error(f"❌ Error: {e}")
                time.sleep(5)
    
    def check_and_execute(self):
        """Check for new signal and execute."""
        if not SIGNAL_FILE.exists():
            return
        
        try:
            with open(SIGNAL_FILE, 'r') as f:
                signal = json.load(f)
            
            # Parse timestamp
            signal_time = datetime.fromisoformat(signal['timestamp'].replace('Z', '+00:00'))
            
            # Skip if already processed
            if self.last_signal_time and signal_time <= self.last_signal_time:
                return
            
            # Skip if dry_run
            if signal.get('dry_run', False):
                log.info(f"⏭️  DRY RUN signal skipped: {signal['direction']} @ {signal['entry_price']}")
                self.last_signal_time = signal_time
                return
            
            # Execute signal
            direction = signal['direction']
            action = "BUY" if direction == "long" else "SELL"
            qty = signal.get('contracts', 1)
            
            log.info(f"🎯 EXECUTING SIGNAL: {direction.upper()} x{qty}")
            log.info(f"   Entry: {signal['entry_price']:.2f}")
            log.info(f"   TP: {signal['tp_price']:.2f}")
            log.info(f"   SL: {signal['sl_price']:.2f}")
            
            # Place order via ATI
            success = self.ati.place_order(
                account=ACCOUNT,
                instrument=INSTRUMENT,
                action=action,
                qty=qty,
                order_type="Market"
            )
            
            if success:
                log.info("✅ Order sent to NinjaTrader")
                self.log_execution(signal)
            else:
                log.error("❌ Order failed")
            
            self.last_signal_time = signal_time
            
        except Exception as e:
            log.error(f"Error processing signal: {e}")
    
    def log_execution(self, signal):
        """Log execution to CSV."""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            line = f"{timestamp},strategy_020,{signal['direction']},{signal['entry_price']:.2f},{signal['tp_price']:.2f},{signal['sl_price']:.2f},{signal.get('contracts', 1)}\n"
            
            with open(EXECUTIONS_FILE, 'a') as f:
                f.write(line)
            
            log.info("✅ Logged to executions.csv")
        except Exception as e:
            log.warning(f"⚠️  Logging error: {e}")


if __name__ == "__main__":
    executor = L2SignalExecutor()
    executor.run()
