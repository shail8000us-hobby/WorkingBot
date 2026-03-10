"""
Gunicorn configuration for GridBot WebUI Backend.

Usage:
    gunicorn -c gunicorn_config.py webui.backend.wsgi:app
"""
import os
import multiprocessing

# ============================================================================
# Server Socket
# ============================================================================
bind = "0.0.0.0:5555"
backlog = 256

# ============================================================================
# Worker Configuration
# ============================================================================
# Single worker: required for SocketIO (shared state) and instance lock
workers = 1
worker_class = "eventlet"
worker_connections = 500
timeout = 120          # Kill worker if no response in 120s
graceful_timeout = 30  # Time for worker to finish requests on shutdown
keepalive = 5

# ============================================================================
# Resource Limits — prevents Mac from crashing
# ============================================================================
# Max requests before worker recycles (prevents memory leaks)
max_requests = 10000
max_requests_jitter = 1000  # Randomize to prevent thundering herd

# ============================================================================
# Process
# ============================================================================
proc_name = "gridbot-webui"
pidfile = "/tmp/gridbot_webui.pid"
daemon = False  # LaunchAgent/start_webui.sh handles daemonization

# ============================================================================
# Logging
# ============================================================================
loglevel = "info"
accesslog = os.path.join(os.path.dirname(__file__), "logs", "gunicorn_access.log")
errorlog = os.path.join(os.path.dirname(__file__), "logs", "gunicorn_error.log")
access_log_format = '%(h)s %(l)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" %(D)sμs'

# ============================================================================
# Server Hooks
# ============================================================================
def on_starting(server):
    print(f"🚀 Gunicorn starting GridBot WebUI on {bind}")
    print(f"   Worker class: {worker_class}")
    print(f"   PID: {os.getpid()}")

def when_ready(server):
    print("✅ Gunicorn ready — accepting connections")

def pre_fork(server, worker):
    pass

def post_fork(server, worker):
    print(f"   Worker spawned (PID: {worker.pid})")

def worker_exit(server, worker):
    print(f"   Worker exited (PID: {worker.pid})")

def on_exit(server):
    print("🛑 Gunicorn shutting down")
