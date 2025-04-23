import os
import sys
import threading
import time

from sage.base_app import BaseApp

current_dir = os.path.dirname(os.path.abspath(__file__))
if (current_dir not in sys.path):
    sys.path.append(current_dir)

try:
    from .emg_reader import EMGReader
except ImportError:
    from emg_reader import EMGReader


class Core(BaseApp):
    def __init__(self, my_sage):
        super().__init__(my_sage, __file__)
        self.iteration = 0
        # Initialize start_time to None. It will be set on the first run_in_loop call.
        self.start_time = None  

        try:
            self.emg_reader = EMGReader(
                low_cut=self.config.get("low_cut"),
                high_cut=self.config.get("high_cut"),
                notch=60 if self.config.get("notch") == "60 hz" else 50
            )
        except Exception as e:
            print(f"Error initializing EMG reader: {e}")
            self.emg_reader = None

        self.emg_raw = []
        self.emg_filtered = []

        self.send_raw_emg = 0.0
        self.send_bandpassed_emg = 0.0
        self.send_notched_emg = 0.0
        self.send_rms_envelope_emg = 0.0

        print("Core initialized")

    def on_start_event(self, _):
        if not self.emg_reader:
            raise Exception("EMG sensor not connected. Please connect the EMG sensor to run the app.")

        self.emg_thread = threading.Thread(target=self.emg_reader.start_reading)
        self.emg_thread.start()

        print("EMG reading thread started")

    def run_in_loop(self):
        data = self.my_sage.get_next_data()
        
        if self.start_time is None:
            self.start_time = time.time()
            time_now = 0  
        else:
            time_now = time.time() - self.start_time

        # Get EMG data from reader
        signals = self.emg_reader.last_emg
        raw_emg_full = signals["raw"]
        bandpassed_emg_full = signals["bandpass"]
        notched_emg_full = signals["notch"]
        rms_envelope_emg_full = signals["envelope"]

        # Retrieve datarates and calculate samples per imu tick
        emg_datarate = self.info["emg_datarate"]
        imu_datarate = self.info["imu_datarate"]
        n_samples = int(emg_datarate / imu_datarate) if imu_datarate else 1

        # Helper function to get the last n samples from a list.
        def get_last_samples(lst):
            return lst[-n_samples:] if len(lst) >= n_samples else lst

        raw_emg_samples = get_last_samples(raw_emg_full)
        bandpassed_emg_samples = get_last_samples(bandpassed_emg_full)
        notched_emg_samples = get_last_samples(notched_emg_full)
        rms_envelope_emg_samples = get_last_samples(rms_envelope_emg_full)

        num_samples = len(raw_emg_samples)

        # Save data at EMG datarate by sending all samples
        for idx in range(num_samples):
            # Distribute sample times evenly over the IMU tick interval.
            sample_time = time_now + (idx * (1 / imu_datarate) / n_samples)
            my_data = {
                "Time(s)": [sample_time],
                "Raw_EMG(mV)": [raw_emg_samples[idx]],
                "Bandpass_Filter(mV)": [bandpassed_emg_samples[idx]],
                "Notch_Filter(mV)": [notched_emg_samples[idx]],
                "RMS_Envelope(mV)": [rms_envelope_emg_samples[idx]]
            }
            try:
                self.my_sage.save_data(data, my_data)
            except Exception as e:
                print(f"Error saving data: {e}")

        # Send stream data at IMU datarate using only the latest sample
        if num_samples:
            sample_time = time_now + ((num_samples - 1) * (1 / imu_datarate) / n_samples)
            my_data = {
                "Time(s)": [sample_time],
                "Raw_EMG(mV)": [raw_emg_samples[-1]],
                "Bandpass_Filter(mV)": [bandpassed_emg_samples[-1]],
                "Notch_Filter(mV)": [notched_emg_samples[-1]],
                "RMS_Envelope(mV)": [rms_envelope_emg_samples[-1]]
            }
            self.my_sage.send_stream_data(data, my_data)

        self.iteration += 1

        return True

    def on_stop_event(self, _):
        # Stop EMG reader
        if hasattr(self, 'emg_reader') and self.emg_reader:
            try:
                print("Stopping EMG reader...")
                self.emg_reader.stop_reading()

                # Wait for thread with timeout only if it exists and is alive
                if (hasattr(self, 'emg_thread') and self.emg_thread
                        and self.emg_thread.is_alive()):
                    try:
                        self.emg_thread.join(timeout=5.0)
                        if self.emg_thread.is_alive():
                            print("Warning: EMG thread did not terminate normally")
                    except Exception as e:
                        print(f"Error during thread cleanup: {e}")
            except Exception as e:
                print(f"Error during EMG reader cleanup: {e}")
            finally:
                self.emg_thread = None
                self.emg_reader = None

        # Clear data
        self.emg_raw = []
        self.emg_filtered = []

        print("All resources cleaned up")

