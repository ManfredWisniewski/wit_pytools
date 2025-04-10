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

# Global log file handle
_log_file = None

def log_setup(logdir=os.getcwd()):
    """Setup Eliot logging with the given configuration"""
    global _log_file
    
    try:
        # Don't open a new file if one is already open
        if _log_file is not None:
            return
            
        # Create directory if it doesn't exist
        os.makedirs(logdir, exist_ok=True)
        
        _log_file = open(os.path.join(logdir, "mailsort.log"), "a")
        to_file(_log_file, format_message)
    except Exception as e:
        print(f"Error setting up log file: {e}")
        # If we failed to set up logging, make sure we clean up
        if _log_file:
            _log_file.close()
            _log_file = None

def log_close():
    """Close the log file if it's open"""
    global _log_file
    if _log_file:
        _log_file.close()
        _log_file = None
