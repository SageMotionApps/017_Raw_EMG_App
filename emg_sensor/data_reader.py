import time
import queue
from queue import Queue
from threading import Thread
from typing import Optional
from enum import Enum
from copy import deepcopy

from .iFocusParser import Parser
from .emg_sock import sock


class iFocus(Thread):
    class Dev(Enum):
        SIGNAL = 10
        SIGNAL_START = 11
        IDLE = 30
        IDLE_START = 31
        TERMINATE = 40
        TERMINATE_START = 41

    dev_args = {
        "type": "iFocus",
        "fs_eeg": 500,
        "fs_imu": 100,
        "channel_eeg": {0: "CH0", 1: "CH1", 2: "CH2", 3: "CH3", 4: "CH4"},
        "channel_imu": {0: "X", 1: "Y", 2: "Z"},
        "AdapterInfo": "Serial Port",
    }

    def __init__(self, port: Optional[str] = None) -> None:
        """
        Args:
            port: if not given, connect to the first available device.
        """
        super().__init__(daemon=True)
        self.__status = iFocus.Dev.TERMINATE
        if port is None:
            port = iFocus.find_devs()[0]
        self.__save_data = Queue()
        self.__parser = Parser()
        self.dev_args = deepcopy(iFocus.dev_args)
        self.dev = sock(port)
        self.set_frequency()
        self.__with_q = True
        self.__socket_flag = "Device not connected, please connect first."
        self.__bdf_flag = False
        
        try:
            self.dev.connect_socket()
        except Exception as e:
            try:
                self.dev.close_socket()
            finally:
                raise e
        self.__status = iFocus.Dev.IDLE_START
        self.__socket_flag = None
        self._bdf_file = None
        self.__enable_imu = False
        self.dev_args["name"] = port
        self.start()

    def set_frequency(self, fs_eeg: int = None):
        """
        Change the sampling frequency of iFocus.

        Args:
            fs_eeg: sampling frequency of eeg data, should be 250 or 500,
                fs_imu will be automatically set to 1/5 of fs_eeg.

        Raises:
            ValueError: if fs_eeg is not 250 or 500.
            NotImplementedError: device firmware too old, not supporting 500Hz.
        """
        if self.__status == iFocus.Dev.SIGNAL:
            raise Exception("Data acquisition already started, please stop first.")
        if fs_eeg is None:
            fs_eeg = self.dev_args["fs_eeg"]
        if fs_eeg not in [250, 500]:
            raise ValueError("fs_eeg should be 250 or 500")
        self.dev_args["fs_eeg"] = fs_eeg
        fs_imu = fs_eeg // 5
        self.dev_args["fs_imu"] = fs_imu
        if hasattr(self, "dev"):
            self.dev.set_frequency(fs_eeg)

    def get_dev_info(self) -> dict:
        """
        Get current device information, including device name, hardware channel number, acquired channels, sample frequency, etc.
        """
        return deepcopy(self.dev_args)

    @staticmethod
    def find_devs() -> list:
        """
        Find available iFocus devices.
        """
        return sock._find_devs()

    def get_data(self, timeout: Optional[float] = 0.02) -> Optional[list[Optional[list]]]:
        """
        Acquire all available data, make sure this function is called in a loop when `with_q` is set to `True` in`start_acquisition_data()`

        Args:
            timeout: Non-negative value, blocks at most 'timeout' seconds and return, if set to `None`, blocks until new data available.

        Returns:
            A list of frames, each frame is made up of 5 eeg data and 1 imu data in a shape as below:
                [[`eeg_0`], [`eeg_1`], [`eeg_2`], [`eeg_3`], [`eeg_4`], [`imu_x`, `imu_y`, `imu_z`]],
                    in which number `0~4` after `_` indicates the time order of channel data.

        Data Unit:
            - eeg: µV
            - imu: degree(°)
        """
        self.__check_dev_status()
        if not self.__with_q:
            return
        try:
            data: list = self.__save_data.get(timeout=timeout)
        except queue.Empty:
            return []
        while not self.__save_data.empty():
            data.extend(self.__save_data.get())
        return data

    def start_acquisition_data(self, with_q: bool = True) -> None:
        """
        Send data acquisition command to device, block until data acquisition started or failed.
        """
        self.__check_dev_status()
        self.__with_q = with_q
        if self.__status == iFocus.Dev.SIGNAL:
            return
        self.__status = iFocus.Dev.SIGNAL_START
        while self.__status not in [iFocus.Dev.SIGNAL, iFocus.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def stop_acquisition(self) -> None:
        """
        Stop data or impedance acquisition, block until data acquisition stopped or failed.
        """
        self.__check_dev_status()
        self.__status = iFocus.Dev.IDLE_START
        while self.__status not in [iFocus.Dev.IDLE, iFocus.Dev.TERMINATE]:
            time.sleep(0.01)
        self.__check_dev_status()

    def setIMUFlag(self, check):
        self.__enable_imu = check

    def close_dev(self):
        """
        Close device connection and release resources.
        """
        if self.__status != iFocus.Dev.TERMINATE:
            # ensure socket is closed correctly
            self.__status = iFocus.Dev.TERMINATE_START
            while self.__status != iFocus.Dev.TERMINATE:
                time.sleep(0.1)
        if self.is_alive():
            self.join()

    def __recv_data(self):
        try:
            self.dev.start_data()
            self.__status = iFocus.Dev.SIGNAL
        except Exception as e:
            print(f"Start data error: {e}")
            self.__socket_flag = f"SIGNAL mode initialization failed: {str(e)}"
            self.__status = iFocus.Dev.TERMINATE_START
            return

        while self.__status in [iFocus.Dev.SIGNAL]:
            try:
                data = self.dev.recv_socket(100)  # Increased buffer size
                if not data:
                    time.sleep(0.01)  # Short sleep to prevent busy waiting
                    continue  # Don't raise exception, just try again
                
                ret = self.__parser.parse_data(data)
                if ret:
                    if self.__with_q:
                        self.__save_data.put(ret)
                    # Only process BDF if flag is enabled
                    if self.__bdf_flag and self._bdf_file:
                        self._bdf_file.write_chunk(ret)
            except Exception as e:
                print(f"Data receive error: {e}")
                self.__socket_flag = f"Data transmission error: {str(e)}"
                self.__status = iFocus.Dev.TERMINATE_START
                break

        # clear buffer
        self.__parser.clear_buffer()
        # Signal end of data stream
        self.__save_data.put(None)
        
        # Clean up queue
        try:
            while not self.__save_data.empty():
                self.__save_data.get_nowait()
        except:
            pass
        
        # stop recv data
        if self.__status != iFocus.Dev.TERMINATE_START:
            try:  # stop data acquisition when thread ended
                self.dev.stop_recv()
            except Exception as e:
                print(f"Stop receive error: {e}")
                if self.__status == iFocus.Dev.IDLE_START:
                    self.__socket_flag = "Connection lost."
                self.__status = iFocus.Dev.TERMINATE_START

    def run(self):
        while self.__status != iFocus.Dev.TERMINATE_START:
            if self.__status == iFocus.Dev.SIGNAL_START:
                self.__recv_data()
            elif self.__status == iFocus.Dev.IDLE_START:
                self.__status = iFocus.Dev.IDLE
                while self.__status == iFocus.Dev.IDLE:
                    time.sleep(0.1)
            else:
                self.__socket_flag = f"Unknown status: {self.__status.name}"
                break
        try:
            self.dev.close_socket()
        finally:
            self.__status = iFocus.Dev.TERMINATE

    def __check_dev_status(self):
        if self.__socket_flag is None:
            return
        if self.is_alive():
            self.close_dev()
        raise Exception(str(self.__socket_flag))
