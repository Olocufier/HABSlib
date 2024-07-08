from brainflow.board_shim import BoardShim
from brainflow.board_shim import BrainFlowInputParams
from brainflow.board_shim import BoardIds
from brainflow.board_shim import BrainFlowPresets
from brainflow.data_filter import DataFilter

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

    def __init__( self, enable_logger, board_id="SYNTHETIC", serial_number="MuseS-88D1", extra=None ):
        if not hasattr(self, 'initialized'):  # Prevent re-initialization
            self.board = None
            self.preset = None
            self.board_descr = None
            self.extra_board = None
            self.params = BrainFlowInputParams()

            # Board Id
            if board_id == "MUSE_2":
                self.board_id = BoardIds.MUSE_2_BOARD
            elif board_id == "MUSE_S":
                self.board_id = BoardIds.MUSE_S_BOARD.value
                self.preset = BrainFlowPresets.ANCILLARY_PRESET
            else:
                self.board_id = BoardIds.SYNTHETIC_BOARD
                self.extra_board = extra # Extra Board parameters

            # Serial Number
            self.params.serial_number = serial_number
            if self.board_id == BoardIds.SYNTHETIC_BOARD:
                self.params.serial_number = ""

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
                self.board.config_board("p52") # or p50 - both give the same result for some reason - need further exploration.

                self.eeg_channels = self.board.get_eeg_channels(self.board_id)
                self.sampling_rate = self.board.get_sampling_rate(self.board_id)
                self.timestamp_channel = self.board.get_timestamp_channel(self.board_id)
                # depending on the model
                if self.board_id == BoardIds.MUSE_S_BOARD.value:
                    # self.gyro_channels = self.board.get_gyro_channels(self.board_id), self.preset
                    # self.accel_channels = self.board.get_accel_channels(self.board_id, self.preset)
                    self.ppg_channels = self.board.get_ppg_channels(self.board_id, self.preset)

                # metadata
                self.metadata = {
                    'board_id': self.board_id,
                    'eeg_channels': self.eeg_channels,
                    'sampling_rate': self.sampling_rate,
                }
                if self.board_id == BoardIds.MUSE_S_BOARD.value:
                    self.metadata['ppg_channels'] = self.ppg_channels

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
        print("\nStopping data streaming...")
        self.board.stop_stream()
        self.disconnect()

    async def data_acquisition_loop(self, stream_duration, buffer_duration, service, user_id, callback=None):
        if self.board is None:
            raise Exception("Board not connected!")
        
        buffer_size_samples = int(self.sampling_rate * buffer_duration)
        total_iterations = 1 + math.ceil((stream_duration - buffer_duration) / buffer_duration)
        self.board.start_stream(buffer_size_samples)

        iter_counter = 0
        t_ref = None
        try:
            while total_iterations > iter_counter:

                data = self.board.get_current_board_data(buffer_size_samples) 

                # Start processing only when the buffer is full
                if data.shape[1] >= buffer_size_samples: 

                    # for extra board params
                    if self.board_id is BoardIds.SYNTHETIC_BOARD and self.extra_board is not None:
                        extra_data = self.generate_dummy_eeg_data(self.extra_board, buffer_duration)
                        data[:extra_data.shape[0], :] = extra_data

                    eeg_data =   data[self.eeg_channels, :]
                    timestamps = data[self.timestamp_channel, :]
                    ppg_ir = np.array([])
                    ppg_red = np.array([])

                    t_current = timestamps[0]
                    if t_ref is None:
                        t_ref = timestamps[0]

                    # Board-dependent data
                    if self.board_id == BoardIds.MUSE_S_BOARD.value:
                        ppg_ir = data[ self.ppg_channels[1] ]
                        ppg_red = data[ self.ppg_channels[0] ] 
                        # if len(ppg_red)>1024 and len(ppg_ir)>1024: # minimum required for functions
                        #     oxygen_level = DataFilter.get_oxygen_level(ppg_ir, ppg_red, self.sampling_rate)
                        #     # print("oxygen_level: ", oxygen_level)
                        #     heart_rate = DataFilter.get_heart_rate(ppg_ir, ppg_red, self.sampling_rate, 1024) 
                        #     # print("heart_rate:",heart_rate)

                    if t_current >= t_ref + buffer_duration:
                        data_id, proc_data = service(
                            metadata=self.metadata, 
                            data=eeg_data.tolist(), 
                            timestamps=timestamps.tolist(), 
                            user_id=user_id,
                            ppg_red=ppg_red.tolist(), 
                            ppg_ir=ppg_ir.tolist()
                        )
                        self.processed_data.append( proc_data )
                        self.data_ids.append( data_id )
                        if callback:
                            callback( proc_data )
                        # next itaration
                        t_ref = t_current
                        iter_counter += 1  

        except KeyboardInterrupt:
            print("KeyboardInterrupt detected.")
            self.stop_streaming()
            
        finally:
            self.stop_streaming()


    def generate_dummy_eeg_data(self, params, buffer_duration):
        # Extract parameters from JSON dictionary
        num_channels = params.get("eeg_channels", 8)
        samples_per_second = params.get("sampling_rate", 256)
        epoch_period = buffer_duration
        noise_level = params.get("noise", 1)
        artifact_prob = params.get("artifacts", 0.01)
        modulation_type = params.get("modulation_type", 'sinusoidal')
        preset = params.get("preset", None)
        sequence = params.get("sequence", None)
        correlation_strength = params.get("correlation_strength", 0.5)  # Strength of correlation between nearby channels
        power_law_slope = params.get("power_law_slope", 1.0)

        # Preset amplitude settings
        preset_settings = {
            #           del  the  alp  bet  gam
            'focus':   [0.1, 0.1, 0.5, 0.8, 0.4],
            'alert':   [0.1, 0.1, 0.4, 0.9, 0.3],
            'relaxed': [0.2, 0.2, 0.7, 0.3, 0.2],
            'drowsy':  [0.4, 0.6, 0.2, 0.2, 0.1],
        }

        if preset in preset_settings:
            delta_amp, theta_amp, alpha_amp, beta_amp, gamma_amp = preset_settings[preset]
        else:
            delta_amp = params.get("delta_amp", 0.1)
            theta_amp = params.get("theta_amp", 0.1)
            alpha_amp = params.get("alpha_amp", 0.1)
            beta_amp = params.get("beta_amp", 0.1)
            gamma_amp = params.get("gamma_amp", 0.1)
        
        total_samples = samples_per_second * epoch_period
        t = np.linspace(0, epoch_period, total_samples, endpoint=False)
        eeg_data = np.zeros((num_channels, total_samples))

        # Frequency bands
        bands = {
            'Delta': (0.5, 4),
            'Theta': (4, 8),
            'Alpha': (8, 13),
            'Beta': (13, 30),
            'Gamma': (30, 100)
        }

        amplitudes = {
            'Delta': delta_amp,
            'Theta': theta_amp,
            'Alpha': alpha_amp,
            'Beta': beta_amp,
            'Gamma': gamma_amp
        }

        # Managing the type of EEG modulation
        if modulation_type == 'sinusoidal':
            modulating_freq = 0.1  # frequency of the amplitude modulation
            delta_mod = (1 + np.sin(2 * np.pi * modulating_freq * t)) / 2  # between 0.5 and 1.5
            theta_mod = (1 + np.cos(2 * np.pi * modulating_freq * t)) / 2
            alpha_mod = (1 + np.sin(2 * np.pi * modulating_freq * t + np.pi / 4)) / 2
            beta_mod = (1 + np.cos(2 * np.pi * modulating_freq * t + np.pi / 4)) / 2
            gamma_mod = (1 + np.sin(2 * np.pi * modulating_freq * t + np.pi / 2)) / 2
        elif modulation_type == 'random':
            delta_mod = np.abs(np.random.randn(total_samples))
            theta_mod = np.abs(np.random.randn(total_samples))
            alpha_mod = np.abs(np.random.randn(total_samples))
            beta_mod = np.abs(np.random.randn(total_samples))
            gamma_mod = np.abs(np.random.randn(total_samples))
        
        for band, (low, high) in bands.items():
            amplitude = amplitudes[band]
            freqs = np.linspace(low, high, int(samples_per_second / 2))
            power_law = freqs ** -power_law_slope

            for i in range(num_channels):
                for f, p in zip(freqs, power_law):
                    phase = np.random.uniform(0, 2 * np.pi)
                    if band == 'Delta':
                        eeg_data[i] += amplitude * p * delta_mod * np.sin(2 * np.pi * f * t + phase)
                    elif band == 'Theta':
                        eeg_data[i] += amplitude * p * theta_mod * np.sin(2 * np.pi * f * t + phase)
                    elif band == 'Alpha':
                        eeg_data[i] += amplitude * p * alpha_mod * np.sin(2 * np.pi * f * t + phase)
                    elif band == 'Beta':
                        eeg_data[i] += amplitude * p * beta_mod * np.sin(2 * np.pi * f * t + phase)
                    elif band == 'Gamma':
                        eeg_data[i] += amplitude * p * gamma_mod * np.sin(2 * np.pi * f * t + phase)

        # Adding random noise
        eeg_data += noise_level * np.random.randn(num_channels, total_samples)

        # Introducing correlation between nearby channels
        for channel in range(1, num_channels):
            eeg_data[channel] += correlation_strength * eeg_data[channel - 1]

        # Introducing artifacts as random peaks
        artifact_indices = np.random.choice(total_samples, int(artifact_prob * total_samples), replace=False)
        for channel in range(0, num_channels):
            eeg_data[channel, artifact_indices] -= np.random.uniform(10, 20, len(artifact_indices))

        # Handle sequence if provided
        if sequence:
            full_data = []
            for seq in sequence:
                preset, duration = seq
                temp_params = params.copy()
                temp_params['preset'] = preset
                temp_params['epoch_period'] = duration
                temp_params['sequence'] = None
                segment = generate_dummy_eeg_data(temp_params)
                full_data.append(segment)
            eeg_data = np.hstack(full_data)

        return eeg_data
