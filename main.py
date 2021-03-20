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

from serial.tools.list_ports import comports

# TODO: JOIN Threads!? Secondary thread keeps running despite KeyboardInterrupt
# GUI Thread should wait for ALL the variables to be updated

# TODO: compile to Cython to improve performance!?

# TODO: make the code more pythonic (organize in classes and modules)

# TODO: move constants to new config file
# Constants configuration:
DEBUG = False
DATA_BUFFER_LENGTH = 200
CURVES_LIFETIME = 5  # [s] time to keep curve with no new data update, after which it's removed
# UPDATE_PERIOD = 10  # milliseconds
ANTIALIASING = False

# Port selection prompt
available_ports = [p[0] for p in comports()]
N_PORTS = len(available_ports)

class Variable:
    """ Object stores an array with all the values to be plotted
     Creation: 20/03/2021
    """
    instances = dict()
    n_instances = 0
    colors = "ygcbmr"  # possible colors cycle around in the plot "ygcbmr"

    def __init__(self, name, init_value):
        self.last_time_updated = 0
        self.name = name
        self.last_value = init_value
        self.instances.update({self.name: self})
        self.index = 0  # integer index of the buffer
        self.id = Variable.n_instances  # unique id (hopefully)
        self.updated = False
        self.buffer = np.zeros(DATA_BUFFER_LENGTH, float)
        self.new_value(self.last_value)

        self.color = Variable.colors[self.id%len(Variable.colors)]

        self.curve = plot_window.plot(pen=self.color)
        legend.addItem(self.curve, self.name)
        self.has_legend = True



        Variable.n_instances += 1

    def __repr__(self):
        return f"{self.name} -> (color={self.color}, last_var={self.last_value}, id={self.id})"

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

# TODO: add legend!
legend = pg.LegendItem((80,60), offset=(70,20))
legend.setParentItem(plot_window)
# legend.addItem(data, 'bar')


# x = np.linspace(0,DATA_BUFFER_LENGTH*UPDATE_PERIOD/1000, DATA_BUFFER_LENGTH)  # TODO: make timing precise
x = np.linspace(0,DATA_BUFFER_LENGTH-1, DATA_BUFFER_LENGTH)
iter = 0
# data = np.random.normal(size=(variations_example,data_length))



variables = dict()  # {"var": (ndarray, plot), ...}
updated_variables = []  # [True, False, ...]. Informs whether the variables were updated
# variables.update({"_time": x})

def data_update_slot(name, value):
    """
    :param name: str
    :param value: float
    :return:
    """
    # t = QtCore.QTime.currentTime()
    # print(f"Signal received!{t}")
    global variables, updated_variables

    #### BEGIN BRANCH 20/03/2021 #############
    if name not in Variable.instances:
        Variable(name=name, init_value=value)
    elif isinstance(value, float):
        Variable.instances[name].new_value(value)

    if DEBUG: print(Variable.instances)

    #### END BRANCH 20/03/2021 #############
    pass

plot_window.enableAutoRange('xy', True)

def update(name, value):
    """
    Receives parameters from SerialParser's signal and updates data
    :param name: str
    :param value: float
    :return:
    """
    global iter, curve2, variables, told, x, updated_variables, mutex, legend

    try:
        value = float(value)
    except ValueError as err:
        if DEBUG:
            print(err.args[0])
            print(f"Warning: {value} failed to be converted to float and was not caught")
            # TODO: do something to catch 'value'

    data_update_slot(name, value)  # Updates the global arrays x and the ones in variables

    #### BEGIN BRANCH 20/03/2021  ############
    mutex.lock()  # locks other thread until this part is processed
    for var in Variable.instances.values(): # gets the objects of Variable
        if var.up_to_date(time_limit=CURVES_LIFETIME):
            var.curve.setData(x, var.buffer)
            if not var.has_legend:
                legend.addItem(var.curve, var.name)
                var.has_legend = True
        else:
            # if the variable wasn't updated in the last couple of seconds, clear it out of the plot
            if var.curve:
                if var.has_legend:
                    # remove cleared data curve from the legend as well
                    legend.removeItem(var.name)
                    var.has_legend = False
                var.curve.clear()

                # print("DELETED CURVE: ", var.name)

    mutex.unlock()  # unlocks other thread
    #### END BRANCH 20/03/2021  ############


told = time.time()


class SerialParser(QtCore.QThread):
    signal = QtCore.pyqtSignal(str, str, name="serial2plot")
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

        self.signal.emit(_name, _value) # FIXME: emit requires type 'int', so perhaps float can't be reliably passed
        return

    def parse_line(self) -> Tuple[str, str]:
        """
        Reads a \\n terminated line from serial port and returns the variable and its value
        Note: only one variable-value pair allowed
        :return: var_name (str)
        :return: var_value (float)
        """
        line = []
        var_name = ""
        var_value = "-1"
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

            # try:
            var_value = line[1]
                # if DEBUG_NOISE and DEBUG:
                    # var_value += np.random.choice([0,10,20,30])
            #         var_value += 10*np.random.randn()
            # except ValueError as err:
            #     print(err.args[0])

        return var_name, var_value


parser = SerialParser()
mutex = QtCore.QMutex()


if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        try:
            parser.start()
            # QtGui.QApplication.instance().exec_()
            app.exec_()
        except KeyboardInterrupt:
            parser.terminate()
            app.exit(-1)
        # QtGui.QGuiApplication.thread().wait()
