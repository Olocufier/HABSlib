"""
Company Name: HABS

Authors: Domenico Guarino

Deposited ID: IDDN.FR.001.290042.000.S.P.2024.000.10600

Note:
This code is currently not released to the public.

License:
All rights reserved.
"""
# USAGE:
# % source os/bin/activate
# % pip install -r requirements.txt
# % pytest tests/test_habslib.py

import pytest

import requests
import time

import sys
print(sys.path)

import os
import sys
import base64
import bson
from datetime import datetime

from scipy import signal

from . import BASE_URL, VERSION, BOARD
BASE_URL = "http://0.0.0.0"
VERSION = 'alpha'
BOARD = 'SYNTHETIC'
# BASE_URL = "http://74.249.61.11"
# BASE_URL = "http://135.237.144.125"

# HABSlib
import HABSlib as hb

#################################################################
# GLOBALS
g_user_id = None
g_session_id = None
g_data_id = None

#################################################################
import uuid

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


#################################################################
# - should create the rsa key pair
# - should reply {'status': 'success', 'api_public_key': api_public_key_pem}
# - should receive the rsa-encrypted AES key
# - should reply {'status': 'success'}

@pytest.mark.order(1)
@pytest.mark.dependency
def test_handshake():
    start_time = time.time()

    result = hb.handshake(base_url=BASE_URL, user_id='666c0158fcbfd9a830399121') 
    
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert result == True



#################################################################
# Set user/subject (if the user already exists it should not creat one)
# - should fail if the required param "email" is absent
# - should reply {'status': 'success', 'user_id': str(user_id)}

@pytest.mark.order(2)
@pytest.mark.dependency
@pytest.mark.parametrize("payload, expected_status", [ 
    # pytest.param({}, 400,  marks=pytest.mark.xfail()),
    ({'first_name': 'Domenico', 'last_name': 'Guarino', 'role': 'Admin', 'group': 'HABS', 'email': 'domenico@habs.ai', 'age': 50, 'weight': 89, 'gender': 'M'}, 208),
    ({'first_name': 'Federico', 'last_name': 'Tesler', 'role': 'Admin', 'group': 'HABS', 'email': 'federico@habs.ai', 'age': 30, 'weight': 79, 'gender': 'M'}, 200),
])
def test_set_user(payload, expected_status):
    print(payload)
    start_time = time.time()

    user_id = hb.set_user(user_id='666c0158fcbfd9a830399121', **payload) ## CALL
    print("test_set_user user_id",user_id)

    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert user_id is not None
    assert bson.objectid.ObjectId.is_valid(user_id)
    if bson.objectid.ObjectId.is_valid(user_id):
        global g_user_id
        g_user_id = user_id
    print("g_user_id",g_user_id)



#################################################################
# Get user data by id
# - if the user is found, should reply {'status': 'success', 'user_data': document}
# - if the user is not found, should reply {'status': 'error', 'message': 'User not found'}

@pytest.mark.order(3)
@pytest.mark.dependency(depends=["test_handshake"])
def test_get_user_by_id():
    print("g_user_id",g_user_id)
    start_time = time.time()

    user_data = hb.get_user_by_id(g_user_id)

    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert isinstance(user_data, dict)




#################################################################
@pytest.mark.order(4)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, expected_status", [
    ('666c0158fcbfd9a830399121', 200),
    pytest.param('8d60e8693a9560ee57e8eba3', 400,  marks=pytest.mark.xfail()), # an existing user id but not Admin
    pytest.param('non_existing_id', 400,  marks=pytest.mark.xfail())
])
def test_list_users(user_id, expected_status):
    start_time = time.time()

    users = hb.list_users(user_id)

    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert isinstance(users, list)==True




#################################################################
# Get user data by id
# - if the user is found, should reply {'status': 'success', 'user_data': document}
# - if the user is not found, should reply {'status': 'error', 'message': 'User not found'}

@pytest.mark.order(5)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, session_id, expected_status", [
    (g_user_id, '667ada8070f5cad4b0525749', 200),
    #             an existing user id         but a session id non belonging to that user
    pytest.param('5ce819935e539c343f141ece', '667ada8070f5cad4b0525749', 400,  marks=pytest.mark.xfail()),
    pytest.param('non_existing_id', 'non_existing_id', 400,  marks=pytest.mark.xfail())
])
def test_get_data_ids_by_session(user_id, session_id, expected_status):
    print("g_user_id",g_user_id)
    start_time = time.time()

    data_ids = hb.get_data_ids_by_session(session_id, user_id)

    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert bson.objectid.ObjectId.is_valid(data_ids[0])



# #################################################################
# # Simple sending data
# # - should receive the param "user_id"
# # - should return the session_id, a valid bson ObjectID

@pytest.mark.order(6)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, expected_status", [
    ('g_user_id', 200),
    pytest.param('non_existing_id', 400,  marks=pytest.mark.xfail()) # test xfail
])
def test_acquire_send_raw(user_id, expected_status):
    if user_id=='g_user_id':
        user_id = g_user_id
    start_time = time.time()
    session_id = hb.acquire_send_raw(
        user_id=user_id, 
        date=datetime.today().strftime('%Y-%m-%d'), 
        board=BOARD,
        extra={
            "eeg_channels": 16,
            "sampling_rate": 250,
            "noise": 1,
            "artifacts": 0.001,
            "modulation_type": 'random',
            "preset": 'focus', # None, # 'focus', 'alert', 'relaxed', 'drowsy'
            "sequence": None, # [("focus", 20), ("relaxed", 20)],
            "correlation_strength": 0.5
        },
        serial_number="", # in the back of the MUSE pod
        serial_port="", 
        stream_duration=10, 
        buffer_duration=5)
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert bson.objectid.ObjectId.is_valid(session_id)
    # update
    if bson.objectid.ObjectId.is_valid(session_id):
        global g_session_id
        g_session_id = session_id



#################################################################
# Pipe setup and sending data
# preprocessing setup, requires a bit of knowledge about the data to process
# - should receive the param "user_id"
# - should return the session_id, a valid bson ObjectID

@pytest.mark.order(7)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, feature, params, expected_status", [
    ('g_user_id', 'mean', {}, 200),
    ('g_user_id', 'std', {}, 200),
    ('g_user_id', 'var', {}, 200),
    ('g_user_id', 'kurtosis', {}, 200),
    ('g_user_id', 'skew', {}, 200),
    ('g_user_id', 'ifms', {}, 200),
    ('g_user_id', 'delta', {}, 200),
    ('g_user_id', 'theta', {}, 200),
    ('g_user_id', 'alpha', {}, 200),
    ('g_user_id', 'beta', {}, 200),
    ('g_user_id', 'gamma', {}, 200),
    ('g_user_id', 'zerocrossings', {}, 200),
    ('g_user_id', 'hjorthmobility', {}, 200),
    # ('g_user_id', 'hjorthcomplexity', {}, 200),
    ('g_user_id', 'entropy', {}, 200),
    # ('g_user_id', 'fractaldim', {}, 200),
    ('g_user_id', 'hurst', {}, 200),
    # ('g_user_id', 'correlatedim', {}, 200),
    ('g_user_id', 'selfaffinity', {}, 200),
    ('g_user_id', 'relative', {'band':'alpha'}, 200),
    ('g_user_id', 'asymmetry', {'band':'alpha', 'channelA':0, 'channelB':2}, 200),
    ('g_user_id', 'correlation', {'band':'alpha', 'channelA':0, 'channelB':2}, 200),
    ('g_user_id', 'phaselocking', {'band':'alpha', 'channelA':0, 'channelB':2}, 200),
    pytest.param({}, '', {}, 400, marks=pytest.mark.xfail()) # test xfail
])
def test_acquire_send_pipe(user_id, feature, params, expected_status):
    b_notch, a_notch = signal.iirnotch(50., 2.0, 256)
    sos = signal.butter(10, [1, 40], 'bandpass', fs=256, output='sos')
    if user_id=='g_user_id':
        user_id = g_user_id
    start_time = time.time()
    session_id = hb.acquire_send_pipe(
        pipeline='filtering/artifact/'+feature,
        params={ 
            # dictionary, the order does not matter, they will be called by key
            "filtering": {
                'a_notch': a_notch.tolist(),
                'b_notch': b_notch.tolist(),
                'sos': sos.tolist(),
            },
            "artifact":{},
            feature:params,
        },
        user_id=user_id, 
        date=datetime.today().strftime('%Y-%m-%d'), 
        board=BOARD,
        extra={
            "eeg_channels": 16,
            "sampling_rate": 250,
            "noise": 1,
            "artifacts": 0.001,
            "modulation_type": 'random',
            "preset": 'focus', # None, # 'focus', 'alert', 'relaxed', 'drowsy'
            "sequence": None, # [("focus", 20), ("relaxed", 20)],
            "correlation_strength": 0.5
        },
        serial_number="", # in the back of the MUSE pod
        serial_port="", 
        stream_duration=10, 
        buffer_duration=5,
        session_type=f"pipe test {feature}", 
        tags=['test '+feature]

    )
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert bson.objectid.ObjectId.is_valid(session_id)
    # update
    if bson.objectid.ObjectId.is_valid(session_id):
        global g_session_id
        g_session_id = session_id




#################################################################
# Perform analysis over existing data
# preprocessing setup, requires a bit of knowledge about the data to process
# - should receive the param "user_id"
# - should return the session_id, a valid bson ObjectID

@pytest.mark.order(8)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, feature, params, expected_status", [
    ('g_user_id', 'mean', {}, 200),
    ('g_user_id', 'std', {}, 200),
    ('g_user_id', 'var', {}, 200),
    ('g_user_id', 'kurtosis', {}, 200),
    ('g_user_id', 'skew', {}, 200),
    ('g_user_id', 'ifms', {}, 200),
    ('g_user_id', 'delta', {}, 200),
    ('g_user_id', 'theta', {}, 200),
    ('g_user_id', 'alpha', {}, 200),
    ('g_user_id', 'beta', {}, 200),
    ('g_user_id', 'gamma', {}, 200),
    ('g_user_id', 'zerocrossings', {}, 200),
    ('g_user_id', 'hjorthmobility', {}, 200),
    # ('g_user_id', 'hjorthcomplexity', {}, 200),
    ('g_user_id', 'entropy', {}, 200),
    # ('g_user_id', 'fractaldim', {}, 200),
    ('g_user_id', 'hurst', {}, 200),
    # ('g_user_id', 'correlatedim', {}, 200),
    ('g_user_id', 'selfaffinity', {}, 200),
    ('g_user_id', 'relative', {'band':'alpha'}, 200),
    ('g_user_id', 'asymmetry', {'band':'alpha', 'channelA':0, 'channelB':2}, 200),
    ('g_user_id', 'correlation', {'band':'alpha', 'channelA':0, 'channelB':2}, 200),
    ('g_user_id', 'phaselocking', {'band':'alpha', 'channelA':0, 'channelB':2}, 200),
    pytest.param({}, '', {}, 400, marks=pytest.mark.xfail()) # test xfail
])
def test_process_session_pipe(user_id, feature, params, expected_status):
    b_notch, a_notch = signal.iirnotch(50., 2.0, 256)
    sos = signal.butter(10, [1, 40], 'bandpass', fs=256, output='sos')
    if user_id=='g_user_id':
        user_id = g_user_id
    start_time = time.time()
    task_id, processed_data = hb.process_session_pipe(
        pipeline='filtering/artifact/'+feature,
        params={ 
            # dictionary, the order does not matter, they will be called by key
            "filtering": {
                'a_notch': a_notch.tolist(),
                'b_notch': b_notch.tolist(),
                'sos': sos.tolist(),
            },
            "artifact":{},
            feature:params,
        },
        user_id=user_id, 
        date=datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
        existing_session_id='667ada8070f5cad4b0525747',
        session_type=f"post-processing test {feature}", 
        tags=['test '+feature]
    )
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert is_valid_uuid(task_id)



#################################################################
# get all data joined by session id (piped or raw)
# - should receive the param "session_id"
# - should return a valid list

@pytest.mark.order(9)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("session_id, user_id, expected_status", [
    ('g_session_id', '666c0158fcbfd9a830399121', 200),
    pytest.param({}, '666c0158fcbfd9a830399121', 400,  marks=pytest.mark.xfail()) # test xfail
])
def test_get_data_by_session(session_id, user_id, expected_status):
    if session_id=='g_session_id':
        session_id = g_session_id
    start_time = time.time()
    results = hb.get_data_by_session(session_id=session_id, user_id=user_id)
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    # print(results)
    assert isinstance(results, list)




#################################################################
# get data ids by sesison id
# - should receive the param "data_id"
# - should return a valid list
@pytest.mark.order(11)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("session_id, user_id, expected_status", [
    ('667ada8070f5cad4b0525747', '666c0158fcbfd9a830399121', 200),
    pytest.param('badSessionId', '666c0158fcbfd9a830399121', 400, marks=pytest.mark.xfail()) # test xfail
])
def test_get_data_ids_by_session(session_id, user_id, expected_status):
    start_time = time.time()
    data = hb.get_data_ids_by_session(session_id, user_id)
    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    print(data)
    if isinstance(data, list):
        global g_data_id
        g_data_id = data[0]
    assert isinstance(data, list)==True



#################################################################
# create tags
# - should receive the param "data_id"
@pytest.mark.order(12)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("session_id, user_id, expected_status", [
    ('667ada8070f5cad4b0525747', '666c0158fcbfd9a830399121', 200),
    pytest.param('', '666c0158fcbfd9a830399121', 400, marks=pytest.mark.xfail()) # test xfail
])
def test_create_tagged_interval(session_id, user_id, expected_status):
    global g_data_id
    print("g_user_id",g_user_id)
    interval_id = hb.create_tagged_interval(
        user_id=user_id,
        session_id=session_id,
        start_time="2024-07-02T09:00:52Z",
        end_time="2024-07-02T09:00:54Z",
        tags=[{"tag": "seizure", "properties": {"severity": "high"}}]
    )
    assert bson.objectid.ObjectId.is_valid(interval_id)==True



#################################################################
# get data ids by sesison id
# - should receive the param "data_id"
# - should return a valid list
@pytest.mark.order(13)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("session_id, user_id, expected_status", [
    ('667ada8070f5cad4b0525747', '666c0158fcbfd9a830399121', 200),
    pytest.param('', '666c0158fcbfd9a830399121', 400, marks=pytest.mark.xfail()) # test xfail
])
def test_get_tagged_interval_data(session_id, user_id, expected_status):
    global g_data_id
    print("g_user_id",g_user_id)
    data = hb.get_tagged_interval_data(
        user_id="666c0158fcbfd9a830399121",
        session_id=session_id,
        tag="seizure"
    )
    assert isinstance(data, list)==True



#################################################################
# Perform analysis over existing data
# preprocessing setup, requires a bit of knowledge about the data to process

@pytest.mark.order(14)
@pytest.mark.dependency(depends=["test_handshake"])
@pytest.mark.parametrize("user_id, service_name, expected_status", [
    (g_user_id, 'concentration', 200),
    pytest.param('g_user_id', '', 400, marks=pytest.mark.xfail()) # test xfail
])
def test_process_session_service(user_id, service_name, expected_status):
    if user_id=='g_user_id':
        user_id = g_user_id
    start_time = time.time()

    from datetime import timezone 
    import datetime 

    # Recommended use of UTC timezone (standard in BrainOS)
    sessiondate = datetime.datetime.now(timezone.utc)
    sessiondate = sessiondate.replace(tzinfo=timezone.utc) 

    # local_data = None
    # def consume_processed_data( proc_data ):
    #     local_data = proc_data

    session_id = hb.acquire_send_service(
        service_name=service_name,
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
            "sequence": [("relaxed",10),("focus",10),("relaxed",10)]
        },
        serial_number="", 
        serial_port="", 
        stream_duration=30, 
        buffer_duration=5,
        session_type="concentration test", 
        tags=['Happy']
        # , callback=consume_processed_data
    )
    print("this session:", session_id)

    end_time = time.time()
    duration = end_time - start_time
    # Attach the duration to the test report
    # pytest.current_test_report.duration = duration
    assert bson.objectid.ObjectId.is_valid(session_id)
    # assert isinstance(local_data, float)

