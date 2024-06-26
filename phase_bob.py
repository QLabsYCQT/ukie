from yqcinst.instruments.epc04 import EPC04, Channel as EPC04Channel, DeviceMode as EPCDeviceMode
from yqcinst.instruments.keithley2231a import Keithley2231A, DeviceMode as KeithleyDeviceMode
from ukie_core.polopt import KoheronPowerPolarisationOptimiser as KPolOpt
from ukie_core.koheronDetector import koheronDetector
from ukie_core.remote_instrument import remote_instrument
from ukie_core.utils import load_config
import questionary
import nidaqmx
import numpy as np
import time
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

RemoteEPC04 = remote_instrument(EPC04, 'epc')
RemoteEPC04Channel1 = remote_instrument(EPC04Channel, 'epc_ch1')
RemoteEPC04Channel2 = remote_instrument(EPC04Channel, 'epc_ch2')
RemoteEPC04Channel3 = remote_instrument(EPC04Channel, 'epc_ch3')
RemoteEPC04Channel4 = remote_instrument(EPC04Channel, 'epc_ch4')
RemoteKeithley = remote_instrument(Keithley2231A, 'keithley')


def initialise():
    config = load_config()
    remote_keithley = RemoteKeithley(**config['server'])
    remote_keithley.mode = KeithleyDeviceMode.REMOTE_LOCK
    remote_keithley.enabled = [True, True, True]
    local_epc = EPC04(config['epc']['address'])
    local_epc.device_mode = EPCDeviceMode.DC
    remote_epc = RemoteEPC04(**config['server'])
    remote_epc.device_mode = EPCDeviceMode.DC


def align_local():
    config = load_config()
    remote_keithley = RemoteKeithley(**config['server'])
    local_epc = EPC04(config['epc']['address'])

    config = config['alignment']['phase']
    remote_keithley.voltage = config['EVOA voltages']['local']

    
    koheron = koheronDetector()

    po = KPolOpt(
        target_voltage=config['polopt']['target_voltage']['local'],
        epc=local_epc,
        detector=koheron,
    )

    po.initialisation()
    po.gradient_search()
    remote_keithley.voltage = [0, 0, 0]


def align_remote():
    config = load_config()
    remote_keithley = RemoteKeithley(**config['server'])
    remote_epc = RemoteEPC04(**config['server'])
    remote_epc.channels = [
        RemoteEPC04Channel1(**config['server']),
        RemoteEPC04Channel2(**config['server']),
        RemoteEPC04Channel3(**config['server']),
        RemoteEPC04Channel4(**config['server'])
    ]
    
    config = config['alignment']['phase']
    remote_keithley.voltage = config['EVOA voltages']['remote']

    po = KPolOpt(
        target_voltage=config['polopt']['target_voltage']['remote'],
        epc=remote_epc,
        detector=koheronDetector(),
    )

    po.initialisation()
    po.gradient_search()
    remote_keithley.voltage = [0, 0, 0]


def monitor_power():
    config = load_config()['acquisition']['phase']
    voltage_min, voltage_max = config['voltage limits']

    fig, ax = plt.subplots(1, 1)
    ai0 = Line2D([], [], color='blue', label='ai0')
    ai1 = Line2D([], [], color='orange', label='ai1')
    ax.add_line(ai0)
    ax.add_line(ai1)
    ax.set_xlabel('time / s')
    ax.set_ylabel('voltage / V')
    ax.set_xlim(0, 10)
    ax.set_ylim(voltage_min, voltage_max)
    ax.legend(loc='upper right')

    with nidaqmx.Task('Read PD1') as task:
        task.ai_channels.add_ai_voltage_chan(
            'Dev1/ai0',
            min_val=voltage_min,
            max_val=voltage_max)
        task.ai_channels.add_ai_voltage_chan(
            'Dev1/ai1',
            min_val=voltage_min,
            max_val=voltage_max)
        task.timing.cfg_samp_clk_timing(
            2_000,
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
        stream = task.in_stream
        reader = nidaqmx.stream_readers.AnalogMultiChannelReader(stream)
        task.start()
        data = np.zeros((2, 200))
        history = np.zeros((2, 20_000))
        t = np.linspace(0, 10, 20_000)
        fig.canvas.draw()
        try:
            while True:
                reader.read_many_sample(
                    data,
                    200,
                    timeout=nidaqmx.constants.WAIT_INFINITELY)
                history = np.roll(history, 200, axis=1)
                history[:,:200] = data
                ai0.set_data(t, history[0])
                ai1.set_data(t, history[1])
                fig.canvas.draw()
                plt.pause(0.01)
        except KeyboardInterrupt:
            task.stop()


def acquire_data():
    with nidaqmx.Task('Read PD1') as task:
        task.ai_channels.add_ai_voltage_chan(
            'Dev1/ai0',
            min_val=0,
            max_val=5)
        task.ai_channels.add_ai_voltage_chan(
            'Dev1/ai1',
            min_val=0,
            max_val=5)
        task.timing.cfg_samp_clk_timing(
            2_000_000,
            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
            samps_per_chan=32_000_000)
        stream = task.in_stream
        reader = nidaqmx.stream_readers.AnalogMultiChannelReader(stream)
        task.start()
        data = np.zeros((2, 32_000_000))
        reader.read_many_sample(
            data,
            nidaqmx.constants.READ_ALL_AVAILABLE,
            timeout=nidaqmx.constants.WAIT_INFINITELY)
        task.stop()
        filename = f'phase-acquisition-{time.time()}'
        np.save(filename, data)


def quit():
    raise KeyboardInterrupt


processes = {
    'local EPC alignment': align_local,
    'remote EPC alignment': align_remote,
    'monitor detectors': monitor_power,
    'data acquisition': acquire_data,
    'quit': quit
}


menu = questionary.select(
    'Please choose a process to run: ',
    choices=list(processes.keys())
)

try:
    print('Initialising...', end='\r')
    initialise()
    print('Initialised!   ')
    while True:
        process = menu.ask()
        try:
            processes[process]()
        except Exception as e:
            print(f'An exception occured whilst executing process {process}:')
            print(f'{repr(e)}')
except KeyboardInterrupt:
    pass
