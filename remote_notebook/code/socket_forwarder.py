# Copyright 2016 deepsense.ai (CodiLime, Inc)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from utils import started_daemon_thread, Logging

class SocketForwarder(Logging):
    """
    This class is responsible for forwarding traffic between
    RabbitMQ and a ZMQ socket in both directions.

    Forwarding from ZMQ to Rabbit is done in a thread,
    while sending to Rabbit is achieved by calling forward_to_zmq method.
    """

    def __init__(self, stream_name, zmq_socket, to_rabbit_sender):
        super().__init__()
        self.stream_name = stream_name
        self.zmq_socket = zmq_socket
        self.to_rabbit_sender = to_rabbit_sender
        self.to_rabbit_forwarding_thread = None
        self._received_message_from_rabbit = False

    @property
    def received_message_from_rabbit(self):
        """
        This flag informs if the "other end" of the "connection"
        has sent something already.
        """
        return self._received_message_from_rabbit

    def start(self):
        try:
            self.logger.debug('Started {} SocketForwarder.'.format(self.stream_name))
            self.to_rabbit_forwarding_thread = started_daemon_thread(target=self.to_rabbit_forwarder)
        except Exception as e:
            self.logger.error('Failed to start SocketForwarder for {}: {}'.format(self.stream_name, e))

    def forward_to_zmq(self, message):
        try:
            self.logger.debug('[{}] Sending {}'.format(self.stream_name, message))
            self.zmq_socket.send_multipart(message)
            self._received_message_from_rabbit = True
        except Exception as e:
            self.logger.error('Failed to forward message to ZMQ for {}: {}'.format(self.stream_name, e))

    def to_rabbit_forwarder(self):
        while True:
            try:
                message = self.zmq_socket.recv_multipart()
                self.logger.debug('[{}] Sending {}'.format(self.stream_name, message))
                self.to_rabbit_sender(message)
            except Exception as e:
                self.logger.error('Failed to forward message to Rabbit for {}: {}'.format(self.stream_name, e))

class ToZmqSocketForwarder(SocketForwarder):
    """
    This subclass of SocketForwarder doesn't forward messages
    from ZMQ to Rabbit.

    This is useful for sockets that don't support receiving, like PUBs.
    """
    def start(self):
        try:
            self.logger.debug('[{}] NOT starting forwarding to Rabbit'.format(self.stream_name))
        except Exception as e:
            self.logger.error('Failed to log NOT starting forwarding to Rabbit for {}: {}'.format(self.stream_name, e))
