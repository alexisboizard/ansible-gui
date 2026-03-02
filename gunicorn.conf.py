import multiprocessing

# Bind
bind = "127.0.0.1:5000"

# Workers
workers = 2
threads = 4
worker_class = "gthread"

# Timeouts
timeout = 120
keepalive = 5

# Logging
accesslog = "/var/log/ansible-gui/access.log"
errorlog = "/var/log/ansible-gui/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s'

# Process
preload_app = True
daemon = False
