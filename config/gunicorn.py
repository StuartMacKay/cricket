import environ  # type: ignore

env = environ.Env()

# The port or socket to bind on
bind = env.str("GUNICORN_BIND", "0.0.0.0:8000")

# Log everything to stdout
accesslog = "-"

# Extend the default format by adding request time in micro-seconds
access_log_format = (
    "%(h)s %(l)s %(u)s %(t)s '%(r)s' %(s)s %(b)s '%(f)s' '%(a)s' in %(D)sµs"
)

loglevel = env.str("GUNICORN_LOG_LEVEL", "debug")

# Number of worker processes and threads per process. For development, the defaults of
# 1 is sufficient. For production this will need to be tuned according to workload. For
# an isolated web server then it will be up to 2 * number of cores + 1 - assuming an
# Intel CPU with 2 threads per code.
workers = env.int("GUNICORN_NUMBER_OF_WORKERS", 1)
threads = env.int("GUNICORN_NUMBER_OF_THREADS", 1)

# Restart workers when code changes - true for development only.
reload = env.bool("GUNICORN_RELOAD", False)

# Maximum number of requests before restarting workers. Default of 0 disables restarts.
max_requests = env.int("GUNICORN_MAX_REQUESTS", 0)

# Time to disable silent workers. Default is 30 seconds
timeout = env.int("GUNICORN_TIMEOUT", 30)
