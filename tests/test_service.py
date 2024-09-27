import HABSlib as hb

from datetime import timedelta
from datetime import timezone 
import datetime 

# Usage:
# % source bos/bin/activate
# % python HABSlib/test_ghost.py

# hb.handshake(base_url="http://0.0.0.0", user_id='666c0158fcbfd9a830399121')
# hb.handshake(base_url="http://74.249.61.11", user_id='666c0158fcbfd9a830399121')
hb.handshake(base_url="http://135.237.144.125", user_id='666c0158fcbfd9a830399121')

# Recommended use of UTC timezone (standard in BrainOS)
sessiondate = datetime.datetime.now(timezone.utc)
sessiondate = sessiondate.replace(tzinfo=timezone.utc) 
# print(sessiondate)
# print(sessiondate.timestamp())


def consume_processed_data( proc_data ):
    print(proc_data)


session_id = hb.acquire_send_service(
    service_name='concentration',
    user_id='666c0158fcbfd9a830399121', 
    date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 
    board="SYNTHETIC", 
    extra={
        "eeg_channels": 16,
        "sampling_rate": 250,
        "noise": 1,
        "artifacts": 0.01,
        "modulation_type": 'random',
        "power_law_slope": 0.8,
        "asymmetry_strength": 0.8,
        "sequence": [("relaxed",10),("focus",40),("relaxed",10)]
    },
    serial_number="", 
    serial_port="", 
    stream_duration=60, 
    buffer_duration=5,
    session_type="concentration test", 
    tags=['Happy'],
    callback=consume_processed_data
)
print("this session:", session_id)
