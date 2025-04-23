# EMG Reader Module: Handles real-time EMG data acquisition and filtering

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

import numpy as np
import time
import threading
from collections import deque
from scipy.signal import butter, filtfilt, iirnotch

from emg_sensor import iFocus

# Updated Constants Section for sample rate pairs
DEFAULT_FS_EEG_HIGH = 500         # High sampling rate for EEG in Hz
DEFAULT_FS_IMU_HIGH = 100          # High sampling rate for IMU in Hz
DEFAULT_FS_EEG_LOW = 250           # Low sampling rate for EEG in Hz
DEFAULT_FS_IMU_LOW = 50            # Low sampling rate for IMU in Hz
DEFAULT_LOW_CUT = 10.0           # Default low cutoff frequency in Hz for bandpass filter
DEFAULT_HIGH_CUT = 100.0         # Default high cutoff frequency in Hz for bandpass filter
DEFAULT_NOTCH = 50.0             # Default notch frequency in Hz for notch filter
FILTER_ORDER = 4                 # Filter order for Butterworth filter
QUALITY_FACTOR = 30.0            # Quality factor for notch filter
DEFAULT_WINDOW_DURATION = 0.2    # Duration in seconds used to compute the window size

class EMGFilter:
    # Applies filtering operations to raw EMG data.
    def __init__(self, fs, window_size, low_cut=DEFAULT_LOW_CUT, high_cut=DEFAULT_HIGH_CUT, notch=DEFAULT_NOTCH):
        # Initialize filter parameters and outputs.
        self.fs = fs
        self.window_size = window_size
        self.lowcut = low_cut
        self.highcut = high_cut
        self.notch_freq = notch
        self.quality_factor = QUALITY_FACTOR
        
        # Containers for storing data at different processing stages.
        self.raw_data = []
        self.bandpassed_data = []
        self.notched_data = []
        self.envelope_data = []

    def bandpass_filter(self, data):
        """Apply bandpass filter to the data with Nyquist normalized to one."""
        # Calculate normalized cutoff frequencies (Nyquist is 1)
        low_norm = 2 * self.lowcut / self.fs
        high_norm = 2 * self.highcut / self.fs
        b, a = butter(FILTER_ORDER, [low_norm, high_norm], btype='band')
        return filtfilt(b, a, data)

    def notch_filter(self, data):
        """Apply notch filter to remove power line noise with normalized frequency."""
        # Calculate normalized notch frequency (Nyquist is 1)
        freq_norm = 2 * self.notch_freq / self.fs
        b, a = iirnotch(freq_norm, self.quality_factor)
        return filtfilt(b, a, data)

    def compute_rms_envelope(self, data):
        """Compute RMS envelope of the signal."""
        rect = np.abs(data)
        return np.sqrt(np.convolve(rect**2, 
                                 np.ones(self.window_size)/self.window_size, 
                                 mode='same'))

    def process_data(self, raw_data):
        """Process the EMG data through filtering stages."""
        self.raw_data = raw_data
        
        # Apply bandpass filtering.
        self.bandpassed_data = self.bandpass_filter(raw_data)
        
        # Remove power line noise using notch filtering.
        self.notched_data = self.notch_filter(self.bandpassed_data)
        
        # Compute the RMS envelope of the filtered signal.
        self.envelope_data = self.compute_rms_envelope(self.notched_data)

class EMGReader:
    def __init__(self, low_cut=DEFAULT_LOW_CUT, high_cut=DEFAULT_HIGH_CUT, notch=DEFAULT_NOTCH, sample_rate_variant="high"):
        # Set sampling frequencies for data acquisition based on sample_rate_variant ("high" uses 500/100, "low" uses 250/50)
        if sample_rate_variant == "low":
            fs_eeg = DEFAULT_FS_EEG_LOW
            fs_imu = DEFAULT_FS_IMU_LOW
        else:
            fs_eeg = DEFAULT_FS_EEG_HIGH
            fs_imu = DEFAULT_FS_IMU_HIGH
        iFocus.dev_args.update({"fs_eeg": fs_eeg, "fs_imu": fs_imu})
        
        # Connect to the first available device.
        self.device = iFocus()
        self.device_port = self.device.dev_args['name']
        
        self.fs = self.device.dev_args['fs_eeg']
        self.lowcut = low_cut
        self.highcut = high_cut
        
        # Compute window size using the DEFAULT_WINDOW_DURATION constant.
        self.window_size = int(self.fs * DEFAULT_WINDOW_DURATION)
        self.filter = EMGFilter(self.fs, self.window_size, low_cut, high_cut, notch)
        self.recent_points = deque(maxlen=self.window_size)
        
        self.samples_per_packet = 5
        self.running = False
        self.read_thread = None

    def start_reading(self):
        # Begin data acquisition if not already started.
        if self.running:
            return
        self.running = True
        self.device.start_acquisition_data()
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("EMG data acquisition started")
        
    def _read_loop(self):
        # Continuously fetch and process data frames from the device.
        while self.running:
            frames = self.device.get_data(timeout=0.1)
            if not frames:
                time.sleep(0.01)
                continue
            for frame in frames:
                if not frame:
                    continue
                # Extract EMG channel values from the frame.
                emg_values = [sample[0] for sample in frame[:self.samples_per_packet]]
                for val in emg_values:
                    self.recent_points.append(val)
                    # Process data only when sufficient samples have been collected.
                    if len(self.recent_points) >= self.window_size:
                        self._process_emg_data()
        print("EMG reading thread exiting")
        
    def stop_reading(self):
        # Stop acquisition, clean up thread resources, and close device connection.
        if not self.running:
            return
        self.running = False
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=2.0)
        self.device.stop_acquisition()
        self.device.close_dev()
        self.recent_points.clear()
        print("EMG reader stopped")
        
    def _process_emg_data(self):
        # Process the collected data if it meets the window size requirement.
        if len(self.recent_points) < self.window_size:
            return
        
        arr = np.array(list(self.recent_points))
        self.filter.process_data(arr)

    @property
    def last_raw_emg(self):
        # Provide access to the last raw EMG samples.
        return list(self.recent_points)
    
    @property
    def last_filtered_emg(self):
        # Provide access to the final filtered (RMS envelope) data.
        data = self.filter.envelope_data
        return data.tolist() if hasattr(data, "tolist") else data
    
    @property
    def last_rms_envelope_emg(self):
        # Alias for last_filtered_emg.
        return self.last_filtered_emg

    @property
    def last_bandpassed_emg(self):
        # Provide access to the bandpass filtered data.
        data = self.filter.bandpassed_data
        return data.tolist() if hasattr(data, "tolist") else data

    @property
    def last_notched_emg(self):
        # Provide access to the notch filtered data.
        data = self.filter.notched_data
        return data.tolist() if hasattr(data, "tolist") else data

    @property
    def last_emg(self):
        # Combine all processed EMG outputs in a single dictionary.
        return {
            "raw": list(self.recent_points),
            "bandpass": self.last_bandpassed_emg,
            "notch": self.last_notched_emg,
            "envelope": self.last_filtered_emg
        }

    def __del__(self):
        # Ensure resources are released when the object is destroyed.
        self.stop_reading()

