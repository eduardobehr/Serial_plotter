from serial import EIGHTBITS, SEVENBITS, PARITY_NONE, PARITY_ODD, PARITY_EVEN, STOPBITS_ONE, STOPBITS_TWO

# GUI configuration:
DEBUG = False
DATA_BUFFER_LENGTH = 200
CURVES_LIFETIME = 5  # [s] time to keep curve with no new data update, after which it's removed
# UPDATE_PERIOD = 10  # milliseconds
ANTIALIASING = False


# Serial configuration
BAUDRATE = 115200  # bits per second
BYTESIZE = EIGHTBITS
PARITY = PARITY_NONE
STOPBITS = STOPBITS_ONE