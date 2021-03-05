# -*- coding: utf-8 -*-
"""
SERIAL FORMAT (separation by white space):
'variable1 123\n'
'variable2 3.141592\n'
"""

from pyqtgraph.Qt import QtGui, QtCore
from typing import Union, Tuple
import numpy as np
import pyqtgraph as pg
import time, re, os
import serial
from serial import EIGHTBITS, SEVENBITS, PARITY_NONE, PARITY_ODD, PARITY_EVEN, STOPBITS_ONE, STOPBITS_TWO, \
    SerialException, SerialTimeoutException
from serial.tools.list_ports import main as list_ports
from serial.tools.list_ports import comports

# Constants configuration:
DEBUG = True
DATA_BUFFER_LENGTH = 100
PRINT_PARSED_DATA = False
UPDATE_PERIOD = 25
VARIABLES_LIMIT = 4
ANTIALIASING = True

# Port selection prompt
available_ports = [p[0] for p in comports()]
N_PORTS = len(available_ports)

def display_ports():
    for i, port in enumerate(available_ports):
        print("\t",i, port)
if N_PORTS == 0:
    print("No ports found! Exiting...")
    exit()
elif N_PORTS == 1:
    PORT = available_ports[0]
    print(f"Connecting to {PORT}")
elif N_PORTS > 1:
    print("Multiple ports found, choose one by its index:")
    display_ports()
    while True:
        chosen_index = input("Choose a port index (q to quit): ")
        if chosen_index.isnumeric() and int(chosen_index) in range(N_PORTS):
            PORT = available_ports[int(chosen_index)]
            break
        elif chosen_index.lower() in ['q', 'quit', 'exit', 'abort', 'suspend', 'cancel']:
            print("Exiting...")
            exit()
        else:
            os.system("clear")
            print("Invalid input!")
            display_ports()
# Serial setup
# PORT = "/dev/ttyUSB0"  # this should be chosen from dropdown (GUI) or argument (CLI)

# if port_connection:
#     PORT = port_connection
# else:
#     PORT = "/dev/ttyUSB0"
BAUDRATE = 115200  # bits per second
BYTESIZE = EIGHTBITS
PARITY = PARITY_NONE
STOPBITS = STOPBITS_ONE


# Setup application
app = QtGui.QApplication([])
win = pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
win.resize(1000,600)
win.setWindowTitle('Serial Plotter')
pg.setConfigOptions(antialias=ANTIALIASING)


t0 = time.time()
plot_window = win.addPlot(title=f"Real time scanning of port {PORT}")

curve = plot_window.plot(pen='y')
# curve2 = plot_window.plot(pen='r')
variations_example = 10
data_length = DATA_BUFFER_LENGTH

# x = np.zeros(DATA_BUFFER_LENGTH, float)
y = np.ones(DATA_BUFFER_LENGTH, float)
x = np.linspace(0,DATA_BUFFER_LENGTH, DATA_BUFFER_LENGTH)
iter = 0
# data = np.random.normal(size=(variations_example,data_length))

# TODO: add legend!
# legend = pg.LegendItem((80,60), offset=(70,20))
# # legend.setParentItem()
# legend.addItem(data, 'bar')
# win.addItem(legend)

variables = dict()  # {"var": (ndarray, plot), ...}
# variables.update({"_time": x})

def data_slot(name, value):
    """
    Receives parameters from SerialParser's signal and updates data
    :param name: str
    :param value: float
    :return:
    """
    # t = QtCore.QTime.currentTime()
    # print(f"Signal received!{t}")
    global variables

    if value is not None:

        if name not in variables and len(variables) <= VARIABLES_LIMIT:
            colors = "yrgb"
            color = colors[len(variables)]
            # creates a new ndarray for the new variable
            variables.update(
                {
                    name:
                        [
                            np.zeros(DATA_BUFFER_LENGTH, float),
                            plot_window.plot(pen=color)
                        ]


                }
            )
        # if name in variables:
        variables[name][0][iter] = value
        y[iter] = value
    else:
        # y[iter] = 0
        pass
    if DEBUG:
        print(name, value)

    pass

plot_window.enableAutoRange('xy', True)
def update():
    global curve, data, plot_window, iter, curve2, variables, told
    tnow = time.time()
    # x[iter] = iter
    # y[iter] = data_slot()
    # curve.setData( data[iter%variations_example])
    # print("Variables:", variables)
    for key, value in variables.items():
        # value == [ndarray, plotitem]
        dat = value[0]

        curv = value[1]
        curv.setData(x, dat)
        # curve2.setData(x,y2)
        # print("DATA: ", dat)
        # print("Curv ", curv)
        pass
    # curve.setData(x, y)

    if iter == 0:
        # plot_window.enableAutoRange('xy', False)  ## stop auto-scaling after the first data set is plotted
        pass

    iter = (iter + 1) % DATA_BUFFER_LENGTH
    if DEBUG:
        dt = tnow-told
        print(f"Sampling rate: {1/dt:.3f} Hz")
        told = tnow

timer = QtCore.QTimer()
told = time.time()
timer.timeout.connect(update)
timer.start(UPDATE_PERIOD)

class SerialParser(QtCore.QThread):
    signal = QtCore.pyqtSignal(str, float, name="serial2plot")
    def __init__(self):
        super(SerialParser, self).__init__()
        self.serial_connect()
        self.variables = []
        self.signal.connect(data_slot)

    def serial_connect(self):
        while True:
            try:
                self.serial = serial.Serial(port=PORT, baudrate=BAUDRATE,
                                            bytesize=BYTESIZE, parity=PARITY, stopbits=STOPBITS)
                break
            except SerialException as exc:
                # Connection attempt failed. Wait some time and retry...

                print(f"Connection failed. Retrying at {PORT} {time.time()-t0}")
                time.sleep(0.5)



    def run(self) -> None:
        # sleep_time = 0#0.1*UPDATE_PERIOD/1000
        while True:
            name, value = self.parse_line()
            self.send_to_main_thread(name, value)
            # time.sleep(sleep_time)

    def send_to_main_thread(self, _name, _value):
        self.signal.emit(_name, _value)
        # TODO: release lock and allow main thread to proceed
        return

    def parse_line(self) -> Tuple[str, float]:
        """
        Reads a \\n terminated line from serial port and returns the variable and its value
        Note: only one variable-value pair allowed
        :return: var_name (str)
        :return: var_value (float)
        """
        # line = []
        # var_name = ""
        var_value = None
        try:
            line = self.serial.readline().strip().decode().split()  # " var 3.14" -> ["var", "3.14"]

        except SerialTimeoutException as exc:
            print("Serial Timeout:", exc.args)
        except SerialException as exc:
            print("Serial Exception:", exc.args)
            # TODO: RETRY CONNECTION AND PROCEED!
            self.serial.close()
            self.serial_connect()
        except UnicodeDecodeError as err:
            print("Unicode Decode Error:", err.args)

        if len(line) > 1:
            var_name = line[0]
            line[1] = re.sub("[^0-9.]", "", line[1])  # removes everything that is not numeric
            if line[1].isnumeric():
                var_value = float(line[1])
            else:
                print(f"Warning: value not found for {var_name}\n")

        return var_name, var_value


# TODO: add automatic port identification (i.e. serial keeps changing from 0 through 2)
parser = SerialParser()
parser.start()




## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()
        # QtGui.QGuiApplication.thread().wait()
