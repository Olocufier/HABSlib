import HABSlib as hb

from datetime import timedelta
from datetime import timezone 
import datetime 

# Usage:
# % source bos/bin/activate
# % python HABSlib/test_pipe.py

# hb.handshake(base_url="http://0.0.0.0", user_id='8d60e8693a9560ee57e8eba3')
# hb.handshake(base_url="http://74.249.61.11", user_id='8d60e8693a9560ee57e8eba3')
hb.handshake(base_url="http://135.237.144.125", user_id='8d60e8693a9560ee57e8eba3')

# Recommended use of UTC timezone (standard in BrainOS)
sessiondate = datetime.datetime.now(timezone.utc)
sessiondate = sessiondate.replace(tzinfo=timezone.utc) 
# print(sessiondate)
# print(sessiondate.timestamp())

def consume_processed_data( proc_data ):
    print(len(proc_data))

session_id = hb.acquire_send_pipe(
    ## Tests ##
    pipeline='/filtering/artifact/alpha',
    params={ 
        "filtering": {},
        "artifact":{},
        "alpha":{},
    },
    user_id='8d60e8693a9560ee57e8eba3', 
    date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 

    board="SYNTHETIC",
    extra={
        "eeg_channels": 4,
        "sampling_rate": 250,
        "noise": 1,
        "artifacts": 0.001,
        "modulation_type": 'random',
        "preset": 'drowsy', # None, # 'focus', 'alert', 'relaxed', 'drowsy'
        "sequence": None, # 
        # "sequence": [("relaxed",5),("focus",15)]
        "correlation_strength": 0.5,
        "power_law_slope": 0.8
    },
    serial_number="",     
    serial_port="", 
    stream_duration=30, # sec
    buffer_duration=5, # sec epoch
    session_type="concentration test", 
    tags=['Happy'],
    callback=consume_processed_data
)
print("this session:", session_id)