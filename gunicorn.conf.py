import multiprocessing
import os

bind = "127.0.0.1:8000"
workers = min(multiprocessing.cpu_count(), 2)
worker_class = "sync"
timeout = 120
keepalive = 5
errorlog = "-"
accesslog = "-"
loglevel = "info"
