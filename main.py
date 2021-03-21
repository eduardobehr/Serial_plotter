#! /usr/bin/python
# -*- coding: utf-8 -*-
""" Serial Plotter: a convenient and simple microcontroller debugger
Make sure to check if the needed parameters in the config.py file are what you want
SERIAL FORMAT (separation by white space, each data in its own line!):
'variable1 123\n'
'variable2 3.1415\n'
"""

from serial import SerialException, SerialTimeoutException
from serial.tools.list_ports import comports
from pyqtgraph.Qt import QtGui, QtCore
from typing import Union, Tuple
import pyqtgraph as pg
from config import *
import numpy as np
import serial
import time
import re
import os

__author__ = "Eduardo Eller Behr (eduardobehr @ Github)"
__license__ = "GPL"
__version__ = "3.0"


# TODO: make the code more pythonic (organize in classes and modules)
# TODO: document! (docstrings)
# TODO: move constants to new config file
# TODO: JOIN Threads!? Secondary thread keeps running despite KeyboardInterrupt
#   GUI Thread should wait for ALL the variables to be updated
# TODO: compile to Cython to improve performance!?


class Variable:
    """
    Stores information about the variables to be plotted (data array, name, color,legend and curve object, etc)
    """
    instances = dict()
    n_instances = 0
    colors = "ygcbmr"  # possible colors cycle around in the plot "ygcbmr"

    def __init__(self, name: str, init_value: Union[float, int], application: "App"):
        """
        :param name: Name of the variable to appear on the legend
        :param init_value: First numeric value to store in the data buffer array
        :param application: application object that runs the GUI
        """
        self.last_time_updated = 0
        self.name = name
        self.last_value = init_value
        self.instances.update({self.name: self})
        self.index = 0  # integer index of the buffer
        self.id = Variable.n_instances  # unique id (hopefully)
        self.updated = False
        self.buffer = np.zeros(DATA_BUFFER_LENGTH, float)
        self.new_value(self.last_value)
        self.app = application
        self.color = Variable.colors[self.id % len(Variable.colors)]
        self.curve = self.app.plot_window.plot(pen=self.color)
        self.app.legend.addItem(self.curve, self.name)
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


# Serial setup
#   Port selection prompt
available_ports = [p[0] for p in comports()]
N_PORTS = len(available_ports)


def display_ports():
    for i, port in enumerate(available_ports):
        print("\t", i, port)


def port_selection_prompt() -> Union[None, str]:
    """
    Prompts the user to select the desired port to read from, if multiple are available.
    If none is available, exit program.
    If only one is available, automatically select it and proceed
    :return: Union[None, str]
    """
    # display ports:

    if N_PORTS == 0:
        print("No ports found! Exiting...")
        exit()
        return None

    elif N_PORTS == 1:
        PORT = available_ports[0]
        print(f"Connecting to {PORT}")
        return PORT

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
        return PORT


class SerialParser(QtCore.QThread):
    signal = QtCore.pyqtSignal(str, str, name="serial2plot")

    def __init__(self):
        super(SerialParser, self).__init__()
        self.serial = None
        self.port = port_selection_prompt()
        self.serial_connect()
        self.variables = []
        self.t0 = time.time()

    def qt_connect_signal_to_slot(self, slot_function):
        self.signal.connect(slot_function)

    def serial_connect(self):
        while True:
            try:
                self.serial = serial.Serial(port=self.port, baudrate=BAUDRATE,
                                            bytesize=BYTESIZE, parity=PARITY, stopbits=STOPBITS)
                break
            except SerialException:
                # Connection attempt failed. Wait some time and retry...
                print(f"Connection failed. Retrying at {self.port} {time.time()-self.t0}")
                time.sleep(0.5)

    def run(self) -> None:
        # sleep_time = 0#0.1*UPDATE_PERIOD/1000
        while True:
            name, value = self.parse_line()
            self.send_to_main_thread(name, value)
            # time.sleep(sleep_time)

    def send_to_main_thread(self, _name, _value):
        self.signal.emit(_name, _value)  # FIXME: emit requires type 'int', so perhaps float can't be reliably passed
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
            self.serial.close()
            self.serial_connect()
        except UnicodeDecodeError as err:
            print("Unicode Decode Error:", err.args)

        if len(line) > 1:
            var_name = line[0]
            var_value = re.sub("[^0-9.-]", "", line[1])  # removes everything that is not numeric

        return var_name, var_value


# Setup application
class App(QtGui.QApplication):
    def __init__(self, serial_parser):
        QtGui.QApplication.__init__(self, [])  # Qt requires another argument, but doesn't know the reference...
        self.win = pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
        self.win.resize(1000, 600)
        self.win.setWindowTitle('Serial Plotter')
        pg.setConfigOptions(antialias=ANTIALIASING)
        self.plot_window = self.win.addPlot(title=f"Real time scanning of port {serial_parser.port}")
        self.plot_window.enableAutoRange('xy', True)
        self.legend = pg.LegendItem((80, 60), offset=(70, 20))
        self.legend.setParentItem(self.plot_window)
        # x = np.linspace(0,DATA_BUFFER_LENGTH*UPDATE_PERIOD/1000, DATA_BUFFER_LENGTH)  # TODO: make timing precise
        self.x = np.linspace(0, DATA_BUFFER_LENGTH-1, DATA_BUFFER_LENGTH)
        self.iter = 0

    def data_update_slot(self, name: str, value: float):
        """
        :param name: name of the variable received from serial (before the white space)
        :param value: value of the variable, as float, received from serial (after the white space)
        :return:
        """

        if name not in Variable.instances:
            Variable(name=name, init_value=value, application=self)
        elif isinstance(value, float):
            Variable.instances[name].new_value(value)

        if DEBUG:
            print(Variable.instances)

    def update(self, name: str, value: str):
        """
        Receives parameters from SerialParser's signal and updates data
        :param name: name of the variable received from serial (before the white space)
        :param value: value of the variable, as str, received from serial (after the white space)
        Note: 'value' must be str so that Qt won't make a fuss about it
        """
        # global iter, curve2, variables, told, x, updated_variables, mutex, legend

        try:
            value = float(value)
        except ValueError as err:
            if DEBUG:
                print(err.args[0])
                print(f"Warning: {value} failed to be converted to float and was not caught")
                # TODO: do something to catch 'value'

        self.data_update_slot(name, value)  # Updates the global arrays x and the ones in variables

        mutex.lock()  # locks other thread until this part is processed
        for var in Variable.instances.values():  # gets the objects of Variable
            if var.up_to_date(time_limit=CURVES_LIFETIME):
                var.curve.setData(self.x, var.buffer)
                if not var.has_legend:
                    self.legend.addItem(var.curve, var.name)
                    var.has_legend = True
            else:
                # if the variable wasn't updated in the last couple of seconds, clear it out of the plot
                if var.curve:
                    if var.has_legend:
                        # remove cleared data curve from the legend as well
                        self.legend.removeItem(var.name)
                        var.has_legend = False
                    var.curve.clear()

                    # print("DELETED CURVE: ", var.name)
        mutex.unlock()  # unlocks other thread


if __name__ == '__main__':
    parser = SerialParser()
    mutex = QtCore.QMutex()
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        app = App(parser)
        parser.qt_connect_signal_to_slot(app.update)
        try:
            parser.start()

            app.exec_()
        except KeyboardInterrupt:
            parser.terminate()
            app.exit(-1)
