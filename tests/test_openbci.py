import HABSlib as hb

from datetime import timedelta
from datetime import timezone 
import datetime 

user_id = '666c0158fcbfd9a830399121'
hb.handshake(base_url="http://0.0.0.0", user_id=user_id)
# hb.handshake(base_url="http://74.249.61.11", user_id=user_id)

# Recommended use of UTC timezone (standard in BrainOS)
sessiondate = datetime.datetime.now(timezone.utc)
sessiondate = sessiondate.replace(tzinfo=timezone.utc) 

def consume_processed_data( proc_data ):
    print(proc_data)


session_id = hb.acquire_send_pipe(
    ## Tests ##
    pipeline='/filtering/artifact/alpha',
    params={ 
        "filtering": {},
        "artifact":{},
        "alpha":{},
    },
    user_id=user_id, 
    date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 

    board="CYTON_DAISY_BOARD",
    serial_port="/dev/cu.usbserial-DM01MWZV", # on mac, discover port typing on terminal: ls /dev/cu.*     
    serial_number="",     
    stream_duration=30, # sec
    buffer_duration=5, # sec epoch
    session_type="concentration test", 
    tags=['Happy'],
    callback=consume_processed_data
)
print("this session:", session_id)


# session_id = hb.acquire_send_service(
#     service_name='concentration',
#     user_id='8d60e8693a9560ee57e8eba3', 
#     date=sessiondate.strftime('%Y-%m-%dT%H:%M:%SZ'), 
#     board="CYTON_DAISY_BOARD",
#     serial_number="",     
#     stream_duration=30, # sec
#     buffer_duration=5, # sec epoch
#     session_type="concentration test", 
#     tags=['Happy'],
#     callback=consume_processed_data
# )
# print("this session:", session_id)
