import multiprocessing

# Bind
bind = "0.0.0.0:5000"

# Workers
workers = 2
threads = 4
worker_class = "gthread"

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s'

# Process
preload_app = True
daemon = False
