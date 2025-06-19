import os
import base64
import zmq
import json
import traceback

from jupyter_client.session import Session

from rabbit_mq_client import RabbitMQClient, RabbitMQJsonReceiver, RabbitMQJsonSender
from socket_forwarder import SocketForwarder
from utils import Logging


class ExecutingKernelClientSettings(Logging):
    def __init__(self, gateway_address, r_backend_address,
                 rabbit_mq_address, rabbit_mq_credentials,
                 session_id, workflow_id, node_id=None, port_number=None,
                 dataframe_storage_type='input'):
        super().__init__()
        self.logger.info("Initializing ExecutingKernelClientSettings")
        try:
            self._gateway_address = gateway_address
            self._r_backend_address = r_backend_address
            self._rabbit_mq_address = rabbit_mq_address
            self._rabbit_mq_credentials = rabbit_mq_credentials
            self._session_id = session_id
            self._workflow_id = workflow_id
            self._node_id = node_id
            self._port_number = port_number
            self._dataframe_storage_type = dataframe_storage_type
            self.logger.info("ExecutingKernelClientSettings initialized successfully")
        except Exception as e:
            self.logger.error("Error initializing ExecutingKernelClientSettings: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    @property
    def dataframe_source(self):
        self.logger.debug("Accessing dataframe_source property")
        try:
            return self._workflow_id, self._node_id, self._port_number, self._dataframe_storage_type
        except Exception as e:
            self.logger.error("Error accessing dataframe_source property: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    @property
    def gateway_address(self):
        self.logger.debug("Accessing gateway_address property")
        try:
            return self._gateway_address
        except Exception as e:
            self.logger.error("Error accessing gateway_address property: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    @property
    def r_backend_address(self):
        self.logger.debug("Accessing r_backend_address property")
        try:
            return self._r_backend_address
        except Exception as e:
            self.logger.error("Error accessing r_backend_address property: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    @property
    def rabbit_mq_address(self):
        self.logger.debug("Accessing rabbit_mq_address property")
        try:
            return self._rabbit_mq_address
        except Exception as e:
            self.logger.error("Error accessing rabbit_mq_address property: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    @property
    def rabbit_mq_credentials(self):
        self.logger.debug("Accessing rabbit_mq_credentials property")
        try:
            return self._rabbit_mq_credentials
        except Exception as e:
            self.logger.error("Error accessing rabbit_mq_credentials property: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise


class ExecutingKernelClient(Logging):
    EXCHANGE = 'remote_notebook_kernel'
    EXECUTION_PUBLISHING_TOPIC = 'execution.{kernel_id}.from_external'
    EXECUTION_SUBSCRIPTION_TOPIC = 'execution.{kernel_id}.to_external'

    def __init__(self, kernel_id, signature_key, executing_kernel_client_settings):
        super().__init__()
        self.logger.info("Initializing ExecutingKernelClient")
        try:
            self.client_settings = executing_kernel_client_settings
            self.kernel_id = kernel_id
            self.context = zmq.Context()
            self.session = Session(key=signature_key.encode('utf-8'))
            self.subscriber = {}

            self._rabbit_sender_client, self._rabbit_listener = self._init_rabbit_clients()
            self._socket_forwarders = self._init_socket_forwarders()
            self.logger.info("ExecutingKernelClient initialized successfully")
        except Exception as e:
            self.logger.error("Error initializing ExecutingKernelClient: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def start(self):
        self.logger.info("Starting ExecutingKernelClient")
        try:
            self._rabbit_listener.subscribe(
                topic=self.EXECUTION_SUBSCRIPTION_TOPIC.format(kernel_id=self.kernel_id),
                handler=self._handle_execution_message_from_rabbit)

            for forwarder in self._socket_forwarders.values():
                forwarder.start()

            self._init_kernel()
            self.logger.info("ExecutingKernelClient started successfully")
        except Exception as e:
            self.logger.error("Error starting ExecutingKernelClient: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def _init_kernel(self):
        self.logger.info("Initializing kernel")
        try:
            connection_dict = self.get_connection_file_dict()
            kernel_name = connection_dict['kernel_name']
            workflow_id, node_id, port_number, dataframe_storage_type = self.client_settings.dataframe_source
            gateway_host, gateway_port = self.client_settings.gateway_address
            r_backend_host, r_backend_port = self.client_settings.r_backend_address

            # The following work both in Python and R
            self._execute_code('workflow_id = "{}"'.format(workflow_id))
            self._execute_code('node_id = {}'.format(
                '"{}"'.format(node_id) if node_id is not None else None))
            self._execute_code('dataframe_storage_type = "{}"'.format(dataframe_storage_type))
            self._execute_code('port_number = {}'.format(port_number))
            self._execute_code('gateway_address = "{}"'.format(gateway_host))
            self._execute_code('gateway_port = {}'.format(gateway_port))
            self._execute_code('r_backend_host = "{}"'.format(r_backend_host))
            self._execute_code('r_backend_port = {}'.format(r_backend_port))

            if kernel_name == 'PythonExecutingKernel':
                self._execute_file(os.path.join(os.getcwd(), 'executing_kernels/python/kernel_init.py'))
            elif kernel_name == 'RExecutingKernel':
                self._execute_file(os.path.join(os.getcwd(), 'executing_kernels/r/kernel_init.R'))

            self.logger.info("Kernel initialized successfully")
        except Exception as e:
            self.logger.error("Error initializing kernel: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def _send_zmq_forward_to_rabbit(self, stream_name, message):
        self.logger.debug("Sending ZMQ forward to RabbitMQ: %s", stream_name)
        try:
            if not isinstance(message, list):
                raise ValueError('Malformed message')
            
            try:
                self.logger.debug("+++++++++++++++INSIDE  {}{}".format(stream_name,message) )
                body=[base64.b64encode(s).decode('ascii') for s in message]
            except Exception as e:
                self.logger.error("+++++++++++++++ERROR++++++: %s", str(e))
            self.logger.debug("+++++++++++++++BODY  {}{}".format(stream_name,body) )    
            if body is not None:
                self._rabbit_sender_client.send({
                    'type': 'zmq_socket_forward',
                    'stream': stream_name,
                    'body': body
                })
                self.logger.debug("ZMQ forward sent successfully")
        except Exception as e:
            self.logger.error("Error sending ZMQ forward to RabbitMQ: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def _handle_execution_message_from_rabbit(self, message):
        self.logger.debug("Handling execution message from RabbitMQ {}".format(message))
        try:
            known_message_types = ['zmq_socket_forward']
            if not isinstance(message, dict) or 'type' not in message \
                    or message['type'] not in known_message_types:
                raise ValueError('Unknown message: {}'.format(message))

            if message['type'] == 'zmq_socket_forward':
                if 'stream' not in message or 'body' not in message:
                    raise ValueError('Malformed message: {}'.format(message))

                self.logger.debug('Sending to %s', message['stream'])
                body = [base64.b64decode(s) for s in message['body']]
                self._socket_forwarders[message['stream']].forward_to_zmq(body)
            
            self.logger.debug("Execution message handled successfully")
        except Exception as e:
            self.logger.error("Error handling execution message from RabbitMQ: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def _execute_code(self, code):
        self.logger.debug("Executing code: %s", code)
        try:
            content = dict(code=code, silent=True, user_variables=[],
                           user_expressions={}, allow_stdin=False)
            msg = self.session.msg('execute_request', content)
            ser = self.session.serialize(msg)

            self._socket_forwarders['shell'].forward_to_zmq(ser)
            self.logger.debug("Code executed successfully")
        except Exception as e:
            self.logger.error("Error executing code: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def _execute_file(self, filename):
        self.logger.info("Executing file: %s", filename)
        try:
            with open(filename, 'r') as f:
                self._execute_code(f.read())
            self.logger.info("File executed successfully")
        except Exception as e:
            self.logger.error("Error executing file: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def _init_rabbit_clients(self):
        self.logger.info("Initializing RabbitMQ clients")
        try:
            rabbit_client = RabbitMQClient(address=self.client_settings.rabbit_mq_address,
                                           credentials=self.client_settings.rabbit_mq_credentials,
                                           exchange=self.EXCHANGE)
            sender = RabbitMQJsonSender(
                rabbit_mq_client=rabbit_client,
                topic=self.EXECUTION_PUBLISHING_TOPIC.format(kernel_id=self.kernel_id))
            listener = RabbitMQJsonReceiver(rabbit_client)
            self.logger.info("RabbitMQ clients initialized successfully")
            return sender, listener
        except Exception as e:
            self.logger.error("Error initializing RabbitMQ clients: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise

    def get_connection_file_dict(self):
        self.logger.debug('Reading connection file %s', os.getcwd())
        try:
            with open('kernel-' + self.kernel_id + '.json', 'r') as json_file:
                connection_dict = json.load(json_file)
            self.logger.debug("Connection file read successfully")
            return connection_dict
        except IOError as e:
            self.logger.error("Error reading connection file: %s", os.strerror(e.errno))
            self.logger.error(traceback.format_exc())
            raise

    def _init_socket_forwarders(self):
        self.logger.info("Initializing socket forwarders")
        try:
            forwarders = {}
            kernel_json = self.get_connection_file_dict()

            def make_sender(stream_name):
                def sender(message):
                    self._send_zmq_forward_to_rabbit(stream_name, message)
                return sender

            for socket in ['shell', 'control', 'stdin']:
                self.subscriber[socket] = self.context.socket(zmq.DEALER)

            # iopub is PUB socket, we treat it differently and have to set SUBSCRIPTION topic
            self.subscriber['iopub'] = self.context.socket(zmq.SUB)
            self.subscriber['iopub'].setsockopt(zmq.SUBSCRIBE, b'')

            for socket, zmq_socket in self.subscriber.items():
                zmq_socket.connect('tcp://localhost:' + str(kernel_json[socket + '_port']))
                forwarders[socket] = SocketForwarder(
                    stream_name=socket,
                    zmq_socket=zmq_socket,
                    to_rabbit_sender=make_sender(socket))

            self.logger.info("Socket forwarders initialized successfully")
            return forwarders
        except Exception as e:
            self.logger.error("Error initializing socket forwarders: %s", str(e))
            self.logger.error(traceback.format_exc())
            raise