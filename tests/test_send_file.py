from datetime import timedelta
from datetime import timezone 
import datetime as dt

import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

import HABSlib as hb

# Usage:
# % source bos/bin/activate
# % python HABSlib/test_ghost.py

hb.handshake(base_url="http://0.0.0.0", user_id='8d60e8693a9560ee57e8eba3')
# hb.handshake(base_url="http://74.249.61.11", user_id='8d60e8693a9560ee57e8eba3')
# hb.handshake(base_url="http://135.237.144.125", user_id='8d60e8693a9560ee57e8eba3')

# Recommended use of UTC timezone (standard in BrainOS)
sessiondate = dt.datetime.now(timezone.utc)
sessiondate = sessiondate.replace(tzinfo=timezone.utc) 

session_id = hb.send_file(
    user_id='8d60e8693a9560ee57e8eba3', 
    date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 
    edf_file=r"tests/test_data.edf", 
    ch_nrs=[0,1,2,3], 
    session_type="Upload data", 
    tags=['edf', 'file']
)

print("this session:", session_id)

b_notch, a_notch = signal.iirnotch(50., 2.0, 256)
sos = signal.butter(10, [1, 40], 'bandpass', fs=256, output='sos')

task_id, processed_data = hb.process_session_pipe(
    pipeline='filtering/artifact/beta',
    params={ 
        # dictionary, the order does not matter, they will be called by key
        "filtering": {
            'a_notch': a_notch.tolist(),
            'b_notch': b_notch.tolist(),
            'sos': sos.tolist(),
        },
        "artifact":{},
        "beta":{},
    },
    user_id='8d60e8693a9560ee57e8eba3', 
    date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 
    existing_session_id=session_id,
    session_type=f"post-processing test beta", 
    tags=['test beta']
)
processed_data = np.array(processed_data)
print(processed_data.shape)
print("this session:", task_id, processed_data)
