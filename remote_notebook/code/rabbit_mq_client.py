import json
import time
from threading import Thread

import pika
from pika.exceptions import ConnectionClosed, ChannelClosed, AMQPError, StreamLostError

from utils import Logging

class RabbitMQClient(Logging):
    def __init__(self, address, credentials, exchange, exchange_type='topic', heartbeat=60, connection_attempts=3, retry_delay=5):
        super(RabbitMQClient, self).__init__()
        self._address = address
        self._exchange = exchange
        self._credentials = credentials
        self._exchange_type = exchange_type
        self._heartbeat = heartbeat
        self._consumer_connection_attempts = connection_attempts
        self._publisher_connection_attempts = connection_attempts
        self._retry_delay = retry_delay
        self._channel_impl = None
        self._publisher_impl = None
        self._connection = None
        self._publisher=None
        self._consumer_thread = None

        try:
            self._connect_consumer()
            self._declare_exchange_consumer()
            self._connect_publisher()
            self._declare_exchange_publisher()
            self.logger.info(f"RabbitMQClient initialized with exchange: {self._exchange}")
        except Exception as e:
            self.logger.error(f"Failed to initialize RabbitMQClient: {e}")
            raise

    def _connect_consumer(self):
        for attempt in range(self._consumer_connection_attempts):
            try:
                self.logger.info(f"Consumer Attempting to connect to RabbitMQ (Attempt {attempt + 1}/{self._consumer_connection_attempts})")
                self._connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self._address[0],
                        port=self._address[1],
                        credentials=pika.PlainCredentials(self._credentials[0], self._credentials[1]) 
                    )
                )
              
                self._channel_impl = self._connection.channel()
                self.logger.info("Consumer Successfully connected to RabbitMQ")
                return
            except (ConnectionClosed, AMQPError) as e:
                self.logger.warning(f"Consumer Failed to connect: {e}")
                if attempt < self._consumer_connection_attempts - 1:
                    self.logger.info(f"Consumer Retrying in {self._retry_delay} seconds...")
                    time.sleep(self._retry_delay)
                else:
                    self.logger.error("Consumer Max connection attempts reached")
                    raise
    
    def _connect_publisher(self):
        for attempt in range(self._publisher_connection_attempts):
            try:
                self.logger.info(f"publisher Attempting to connect to RabbitMQ (Attempt {attempt + 1}/{self._publisher_connection_attempts})")
                self._publisher = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self._address[0],
                        port=self._address[1],
                        credentials=pika.PlainCredentials(self._credentials[0], self._credentials[1])
                    )
                )
                self._publisher_impl = self._publisher.channel()
                self.logger.info("publisher Successfully connected to RabbitMQ")
                return
            except (ConnectionClosed, AMQPError) as e:
                self.logger.warning(f"publisher Failed to connect: {e}")
                if attempt < self._publisher_connection_attempts - 1:
                    self.logger.info(f"publisher Retrying in {self._retry_delay} seconds...")
                    time.sleep(self._retry_delay)
                else:
                    self.logger.error("publisher Max connection attempts reached")
                    raise
    
    def _reconnect_consumer(self):
        self.logger.info("Attempting to reconnect...")
        if self._connection and not self._connection.is_closed:
            try:
                self._connection.close()
            except Exception as e:
                self.logger.warning(f"Error closing existing connection: {e}")
        self._connect_consumer()
        self._declare_exchange_consumer()
    
    def _reconnect_publisher(self):
        self.logger.info("Attempting to reconnect...")
        if self._publisher and not self._publisher.is_closed:
            try:
                self._publisher.close()
            except Exception as e:
                self.logger.warning(f"Error closing existing connection: {e}")
        self._connect_publisher()
        self._declare_exchange_publisher()

    def send(self, topic, message, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Attempt {attempt + 1}: Sending message to topic: {topic} message :{message}")
                #self._reconnect()
                if self._publisher_impl is None:
                    raise Exception("Channel is None after reconnect")
                status = self._publisher_impl.basic_publish(
                    exchange=self._exchange,
                    routing_key=topic,
                    body=message,
                    mandatory=True
                )
                self.logger.debug(f"Message : {message} sent successfully. Status: {status}")
                return
            except (ConnectionClosed, ChannelClosed, AMQPError, StreamLostError) as e:
                self.logger.warning(f"Message : {message} send Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    self.logger.info("Attempting to reconnect...")
                    self._reconnect_publisher()
                else:
                    self.logger.error("Max retries reached. Failed to send message.")
                    raise

    def subscribe(self, topic, handler):
        try:
            #self._reconnect()
            queue_name = self._channel_impl.queue_declare(queue='', exclusive=True).method.queue
            self._channel_impl.queue_bind(exchange=self._exchange, queue=queue_name, routing_key=topic)
            self._channel_impl.basic_consume(queue=queue_name, on_message_callback=handler)

            if not self._consumer_thread or not self._consumer_thread.is_alive():
                self._reset_consumer_thread(start=True)

            self.logger.info(f"Subscribed to topic: {topic} with queue: {queue_name}")
        except (ConnectionClosed, ChannelClosed, AMQPError) as e:
            self.logger.error(f"Failed to subscribe to topic {topic}: {e}")
            self._reconnect_consumer()
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while subscribing to topic {topic}: {e}")
            raise

    def _declare_exchange_consumer(self):
        try:
            self._channel_impl.exchange_declare(exchange=self._exchange, exchange_type=self._exchange_type)
            self.logger.info(f"Exchange declared: {self._exchange} (type: {self._exchange_type})")
        except (ConnectionClosed, ChannelClosed, AMQPError) as e:
            self.logger.error(f"Failed to declare exchange: {e}")
            self._reconnect_consumer()
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while declaring exchange: {e}")
            raise
    def _declare_exchange_publisher(self):
        try:
            self._publisher_impl.exchange_declare(exchange=self._exchange, exchange_type=self._exchange_type)
            self.logger.info(f"Exchange declared: {self._exchange} (type: {self._exchange_type})")
        except (ConnectionClosed, ChannelClosed, AMQPError) as e:
            self.logger.error(f"Failed to declare exchange: {e}")
            self._reconnect_publisher()
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error while declaring exchange: {e}")
            raise
    def _reset_consumer_thread(self, start):
        try:
            if self._consumer_thread and self._consumer_thread.is_alive():
                self.logger.info("Stopping existing consumer thread")
                self._channel_impl.stop_consuming()
                self._consumer_thread.join(timeout=5)

            self._consumer_thread = Thread(target=self._channel_impl.start_consuming)
            self._consumer_thread.daemon = True
            if start:
                self._consumer_thread.start()
                self.logger.info("Consumer thread started")
        except Exception as e:
            self.logger.error(f"Error in reset_consumer_thread: {e}")
            raise

    def close(self):
        try:
            if self._channel_impl and self._channel_impl.is_open:
                self._channel_impl.close()
            if self._connection and self._connection.is_open:
                self._connection.close()
            self.logger.info("RabbitMQ connection closed")
        except Exception as e:
            self.logger.error(f"Error while closing RabbitMQ connection: {e}")

class RabbitMQJsonSender(Logging):
    def __init__(self, rabbit_mq_client, topic):
        super(RabbitMQJsonSender, self).__init__()
        self._rabbit_mq_client = rabbit_mq_client
        self._topic = topic
        self.logger.info(f"RabbitMQJsonSender initialized for topic: {self._topic}")

    def send(self, message):
        json_message = json.dumps(message)
        #self.logger.debug(f"JSON message to be sent to topic: {self._topic}: {json_message}")
        self._rabbit_mq_client.send(topic=self._topic, message=json_message)
        self.logger.debug(f"JSON message sent to topic: {self._topic}")
       
class RabbitMQJsonReceiver(Logging):
    def __init__(self, rabbit_mq_client):
        super(RabbitMQJsonReceiver, self).__init__()
        self._rabbit_mq_client = rabbit_mq_client
        self.logger.info("RabbitMQJsonReceiver initialized")

    def subscribe(self, topic, handler):
        try:
            self._rabbit_mq_client.subscribe(topic, self._wrapped_handler(handler))
            self.logger.info(f'Subscribed to topic {topic}')
        except Exception as e:
            self.logger.error(f'Unexpected error while subscribing to topic {topic}: {e}')
            raise

    def _wrapped_handler(self, actual_handler):
        def handle(ch, method, properties, body):
            try:
                message = json.loads(body)
                self.logger.debug(f"Received JSON message on topic: {method.routing_key}: {message}")
                return actual_handler(message)
            except ValueError as e:
                self.logger.error(f"Failed to decode JSON message: {body}. Error: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error in message handler: {e}")
        return handle