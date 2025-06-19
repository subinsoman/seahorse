import os
from threading import Event
import json
import traceback
import logging

from jupyter_client import MultiKernelManager
from jupyter_client.kernelspec import KernelSpecManager

from rabbit_mq_client import RabbitMQClient, RabbitMQJsonReceiver, RabbitMQJsonSender
from utils import setup_logging
import argparse
import signal

from executing_kernel_client import ExecutingKernelClient, ExecutingKernelClientSettings


class ExecutingKernelManager:
    """
    This is the class implementing the main process on the remote host.

    Its role is to manage the lifecycle of all ExecutingKernels, in particular
    start them and shut them down.
    """

    EXCHANGE = 'remote_notebook_kernel'
    ALL_MANAGEMENT_SUBSCRIPTION_TOPIC = 'management.{session_id}.*.to_manager'

    SX_EXCHANGE = 'seahorse'
    SX_PUBLISHING_TOPIC = 'kernelmanager.{session_id}.{workflow_id}.from'

    PYTHON_EXECUTING_KERNEL_NAME = 'PythonExecutingKernel'
    R_EXECUTING_KERNEL_NAME = 'RExecutingKernel'

    def __init__(self, gateway_address, r_backend_address,
                 rabbit_mq_address, rabbit_mq_credentials,
                 session_id, workflow_id, kernels_source_dir,
                 py_executing_kernel_source_dir,
                 r_executing_kernel_source_dir):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initializing ExecutingKernelManager")

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self.executing_kernel_clients = {}

        self._kernels_source_dir = kernels_source_dir
        self._py_executing_kernel_source_dir = py_executing_kernel_source_dir
        self._r_executing_kernel_source_dir = r_executing_kernel_source_dir
        self._gateway_address = gateway_address
        self._r_backend_address = r_backend_address
        self._rabbit_mq_address = rabbit_mq_address
        self._rabbit_mq_credentials = rabbit_mq_credentials
        self._session_id = session_id
        self._workflow_id = workflow_id

        self._shutdown_event = Event()
        self._multi_kernel_manager = self._init_kernel_manager()
        self._rabbit_listener = self._init_rabbit_client()
        self._sx_sender = RabbitMQJsonSender(
            rabbit_mq_client=RabbitMQClient(address=self._rabbit_mq_address,
                                            credentials=self._rabbit_mq_credentials,
                                            exchange=self.SX_EXCHANGE),
            topic=self.SX_PUBLISHING_TOPIC.format(session_id=self._session_id,
                                                  workflow_id=self._workflow_id))
        
        self.logger.info("ExecutingKernelManager initialized successfully")

    def run(self):
        try:
            self.logger.info('Starting ExecutingKernelManager')
            self._rabbit_listener.subscribe(
                topic=self.ALL_MANAGEMENT_SUBSCRIPTION_TOPIC.format(session_id=self._session_id),
                handler=self._handle_management_message)

            # Send ready notification
            self._sx_sender.send({
                'messageType': 'kernelManagerReady',
                'messageBody': {}
            })
            self.logger.info('Sent kernelManagerReady notification')
            
            while not self._shutdown_event.is_set():
                if os.getppid() == 1:
                    self.logger.warning("Process is an orphan - stopping")
                    self.stop()
                self._shutdown_event.wait(1)

            self.logger.info('Shutting down kernels')
            self._multi_kernel_manager.shutdown_all(now=True)
            self.logger.info('ExecutingKernelManager stopped')
        except Exception as e:
            self.logger.error("An error occurred in run: %s", str(e))
            self.logger.error(traceback.format_exc())
            self.stop()

    def stop(self):
        self.logger.info("Stopping ExecutingKernelManager")
        self._shutdown_event.set()

    def exit_gracefully(self, signum, frame):
        self.logger.info("Received signal %s. Exiting gracefully.", signum)
        self.stop()

    def _handle_management_message(self, message):
        try:
            self.logger.info('Received management message: %s', message)
            known_message_types = ['start_kernel', 'shutdown_kernel']
            if not isinstance(message, dict) or 'type' not in message or message['type'] not in known_message_types:
                self.logger.warning('Unknown message type: %s', message)
                return

            if message['type'] == 'start_kernel':
                dataframe_source = message['dataframe_source']
                dataframe_storage_type = dataframe_source['dataframe_storage_type']
                node_id = dataframe_source['node_id']
                port_number = dataframe_source['port_number']
                kernel_name = message['kernel_name']
                self.start_kernel(kernel_id=message['kernel_id'],
                                  signature_key=message['signature_key'],
                                  node_id=node_id,
                                  port_number=port_number,
                                  kernel_name=kernel_name,
                                  dataframe_storage_type=dataframe_storage_type)

            elif message['type'] == 'shutdown_kernel':
                self.shutdown_kernel(kernel_id=message['kernel_id'])
        except Exception as e:
            self.logger.error("An error occurred in _handle_management_message: %s", str(e))
            self.logger.error(traceback.format_exc())

    def start_kernel(self, kernel_id, signature_key, node_id, port_number, kernel_name, dataframe_storage_type):
        try:
            self.logger.info('Starting kernel: %s, kernel_name: %s', kernel_id, kernel_name)

            if kernel_id in self._multi_kernel_manager.list_kernel_ids():
                self.logger.info('Kernel %s already exists. Shutting down before restart.', kernel_id)
                self._multi_kernel_manager.shutdown_kernel(kernel_id, now=True)

            def with_replaced_key(real_factory):
                def hacked_factory(**kwargs):
                    km = real_factory(**kwargs)
                    km.session.key = signature_key.encode('utf-8') if isinstance(signature_key, str) else signature_key
                    return km
                return hacked_factory

            self._multi_kernel_manager.kernel_manager_factory = with_replaced_key(
                self._multi_kernel_manager.kernel_manager_factory)
            
            self._multi_kernel_manager.start_kernel(kernel_name=kernel_name, kernel_id=kernel_id)
            self.logger.info('Kernel started: %s', kernel_id)
            
            settings = ExecutingKernelClientSettings(self._gateway_address, self._r_backend_address,
                                                     self._rabbit_mq_address,
                                                     self._rabbit_mq_credentials, self._session_id,
                                                     self._workflow_id, node_id, port_number, dataframe_storage_type)
            
            self.logger.debug('Creating ExecutingKernelClient for kernel_id: %s', kernel_id)
            executing_kernel_client = ExecutingKernelClient(kernel_id, signature_key, settings)
            executing_kernel_client.start()
            self.logger.info('ExecutingKernelClient started for kernel_id: %s', kernel_id)
            
            self.executing_kernel_clients[kernel_id] = executing_kernel_client
        except Exception as e:
            self.logger.error("An error occurred in start_kernel: %s", str(e))
            self.logger.error(traceback.format_exc())

    def shutdown_kernel(self, kernel_id):
        try:
            self.logger.info('Shutting down kernel: %s', kernel_id)
            self._multi_kernel_manager.shutdown_kernel(kernel_id=kernel_id)
            self.executing_kernel_clients.pop(kernel_id, None)
            self.logger.info('Kernel %s shut down successfully', kernel_id)
        except Exception as e:
            self.logger.error("An error occurred in shutdown_kernel: %s", str(e))
            self.logger.error(traceback.format_exc())

    def _init_rabbit_client(self):
        self.logger.info("Initializing RabbitMQ client")
        rabbit_client = RabbitMQClient(address=self._rabbit_mq_address,
                                       credentials=self._rabbit_mq_credentials,
                                       exchange=self.EXCHANGE)
        return RabbitMQJsonReceiver(rabbit_client)

    def _init_kernel_manager(self):
        self.logger.info("Initializing MultiKernelManager")
        mkm = MultiKernelManager()
        mkm.log_level = 'DEBUG'
        mkm.kernel_spec_manager = KernelSpecManager()
        mkm.kernel_spec_manager.kernel_dirs.append(
          os.path.join(self._kernels_source_dir, 'share', 'jupyter', 'kernels'))
        
        self.logger.info("Installing %s", self.PYTHON_EXECUTING_KERNEL_NAME)
        mkm.kernel_spec_manager.install_kernel_spec(source_dir=self._py_executing_kernel_source_dir,
                                                    kernel_name=self.PYTHON_EXECUTING_KERNEL_NAME,
                                                    prefix=self._kernels_source_dir)

        self.logger.info("Installing %s", self.R_EXECUTING_KERNEL_NAME)
        mkm.kernel_spec_manager.install_kernel_spec(source_dir=self._r_executing_kernel_source_dir,
                                                    kernel_name=self.R_EXECUTING_KERNEL_NAME,
                                                    prefix=self._kernels_source_dir)
        return mkm


if __name__ == '__main__':
    try:
        setup_logging(os.path.join(os.getcwd(), 'executing_kernel_manager.log'))
        logger = logging.getLogger(__name__)
        logger.info("Starting ExecutingKernelManager script")

        parser = argparse.ArgumentParser()
        parser.add_argument('--gateway-host', action='store', dest='gateway_host')
        parser.add_argument('--gateway-port', action='store', dest='gateway_port')
        parser.add_argument('--r-backend-host', action='store', dest='r_backend_host')
        parser.add_argument('--r-backend-port', action='store', dest='r_backend_port')
        parser.add_argument('--mq-host', action='store', dest='mq_host')
        parser.add_argument('--mq-port', action='store', dest='mq_port')
        parser.add_argument('--mq-user', action='store', dest='mq_user')
        parser.add_argument('--mq-pass', action='store', dest='mq_pass')
        parser.add_argument('--session-id',  action='store', dest='session_id')
        parser.add_argument('--workflow-id', action='store', dest='workflow_id')
        args = parser.parse_args()

        gateway_address = (args.gateway_host, int(args.gateway_port))
        r_backend_address = (args.r_backend_host, int(args.r_backend_port))
        mq_address = (args.mq_host, int(args.mq_port))
        mq_credentials = (args.mq_user, args.mq_pass)

        kernels_source_dir = os.path.join(os.getcwd(), 'executing_kernels')
        py_kernel_source_dir = os.path.join(kernels_source_dir, 'python')
        r_kernel_source_dir = os.path.join(kernels_source_dir, 'r')

        logger.info("Initializing ExecutingKernelManager")
        ekm = ExecutingKernelManager(gateway_address, r_backend_address,
                                     mq_address, mq_credentials,
                                     args.session_id, args.workflow_id,
                                     kernels_source_dir=kernels_source_dir,
                                     py_executing_kernel_source_dir=py_kernel_source_dir,
                                     r_executing_kernel_source_dir=r_kernel_source_dir)
        logger.info("Starting ExecutingKernelManager")
        ekm.run()
    except Exception as e:
        logger.error("An error occurred in main: %s", str(e))
        logger.error(traceback.format_exc())