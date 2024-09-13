import HABSlib as hb

from datetime import timedelta
from datetime import timezone 
import datetime 

import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

# Usage:
# % source bos/bin/activate
# % python HABSlib/test_pipe.py

hb.handshake(base_url="http://0.0.0.0", user_id='8d60e8693a9560ee57e8eba3')

# Recommended use of UTC timezone (standard in BrainOS)
sessiondate = datetime.datetime.now(timezone.utc)
sessiondate = sessiondate.replace(tzinfo=timezone.utc) 
# print(sessiondate)
# print(sessiondate.timestamp())

# Pipe setup and sending data
# preprocessing setup, requires a bit of knowledge about the data to process
b_notch, a_notch = signal.iirnotch(50., 2.0, 250)
sos = signal.butter(10, [1, 40], 'bandpass', fs=250, output='sos')

session_id = hb.acquire_send_pipe(
    ## Tests ##
    # pipeline='/filtering/artifact/mean',
    # pipeline='/filtering/artifact/std',
    # pipeline='/filtering/artifact/var',
    # pipeline='/filtering/artifact/kurtosis',
    # pipeline='/filtering/artifact/skew',
    # pipeline='/filtering/artifact/ifms',
    # pipeline='/filtering/artifact/delta',
    # pipeline='/filtering/artifact/theta',
    # pipeline='/filtering/artifact/alpha',
    # pipeline='/filtering/artifact/beta',
    # pipeline='/filtering/artifact/gamma',
    # pipeline='/filtering/artifact/zerocrossing',
    # pipeline='/filtering/artifact/hjorthmobility',
    # pipeline='/filtering/artifact/hjorthcomplexity',
    # pipeline='/filtering/artifact/entropy',
    # pipeline='/filtering/artifact/fractaldim',
    # pipeline='/filtering/artifact/hurst',
    # pipeline='/filtering/artifact/correlatedim',
    # pipeline='/filtering/artifact/selfaffinity',
    # pipeline='/filtering/artifact/relative',
    # pipeline='/filtering/artifact/asymmetry',
    # pipeline='/filtering/artifact/correlation',
    pipeline='/filtering/artifact/phaselocking',
    params={ 
        # dictionary, the order does not matter, they will be called by key
        "filtering": {
            'a_notch': a_notch.tolist(),
            'b_notch': b_notch.tolist(),
            'sos': sos.tolist(),
        },
        "artifact":{},
        # "mean":{},
        # "std":{},
        # "var":{},
        # "kurtosis":{},
        # "skew":{},
        # "ifms":{},
        # "delta":{},
        # "theta":{},
        # "alpha":{},
        # "beta":{},
        # "gamma":{},
        # "zerocrossing":{},
        # "hjorthmobility":{},
        # "hjorthcomplexity":{},
        # "entropy":{},
        # "fractaldim":{},
        # "hurst":{},
        # "correlatedim":{},
        # "selfaffinity":{},
        # "relative":{'band': 'alpha'},
        # "asymmetry":{'band':'alpha', 'channelA':0, 'channelB':2},
        # "correlation":{'band':'alpha', 'channelA':0, 'channelB':2},
        "phaselocking":{'band':'alpha', 'channelA':0, 'channelB':2},
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
    stream_duration=10, # 10 sec
    buffer_duration=5, # 5 sec epoch
    session_type="phaselocking test", 
    tags=['Happy']
)
print("this session:", session_id)