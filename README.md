# RAW_IMU_EMG App

This application collects and processes raw EMG and IMU data during activities. The app interfaces with a sensor device to read EMG signals, apply filtering, and calculate outputs for visualization and storage.

## Nodes Required: 2 

**Sensing (2):**  
- **EMG Sensor** (attached to skin on target muscle)

- **IMU Sensor** (attached to the body or equipment)

## Algorithm Information

The raw EMG data from the sensor undergoes a series of filtering steps:

1. **Bandpass Filtering:** Removes unwanted low- and high-frequency noise based on specified frequency bounds.
2. **Notch Filtering:** Removes power line interference (50 or 60 Hz).
3. **RMS Envelope Calculation:** Calculates the root-mean-square (RMS) envelope using a moving average approach.

### Processed Data Variables
- `raw_data`: Original unprocessed EMG data.
- `bandpassed_data`: EMG after bandpass filtering.
- `notched_data`: EMG after notch filtering.
- `envelope_data`: Final processed RMS envelope of EMG.

## User Configurable Settings

- **Band Filter Settings:**  
  - **Low Cut Frequency:** Default 10 Hz  
  - **High Cut Frequency:** Default 100 Hz  
  - **Notch Filter Frequency:** Selectable (50 or 60 Hz)

- **Save Options:**  
  - **Output File Format:** CSV, H5, XLSX

These settings directly influence data processing and output storage.

## Data Output

### Saved and Calculated Fields
- **Time (s):** Time elapsed since the start of collection.
- **Raw_EMG (mV):** Unprocessed EMG sensor data.
- **Bandpass_Filter (mV):** EMG data after bandpass filter.
- **Notch_Filter (mV):** EMG data after notch filter.
- **RMS_Envelope (mV):** RMS envelope of the filtered EMG.

Data is recorded at 500Hz and streamed at 100Hz for visualization.

### IMU Data (if applicable)
- **AccelX/Y/Z (m/s²):** Raw acceleration data from the IMU sensor.
- **GyroX/Y/Z (°/s):** Raw gyroscope data from the IMU sensor.
- **MagX/Y/Z (μT):** Raw magnetometer data from the IMU sensor.
- **Quat1/2/3/4:** Quaternion data for sensor orientation.
- **Sampletime:** Timestamp for each sensor data point.
- **Package:** The package number associated with the sensor data.

## Development and Processing Loop

- The main application logic continuously acquires and processes data.
- Processed data is sent to the SageMotion platform for logging and real-time visualization.

For additional development resources, refer to the [SageMotion Documentation page](http://docs.sagemotion.com/).
