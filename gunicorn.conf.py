import multiprocessing

# Bind
bind = "0.0.0.0:5000"

# Workers - Use gevent for WebSocket support
workers = 1  # gevent uses a single worker with greenlets
worker_class = "gevent"

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s'

# Process
preload_app = False  # Must be False for gevent with websockets
daemon = False
