from ukie_core.koheronOptimisation import PolarisationOptimiser
from ukie_core.EPC04 import EPCDriver
from ukie_core.remote_instrument import RemoteEPCDriver
import json
from bullet import Bullet


def load_config(config=None):
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config


def align_local(config):
    local_epc = EPCDriver(EPCAddress='ASRL3::INSTR')
    po = PolarisationOptimiser(config['po_args'], epc=local_epc)
    po.run()


def align_remote(config):
    remote_epc = RemoteEPCDriver(config['hostname'],
                                 config['local_name'],
                                 config['remote_name'])

    po = PolarisationOptimiser(config['po_args'], epc=remote_epc)
    po.epc = remote_epc
    po.run()


def acquire_data(config):
    pass


def quit(config):
    raise KeyboardInterrupt


processes = {
    'load config': load_config,
    'local EPC alignment': align_local,
    'remote EPC alignment': align_remote,
    'data acquisition': acquire_data,
    'quit': quit
}

cli = Bullet(
    prompt='\nPlease choose a process to run: ',
    choices=list(processes.keys()),
    indent=0,
    align=5,
    margin=2,
    shift=0,
    bullet='',
    pad_right=5,
    return_index=True
)


config = load_config()
try:
    while True:
        process = cli.launch()[0]
        try:
            processes[process](config)
        except Exception as e:
            print(f'An exception occured whilst executing process {process}:')
            print(f'{repr(e)}')
except KeyboardInterrupt:
    pass

# NOTE: step 1: establish connection to remote and local EPCs and koherons
# NOTE: step 2: perform polarisation optimisation with Bob's EPC
# NOTE: step 3: perform polarisation optimisation with Alice's EPC
# NOTE: step 4: run acquisition