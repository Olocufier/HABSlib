import HABSlib as hb

from datetime import timedelta
from datetime import timezone 
import datetime 

import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

# Usage:
# % source bos/bin/activate
# % python HABSlib/test_ghost.py

hb.handshake(base_url="http://0.0.0.0", user_id='8d60e8693a9560ee57e8eba3')
# hb.handshake(base_url="http://74.249.61.11", user_id='8d60e8693a9560ee57e8eba3')

#######################################################
#######################################################
# Recommended use of UTC timezone (standard in BrainOS)
sessiondate = datetime.datetime.now(timezone.utc)
sessiondate = sessiondate.replace(tzinfo=timezone.utc) 
# print(sessiondate)
# print(sessiondate.timestamp())

session_id = hb.acquire_send_raw(
    user_id='8d60e8693a9560ee57e8eba3', 
    date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 
    board="SYNTHETIC", 
    extra={
        "eeg_channels": 16,
        "sampling_rate": 250,
        "noise": 1,
        "artifacts": 0.01,
        "modulation_type": 'random',
        "power_law_slope": 0.8,
        # "sequence": [("relaxed",5),("focus",15)]
        "sequence": [("relaxed",10),("focus",40)]
    },
    serial_number="", 
    stream_duration=50, 
    buffer_duration=5,
    session_type="Ghost test"
)
print("this session:", session_id)
