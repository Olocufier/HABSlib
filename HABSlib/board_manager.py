from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

import asyncio
import time
import math
import base64
import scipy 
import numpy as np
from scipy import signal



#############################
# BrainOS - FrontEnd - TODO #
#############################
#       
# - Consider multiple flows of data:
#       https://brainflow.org/2022-07-15-brainflow-5-1-0/
#       For Muse boards we’ve added EEG data to DEFAULT_PRESET, 
#       Accelerometer and Gyroscope data to AUXILIARY_PRESET 
#       and PPG data to ANCILLARY_PRESET (PPG not available for Muse 2016, so Muse 2016 has only two presets). 
#       Also, each preset has it’s own sampling rate, timestamp and package counter.



class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class BoardManager(metaclass=SingletonMeta):

    def __init__(self, enable_logger, board_id="SYNTHETIC_BOARD"):
        if not hasattr(self, 'initialized'):  # Prevent re-initialization
            self.board = None
            self.board_descr = None
            self.params = BrainFlowInputParams()

            if board_id == "MUSE_2":
                self.board_id = BoardIds.MUSE_2_BOARD
            elif board_id == "MUSE_S":
                self.board_id = BoardIds.MUSE_S_BOARD.value
            else:
                self.board_id = BoardIds.SYNTHETIC_BOARD

            if not enable_logger:
                BoardShim.disable_board_logger()
            self.initialized = True  # Mark as initialized
            # local availability
            self.data_ids = []
            self.processed_data = []

    def connect(self, retries=3, delay=2):
        if self.board is not None:
            raise Exception("Board already connected!")
        print("Connecting to the headset...")
        attempt = 0

        while attempt < retries:
            try:    
                self.board = BoardShim(self.board_id, self.params)
                self.board.prepare_session()
                self.board_descr = BoardShim.get_board_descr(self.board_id)
                # Muse S = {
                #     'eeg_channels': [1, 2, 3, 4], 
                #     'eeg_names': 'TP9,Fp1,Fp2,TP10', 
                #     'marker_channel': 7, 
                #     'name': 'MuseS', 
                #     'num_rows': 8, 
                #     'other_channels': [5], 
                #     'package_num_channel': 0, 
                #     'sampling_rate': 256, 
                #     'timestamp_channel': 6
                # }
                if "gyro_channels" in self.board_descr.keys():
                    self.gyro_channels = self.board.get_gyro_channels(self.board_id)
                if "accel_channels" in self.board_descr.keys():
                    self.accel_channels = self.board.get_accel_channels(self.board_id)
                if "ppg_channels" in self.board_descr.keys():
                    self.ppg_channels = self.board.get_ppg_channels(self.board_id)

                # self.board.config_board("p61")
                self.eeg_channels = self.board.get_eeg_channels(self.board_id)
                self.sampling_rate = self.board.get_sampling_rate(self.board_id)
                self.timestamp_channel = self.board.get_timestamp_channel(self.board_id)
                # depending on the model

                # metadata
                self.metadata = {
                    'board_id': self.board_id,
                    'eeg_channels': self.eeg_channels,
                    'sampling_rate': self.sampling_rate,
                }
                if "accel_channels" in self.board_descr.keys():
                    self.metadata['accel_channels'] = self.board.get_accel_channels(self.board_id)
                if "ppg_channels" in self.board_descr.keys():
                    self.metadata['ppg_channels'] = self.board.get_ppg_channels(self.board_id)

                # print(self.metadata)

                print("Headset connected successfully!")
                self.data_ids = []
                self.processed_data = []
                break  # Exit loop if connection is successful

            except KeyboardInterrupt:
                print("Interrupted by user. Disconnecting...")
                self.disconnect()
                break

            except Exception as e:
                print(f"Failed to connect on attempt {attempt + 1}. Press the power button once.")
                if self.board is not None:
                    self.board.release_session()
                time.sleep(delay)
                attempt += 1
                if attempt == retries:
                    self.board = None  # Reset the board if all retries fail
                    raise e  #

    def disconnect(self):
        if self.board is not None and self.board.is_prepared():
            print("Releasing session...")
            self.board.release_session()
            self.board = None

    def stop_streaming(self):
        if self.board is None:
            raise Exception("Board not connected!")
        print("Stopping data streaming...")
        self.board.stop_stream()
        self.disconnect()

    async def data_acquisition_loop(self, stream_duration, buffer_duration, service):
        if self.board is None:
            raise Exception("Board not connected!")
        
        buffer_size_samples = int(self.sampling_rate * buffer_duration)  # 256 * 5 = 1280
        total_iterations = 1 + math.ceil((stream_duration - buffer_duration) / buffer_duration) # 1440
        self.board.start_stream(buffer_size_samples) # 7200 * 256 = 1843200

        iter_counter = 0
        try:
            while total_iterations > iter_counter: # 1440

                # time.sleep(buffer_duration) # had to reintroduce, otherwise the buffers are empty

                data = self.board.get_current_board_data(buffer_size_samples) 

                eeg_data =   data[self.eeg_channels, :]
                timestamps = data[self.timestamp_channel, :]
                if "accel_channels" in self.board_descr:
                    accel_data = data[ self.metadata['accel_channels'], :]
                if "ppg_channels" in self.board_descr:
                    ppg_data = data[ self.metadata['ppg_channels'], :]

                if data.shape[1] >= buffer_size_samples: # Start processing only when the buffer is full
                    # print(eeg_data.tolist())
                    data_id, proc_data = service(metadata=self.metadata, data=eeg_data.tolist(), timestamps=timestamps.tolist())
                    # print(proc_data)
                    self.processed_data.append( proc_data )
                    self.data_ids.append( data_id )
                    #await callback(proc_data)
                    iter_counter += 1  

        except KeyboardInterrupt:
            print("KeyboardInterrupt detected.")
            self.stop_streaming()
            
        finally:
            self.stop_streaming()
