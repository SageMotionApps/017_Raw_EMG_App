def parse_packet(packet: bytes) -> dict:
    """
    Expects a packet containing 15 bytes of EMG data (5 channels, 3 bytes each)
    followed by IMU data. Returns a dict with keys 'emg' and 'imu'.
    """
    if len(packet) < 15:
        raise ValueError("Incomplete packet: less than 15 bytes")
    emg_bytes = packet[:15]
    emg_values = []
    import struct
    for i in range(5):
        start = i * 3
        val = int.from_bytes(emg_bytes[start:start+3], byteorder="little", signed=False)
        if val & 0x00800000:  # sign extension if needed
            val |= 0xFF000000
            val = struct.unpack("<i", val.to_bytes(4, "little"))[0]
        # Conversion factor as in EMGReader
        emg_values.append(val * 0.0240405)
    imu_data = packet[15:]  # ignore IMU processing; optionally validate length
    return {"emg": emg_values, "imu": imu_data}
