#!/usr/bin/env python3
"""
tmux Control Daemon - Enables remote control of tmux session
Runs as LaunchAgent with SessionCreate=true to bypass restrictions
WebUI sends HTTP requests to this daemon to control tmux
"""

import os
import subprocess
import logging
from flask import Flask, jsonify, request
from pathlib import Path

# Setup logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "tmux_control_daemon.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
TMUX_SOCKET = Path.home() / ".tmux-gridbot" / "default"
SESSION_NAME = "gridbot"
START_SCRIPT = PROJECT_ROOT / "scripts" / "start_tmux_daemon.sh"

# Simple token-based auth (shared secret between WebUI and daemon)
AUTH_TOKEN = os.environ.get("GRIDBOT_CONTROL_TOKEN", "gridbot-secure-token-2025")


def verify_token():
    """Verify authorization token from request"""
    token = request.headers.get("X-Auth-Token")
    if token != AUTH_TOKEN:
        logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
        return False
    return True


def check_tmux_session():
    """Check if tmux session is running"""
    if not TMUX_SOCKET.exists():
        return False
    
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/tmux", "-S", str(TMUX_SOCKET), "list-sessions"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return SESSION_NAME in result.stdout
    except Exception as e:
        logger.error(f"Error checking tmux session: {e}")
        return False


def get_bot_pids():
    """Get PIDs of actual Python bot processes (not shells)"""
    if not check_tmux_session():
        return []
    
    try:
        # Find actual Python processes running the bots
        # pgrep doesn't support regex, so search for each bot separately
        all_pids = []
        for pattern in ["run.py", "guardian_bot", "monitor.py"]:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                pids = [int(pid.strip()) for pid in result.stdout.strip().split("\n") if pid.strip()]
                all_pids.extend(pids)
        return all_pids
    except Exception as e:
        logger.error(f"Error getting bot PIDs: {e}")
        return []


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "tmux-control-daemon",
        "port": 5556
    })


@app.route("/api/tmux/status", methods=["GET"])
def get_status():
    """Get tmux session status"""
    if not verify_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    session_running = check_tmux_session()
    pids = get_bot_pids() if session_running else []
    
    return jsonify({
        "session_running": session_running,
        "session_name": SESSION_NAME,
        "socket_path": str(TMUX_SOCKET),
        "bot_pids": pids,
        "bot_count": len(pids)
    })


@app.route("/api/tmux/start", methods=["POST"])
def start_tmux():
    """Start tmux session with all bots"""
    if not verify_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check if already running
    if check_tmux_session():
        logger.info("tmux session already running")
        return jsonify({
            "success": False,
            "message": "tmux session already running",
            "session_name": SESSION_NAME
        }), 400
    
    try:
        logger.info("Starting tmux session...")
        
        # Clean up stale socket - IMPROVED
        if TMUX_SOCKET.exists():
            logger.info("Found existing socket - checking if stale...")
            try:
                result = subprocess.run(
                    ["/opt/homebrew/bin/tmux", "-S", str(TMUX_SOCKET), "list-sessions"],
                    capture_output=True,
                    timeout=2
                )
                # Socket is good, session might be running
                if result.returncode == 0:
                    logger.warning("Socket is active - not removing")
                else:
                    logger.info("Socket is stale - removing")
                    TMUX_SOCKET.unlink()
            except Exception as e:
                logger.info(f"Socket check failed - removing: {e}")
                try:
                    TMUX_SOCKET.unlink()
                except:
                    pass
        
        # Create tmux session directly from Python - NO EXTERNAL SCRIPT
        tmux_cmd = "/opt/homebrew/bin/tmux"
        
        # 1. Create detached session
        logger.info("Creating tmux session...")
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "new-session", "-d", "-s", SESSION_NAME, "-n", "Bots"],
            cwd=str(PROJECT_ROOT),
            timeout=10,
            check=True
        )
        
        # CRITICAL FIX: Wait for session to be fully initialized
        import time
        time.sleep(2)  # Increased from 0 to 2 seconds
        
        # Verify session exists before sending keys
        verify_result = subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "list-panes", "-t", f"{SESSION_NAME}:0"],
            capture_output=True,
            timeout=3
        )
        if verify_result.returncode != 0:
            logger.error("Session created but panes not ready")
            raise Exception("Panes not ready after session creation")
        
        # 2. Start trading bot in first pane
        logger.info("Starting trading bot in pane 0...")
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "send-keys", "-t", f"{SESSION_NAME}:0.0",
             f"cd {PROJECT_ROOT} && export PYTHONPATH={PROJECT_ROOT}:$PYTHONPATH && python3 -u bot/run.py 2>&1 | tee -a logs/bot_live.log; exec bash", "C-m"],
            timeout=5,
            check=True
        )
        
        time.sleep(1)  # Increased from 0.5 to 1 second
        
        # 3. Split and start guardian
        logger.info("Creating guardian pane...")
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "split-window", "-h", "-t", f"{SESSION_NAME}:0.0"],
            timeout=5,
            check=True
        )
        time.sleep(1)  # Wait for pane to be ready
        
        logger.info("Starting guardian bot in pane 1...")
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "send-keys", "-t", f"{SESSION_NAME}:0.1",
             f"cd {PROJECT_ROOT} && export PYTHONPATH={PROJECT_ROOT}:$PYTHONPATH && python3 -u bot/guardian/guardian_bot.py 2>&1 | tee -a logs/guardian.log; exec bash", "C-m"],
            timeout=5,
            check=True
        )
        
        time.sleep(1)  # Increased from 0.5 to 1 second
        
        # 4. Split and start monitor
        logger.info("Creating monitor pane...")
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "split-window", "-v", "-t", f"{SESSION_NAME}:0.1"],
            timeout=5,
            check=True
        )
        time.sleep(1)  # Wait for pane to be ready
        
        logger.info("Starting monitor in pane 2...")
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "send-keys", "-t", f"{SESSION_NAME}:0.2",
             f"cd {PROJECT_ROOT} && export PYTHONPATH={PROJECT_ROOT}:$PYTHONPATH && python3 -u bot/heartbeat/monitor.py 2>&1 | tee -a logs/monitor.log; exec bash", "C-m"],
            timeout=5,
            check=True
        )
        
        time.sleep(1)  # Increased from 0.5 to 1 second
        
        # 5. Set layout
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "resize-pane", "-t", f"{SESSION_NAME}:0.0", "-x", "66%"],
            timeout=5
        )
        subprocess.run(
            [tmux_cmd, "-S", str(TMUX_SOCKET), "resize-pane", "-t", f"{SESSION_NAME}:0.1", "-y", "66%"],
            timeout=5
        )
        
        # Verify session started
        if not check_tmux_session():
            logger.error("tmux session not running after start")
            return jsonify({
                "success": False,
                "message": "Session not running after start"
            }), 500
        
        # Wait for bots to initialize
        time.sleep(3)
        
        pids = get_bot_pids()
        
        if len(pids) == 0:
            logger.warning("tmux session started but no bot processes detected")
            return jsonify({
                "success": True,
                "message": "tmux session started (bots initializing...)",
                "session_name": SESSION_NAME,
                "bot_pids": [],
                "bot_count": 0,
                "warning": "Bot processes not detected yet"
            })
        
        logger.info(f"tmux session started successfully with {len(pids)} bots")
        
        return jsonify({
            "success": True,
            "message": "tmux session started successfully",
            "session_name": SESSION_NAME,
            "bot_pids": pids,
            "bot_count": len(pids)
        })
        
    except subprocess.TimeoutExpired:
        logger.error("Timeout starting tmux session")
        return jsonify({
            "success": False,
            "message": "Timeout starting tmux session"
        }), 500
    except subprocess.CalledProcessError as e:
        logger.error(f"tmux command failed: {e}")
        logger.error(f"Command: {e.cmd}")
        logger.error(f"Return code: {e.returncode}")
        
        # Clean up failed session
        try:
            subprocess.run(["/opt/homebrew/bin/tmux", "-S", str(TMUX_SOCKET), "kill-session", "-t", SESSION_NAME], timeout=5)
        except:
            pass
        
        return jsonify({
            "success": False,
            "message": f"tmux command failed. Try: 1) Clean up with 'pkill -f bot/run.py', 2) Remove ~/.tmux-gridbot/default, 3) Retry"
        }), 500
    except Exception as e:
        logger.error(f"Error starting tmux: {e}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}. Try manual cleanup: rm -f ~/.tmux-gridbot/default"
        }), 500


@app.route("/api/tmux/stop", methods=["POST"])
def stop_tmux():
    """Stop tmux session and all bots"""
    if not verify_token():
        return jsonify({"error": "Unauthorized"}), 401
    
    # Check if running
    if not check_tmux_session():
        logger.info("tmux session not running")
        return jsonify({
            "success": False,
            "message": "tmux session not running"
        }), 400
    
    try:
        logger.info("Stopping tmux session...")
        
        # Get PIDs before killing
        pids = get_bot_pids()
        
        # Kill tmux session
        result = subprocess.run(
            ["/opt/homebrew/bin/tmux", "-S", str(TMUX_SOCKET), "kill-session", "-t", SESSION_NAME],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to stop tmux: {result.stderr}")
            return jsonify({
                "success": False,
                "message": "Failed to stop tmux session",
                "error": result.stderr
            }), 500
        
        # Verify session stopped
        if check_tmux_session():
            logger.error("tmux session still running after kill")
            return jsonify({
                "success": False,
                "message": "Session still running after kill"
            }), 500
        
        logger.info(f"tmux session stopped successfully (killed {len(pids)} bots)")
        
        return jsonify({
            "success": True,
            "message": "tmux session stopped successfully",
            "bots_stopped": len(pids),
            "pids_killed": pids
        })
        
    except subprocess.TimeoutExpired:
        logger.error("Timeout stopping tmux session")
        return jsonify({
            "success": False,
            "message": "Timeout stopping tmux session"
        }), 500
    except Exception as e:
        logger.error(f"Error stopping tmux: {e}")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500


if __name__ == "__main__":
    logger.info("Starting tmux Control Daemon on port 5556...")
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info(f"tmux socket: {TMUX_SOCKET}")
    logger.info(f"Session name: {SESSION_NAME}")
    
    # Run Flask server
    app.run(
        host="127.0.0.1",
        port=5556,
        debug=False,
        threaded=True
    )
