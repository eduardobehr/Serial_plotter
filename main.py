#! /usr/bin/python
# -*- coding: utf-8 -*-
"""
SERIAL FORMAT (separation by white space. Only integers):
'variable1 123\n'
'variable2 31415\n'
"""

from pyqtgraph.Qt import QtGui, QtCore
from typing import Union, Tuple, List
import numpy as np
import pyqtgraph as pg
import time, re, os
import serial
from serial import EIGHTBITS, SEVENBITS, PARITY_NONE, PARITY_ODD, PARITY_EVEN, STOPBITS_ONE, STOPBITS_TWO, \
    SerialException, SerialTimeoutException
from serial.tools.list_ports import main as list_ports
from serial.tools.list_ports import comports
from ctypes import c_float

# FIXME: When more signals are sent, the plotter interleaves them switching to zero (like a saw tooth wave)
#   It happens because the buffer index is global and increments with the update of each var, leaving the other at zero
# FIXME: sometimes, the plot freezes on start, although the data is being received
#   The above happens when the serial is caught in the middle of a transaction, and the string gets currupted!
#   Check if the value is correct?
#   Alternative: if the variable is not updated after N sweeps, remove it from the plot!

# WARNING: Qt's "emit" rejects type 'float'. Therefore, values must be 'int'

# TODO: JOIN Threads! Secondary thread keeps running despite KeyboardInterrupt
# GUI Thread should wait for ALL the variables to be updated
# Constants configuration:
DEBUG = True
DEBUG_NOISE = True
DATA_BUFFER_LENGTH = 1100
PRINT_PARSED_DATA = False
UPDATE_PERIOD = 10  # milliseconds
VARIABLES_LIMIT = 1
ANTIALIASING = True

# Port selection prompt
available_ports = [p[0] for p in comports()]
N_PORTS = len(available_ports)

class Variable:
    """ Object stores an array with all the values to be plotted
     Creation: 20/03/2021
    """
    instances = dict()
    n_instances = 0
    colors = "yrgb"  # possible colors to plot
    color = colors[len(instances)]

    # def create_var(self, name, init_value):
    #     if name not in Variable.instances:
    #         Variable(name, init_value)
    #     else:
    #         if DEBUG:
    #             print()

    def __init__(self, name, init_value):
        """ WARNING: do not call this method! """
        self.name = name
        self.last_value = init_value
        self.instances.update({self.name: self})
        self.index = 0  # integer index of the buffer
        self.id = Variable.n_instances
        self.updated = False
        self.buffer = np.zeros(DATA_BUFFER_LENGTH, float)
        self.new_value(self.last_value)
        self.color = Variable.colors[self.id%len(Variable.instances)]
        self.curve = plot_window.plot(pen=self.color)
        self.last_time_updated = 0

        Variable.n_instances += 1

    def __repr__(self):
        return f"{self.name} -> (color={self.color}, last_var={self.last_value})"

    def _increment_index(self):
        self.index = (self.index + 1) % DATA_BUFFER_LENGTH
        self.updated = False

    def new_value(self, value):
        self.last_value = value
        self.buffer[self.index] = self.last_value
        self.updated = True
        self.last_time_updated = time.time()
        self._increment_index()

    def up_to_date(self, time_limit=5):
        """ Tests if the variable was recently updated """
        return time.time() - self.last_time_updated < time_limit



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
x = np.linspace(0,DATA_BUFFER_LENGTH*UPDATE_PERIOD/1000, DATA_BUFFER_LENGTH)
iter = 0
# data = np.random.normal(size=(variations_example,data_length))

# TODO: add legend!
# legend = pg.LegendItem((80,60), offset=(70,20))
# # legend.setParentItem()
# legend.addItem(data, 'bar')
# win.addItem(legend)

variables = dict()  # {"var": (ndarray, plot), ...}
updated_variables = []  # [True, False, ...]. Informs whether the variables were updated
# variables.update({"_time": x})

def data_update_slot(name, value):
    """
    Receives parameters from SerialParser's signal and updates data
    :param name: str
    :param value: float
    :return:
    """
    # t = QtCore.QTime.currentTime()
    # print(f"Signal received!{t}")
    global variables, updated_variables

    # if value >= 0:  # ADC reads no negative value. TODO: allow any real value
    if True:

        #### BEGIN BRANCH 20/03/2021 #############
        if name not in Variable.instances:
            Variable(name=name, init_value=value)
        else:
            Variable.instances[name].new_value(value)

        if DEBUG: print(Variable.instances)

        #### END BRANCH 20/03/2021 #############

        # checks if there is a new variable from serial
        # if name not in variables and len(variables) <= VARIABLES_LIMIT:
        #     colors = "yrgb"
        #     color = colors[len(variables)]
        #
        #     updated_variables.append(False)
        #     # creates a new ndarray for the new variable
        #     variables.update(
        #         {
        #             name:
        #                 [
        #                     np.zeros(DATA_BUFFER_LENGTH, float),
        #                     plot_window.plot(pen=color),
        #                     False  # updated value state
        #                 ]
        #
        #
        #         }
        #     )
        # if name in variables:
        #     variables[name][0][iter] = value
        #     variables[name][2] = True
            # if DEBUG: print(f"Value assigned! {value} passed to variable {name}")
        # y[iter] = value
        # x[iter] = time.time()-t0
    else:
        # y[iter] = 0
        pass
    # if DEBUG: print(name, value)

    pass

plot_window.enableAutoRange('xy', True)
def update(name, value):
    global iter, curve2, variables, told, x, updated_variables
    # resets 'updated' state
    # for i in enumerate(updated_variables):
    #     updated_variables[i] = False

    data_update_slot(name, value)  # Updates the global arrays x and the ones in variables

    #### BEGIN BRANCH 20/03/2021  ############
    for var in Variable.instances.values(): # gets the objects of Variable
        if var.up_to_date(time_limit=2):
            var.curve.setData(x, var.buffer)
        else:
            # if the variable wasn't updated in the last couple of seconds, clear it out of the plot
            if var.curve:
                var.curve.clear()
        ...
    #### END BRANCH 20/03/2021  ############


# TODO: instead of timer, use event driven approach. I.e, update only when new data reachs the data_update_slot!
timer = QtCore.QTimer()
# event = QtCore.QEvent()
# event.
told = time.time()
# timer.timeout.connect(update)
# timer.start(UPDATE_PERIOD)


class SerialParser(QtCore.QThread):
    signal = QtCore.pyqtSignal(str, int, name="serial2plot")
    def __init__(self):
        super(SerialParser, self).__init__()
        self.serial_connect()
        self.variables = []
        self.signal.connect(update)

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

        self.signal.emit(_name, int(_value)) # FIXME: emit requires type 'int', so perhaps float can't be reliably passed
        # TODO: release lock and allow main thread to proceed
        return

    def parse_line(self) -> Tuple[str, int]:
        """
        Reads a \\n terminated line from serial port and returns the variable and its value
        Note: only one variable-value pair allowed
        :return: var_name (str)
        :return: var_value (float)
        """
        line = []
        var_name = ""
        var_value = -1
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
            line[1] = re.sub("[^0-9.-]", "", line[1])  # removes everything that is not numeric
            #if DEBUG:
                #print("raw value is: ", line[1], '+ noise')

            try:
                var_value = int(line[1])
                if DEBUG_NOISE and DEBUG:
                    # var_value += np.random.choice([0,10,20,30])
                    var_value += 10*np.random.randn()
            except ValueError as err:
                print(err.args[0])

        return var_name, var_value


# TODO: add automatic port identification (i.e. serial keeps changing from 0 through 2)
parser = SerialParser()
# parser.start()





## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        parser.start()
        QtGui.QApplication.instance().exec_()
        # QtGui.QGuiApplication.thread().wait()
