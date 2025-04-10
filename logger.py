from eliot import to_file
import os

def setup_logging(config):
    """Setup Eliot logging with the given configuration"""
    if not config:
        return
        
    logdir = config['WIT PYTOOLS'].get('nctoolslogdir')
    if logdir:
        log_file = open(os.path.join(logdir, "mailsort.log"), "a")
        to_file(log_file)
