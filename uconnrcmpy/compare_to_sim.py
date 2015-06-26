"""
Compare simulated pressure trace to the corresponding reactive trace
"""

# System imports
from glob import glob

# Third-party imports
import numpy as np
import matplotlib.pyplot as plt
import yaml
from cansen.profiles import VolumeProfile
import cantera as ct

# Local imports
from .pressure_traces import SimulatedPressureTrace
from .utilities import copy


class Simulation(object):
    """Class for simulations of experiments."""

    def __init__(self, is_reactive):
        self.keywords = {}
        self.time = []
        self.temp = []
        self.pres = []
        self.volm = []
        self.load_yaml()
        self.is_reactive = is_reactive
        self.setup_simulation(self.is_reactive)
        self.run_simulation()
        self.process_simulation()

    def load_yaml(self):
        with open('volume-trace.yml') as yaml_file:
            yaml_data = yaml.load(yaml_file)
            self.comptime = yaml_data['comptime']

    def load_volume_trace(self, filename='volume.csv'):
        """
        Load the volume trace from the file and put it in the proper
        format for `CanSen.profiles.VolumeProfile`.
        """
        data = np.genfromtxt(filename, delimiter=',')
        self.keywords['vproTime'] = data[:, 0]
        self.keywords['vproVol'] = data[:, 1]

    def append_to_data_arrays(self):
        self.time.append(self.netw.time)
        self.temp.append(self.reac.T)
        self.pres.append(self.gas.P/1E5)
        self.volm.append(self.reac.volume)

    def setup_simulation(self, is_reactive=True):
        self.gas = ct.Solution('species.cti')
        if not is_reactive:
            self.gas.set_multiplier(0)
        self.reac = ct.IdealGasReactor(self.gas)
        env = ct.Reservoir(ct.Solution('air.xml'))
        self.load_volume_trace()
        ct.Wall(self.reac, env, A=1.0, velocity=VolumeProfile(self.keywords))
        self.netw = ct.ReactorNet([self.reac])
        self.netw.set_max_time_step(self.keywords['vproTime'][1])
        self.append_to_data_arrays()

    def run_simulation(self, end_Temp=2000, end_time=0.2):
        while self.reac.T < end_Temp and self.netw.time < end_time:
            self.netw.step(1)
            self.append_to_data_arrays()

    def process_simulation(self):
        self.pressure_trace = self.create_pressure_trace()
        self.time = np.array(self.time)
        self.temp = np.array(self.temp)
        self.pres = np.array(self.pres)
        self.volm = np.array(self.volm)

    def create_pressure_trace(self):
        pres_trace = np.core.records.fromarrays(
            np.vstack((self.time, self.pres)),
            names='Time_(sec), Pressure_(bar)',
            formats='f8, f8',
        )
        self.pressure_trace = SimulatedPressureTrace(data=pres_trace)


def compare_to_sim():
    """
    Compare a reactive pressure trace to the corresponding simulation.

    This function conducts non-reactive and reactive simulations of a
    given experimental case. It relies on the `volume.csv` file
    generated from the `uconnrcmpy.volume_trace.VolumeTraceBuilder`
    class. It compares the simulated pressure traces to the pressure
    trace generated by the same class in the text file with the name
    ending in `pressure.txt`. After the comparison, it copies the
    simulated ignition delay or the EOC temperature to the clipboard.
    """

    nonreactive_sim = Simulation(is_reactive=False)
    reactive_sim = Simulation(is_reactive=True)

    # Load the experimental pressure trace. Try the glob function first
    # and if it fails, ask the user for help.
    flist = glob('*pressure.txt')
    if not len(flist) == 1:
        flist = [input('Input the experimental pressure trace file name: ')]
    expdata = np.genfromtxt(flist[0])
    exptime = expdata[:, 0]
    exppressure = expdata[:, 1]

    # Plot the pressure traces together
    fig = plt.figure('Simulation Comparison')
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(exptime, exppressure)
    ax.plot(nonreactive_sim.time, nonreactive_sim.pres)
    ax.plot(reactive_sim.time, reactive_sim.pres)
    m = plt.get_current_fig_manager()
    m.window.showMaximized()

    # Compute the temperature at the end of compression and the
    # ignition delay from the corresponding simulated case. Copy
    # them to the clipboard.
    T_EOC = np.amax(nonreactive_sim.temp)
    ign_delay = (reactive_sim.time[np.argmax(reactive_sim.dpdt)]*1000 -
                 reactive_sim.comptime)
    print('{:.0f}, {:.6f}'.format(T_EOC, ign_delay))
    copy('{}\t\t\t{}'.format(T_EOC, ign_delay))
