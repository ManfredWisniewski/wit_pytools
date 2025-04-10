from eliot import to_file
from eliot.json import EliotJSONEncoder
import os
import json
from datetime import datetime

class CustomEliotEncoder(EliotJSONEncoder):
    def default(self, obj):
        result = super().default(obj)
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return result

def format_message(message):
    """Format the Eliot message to our preferences"""
    # Convert timestamp to readable format
    if 'timestamp' in message:
        timestamp = datetime.fromtimestamp(message['timestamp'])
        message['timestamp'] = timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    # Remove task_uuid
    message.pop('task_uuid', None)
    
    return json.dumps(message, cls=CustomEliotEncoder)

def setup_logging(config):
    """Setup Eliot logging with the given configuration"""
    if not config:
        return
        
    logdir = config['WIT PYTOOLS'].get('nctoolslogdir')
    if logdir:
        log_file = open(os.path.join(logdir, "mailsort.log"), "a")
        to_file(log_file, format_message)
