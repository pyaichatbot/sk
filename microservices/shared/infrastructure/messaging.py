# ============================================================================
# microservices/shared/infrastructure/messaging.py
# ============================================================================
"""
Enterprise Message Queue Manager for Microservices.
Provides robust, production-ready messaging with dead letter queues,
retry mechanisms, circuit breakers, and comprehensive monitoring.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager
import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
import logging
from datetime import datetime, timedelta

from shared.config.settings import MicroserviceSettings

logger = logging.getLogger(__name__)

class MessagePriority(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class MessageStatus(str, Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"

class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class MessageMetadata:
    """Message metadata for tracking and monitoring"""
    message_id: str
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    timestamp: datetime = None
    priority: MessagePriority = MessagePriority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    status: MessageStatus = MessageStatus.PENDING
    source_service: Optional[str] = None
    target_service: Optional[str] = None
    custom_headers: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.custom_headers is None:
            self.custom_headers = {}

@dataclass
class QueueConfig:
    """Queue configuration for enterprise features"""
    name: str
    durable: bool = True
    exclusive: bool = False
    auto_delete: bool = False
    arguments: Dict[str, Any] = None
    dead_letter_exchange: Optional[str] = None
    dead_letter_routing_key: Optional[str] = None
    message_ttl: Optional[int] = None  # in milliseconds
    max_length: Optional[int] = None
    max_priority: int = 10
    
    def __post_init__(self):
        if self.arguments is None:
            self.arguments = {}

@dataclass
class ExchangeConfig:
    """Exchange configuration"""
    name: str
    type: ExchangeType = ExchangeType.TOPIC
    durable: bool = True
    auto_delete: bool = False
    arguments: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.arguments is None:
            self.arguments = {}

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5
    recovery_timeout: int = 60  # seconds
    half_open_max_calls: int = 3

class CircuitBreaker:
    """Circuit breaker implementation for message queue resilience"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.config.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls
        return False
    
    def on_success(self):
        """Handle successful operation"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.config.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
    
    def on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
        elif self.state == CircuitBreakerState.CLOSED and self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN

class MessageQueueManager:
    """Enterprise Message Queue Manager with advanced features"""
    
    def __init__(self, settings: MicroserviceSettings):
        self.settings = settings
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self._exchanges: Dict[str, aio_pika.Exchange] = {}
        self._queues: Dict[str, aio_pika.Queue] = {}
        self._circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        self._message_metadata: Dict[str, MessageMetadata] = {}
        self._retry_queues: Dict[str, str] = {}  # original_queue -> retry_queue mapping
        self._dead_letter_queues: Dict[str, str] = {}  # original_queue -> dlq mapping
        self._consumers: Dict[str, aio_pika.abc.AbstractConsumer] = {}
        self._initialized = False
        self._metrics = {
            "messages_published": 0,
            "messages_consumed": 0,
            "messages_failed": 0,
            "messages_retried": 0,
            "messages_dead_lettered": 0,
            "circuit_breaker_trips": 0
        }
    
    async def initialize(self) -> None:
        """Initialize RabbitMQ connection with enterprise features"""
        try:
            if not self._circuit_breaker.can_execute():
                raise RuntimeError("Circuit breaker is open - cannot initialize connection")
            
            # Create robust connection with automatic reconnection
            self.connection = await aio_pika.connect_robust(
                self.settings.rabbitmq_url,
                heartbeat=30,
                blocked_connection_timeout=300,
                client_properties={
                    "connection_name": f"{self.settings.service_name}_mq_client",
                    "product": "Enterprise Agentic AI",
                    "version": self.settings.service_version
                }
            )
            
            # Create channel with QoS settings
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10, prefetch_size=0, global_=False)
            
            # Create default exchanges
            await self._create_default_exchanges()
            
            self._initialized = True
            self._circuit_breaker.on_success()
            
            logger.info(
                "Enterprise RabbitMQ connection established",
                service=self.settings.service_name,
                host=self.settings.rabbitmq_host,
                port=self.settings.rabbitmq_port,
                circuit_breaker_state=self._circuit_breaker.state.value
            )
            
        except Exception as e:
            self._circuit_breaker.on_failure()
            logger.error(
                "Failed to initialize RabbitMQ connection",
                error=str(e),
                service=self.settings.service_name,
                circuit_breaker_state=self._circuit_breaker.state.value
            )
            raise
    
    async def _create_default_exchanges(self) -> None:
        """Create default exchanges for enterprise messaging"""
        default_exchanges = [
            ExchangeConfig("amq.topic", ExchangeType.TOPIC),
            ExchangeConfig("dlx", ExchangeType.TOPIC),  # Dead letter exchange
            ExchangeConfig("retry", ExchangeType.TOPIC),  # Retry exchange
            ExchangeConfig("events", ExchangeType.TOPIC),  # Event exchange
            ExchangeConfig("commands", ExchangeType.DIRECT),  # Command exchange
            ExchangeConfig("responses", ExchangeType.DIRECT)  # Response exchange
        ]
        
        for exchange_config in default_exchanges:
            await self.create_exchange(exchange_config)
    
    async def close(self) -> None:
        """Close RabbitMQ connection gracefully"""
        try:
            # Stop all consumers
            for consumer in self._consumers.values():
                await consumer.cancel()
            
            # Close channel and connection
            if self.channel:
                await self.channel.close()
            if self.connection:
                await self.connection.close()
            
            self._initialized = False
            logger.info(
                "RabbitMQ connection closed gracefully",
                service=self.settings.service_name
            )
            
        except Exception as e:
            logger.error(
                "Error closing RabbitMQ connection",
                error=str(e),
                service=self.settings.service_name
            )
    
    async def create_exchange(self, config: Union[str, ExchangeConfig]) -> aio_pika.Exchange:
        """Create an exchange with enterprise configuration"""
        if not self._initialized:
            raise RuntimeError("Message queue manager not initialized")
        
        if isinstance(config, str):
            config = ExchangeConfig(name=config)
        
        try:
            exchange = await self.channel.declare_exchange(
                name=config.name,
                type=config.type,
                durable=config.durable,
                auto_delete=config.auto_delete,
                arguments=config.arguments
            )
            
            self._exchanges[config.name] = exchange
            logger.debug(
                "Exchange created",
                exchange=config.name,
                type=config.type.value,
                service=self.settings.service_name
            )
            
            return exchange
            
        except Exception as e:
            logger.error(
                "Failed to create exchange",
                exchange=config.name,
                error=str(e),
                service=self.settings.service_name
            )
            raise
    
    async def create_queue(self, config: Union[str, QueueConfig]) -> aio_pika.Queue:
        """Create a queue with enterprise features (DLQ, retry, TTL, etc.)"""
        if not self._initialized:
            raise RuntimeError("Message queue manager not initialized")
        
        if isinstance(config, str):
            config = QueueConfig(name=config)
        
        try:
            # Prepare queue arguments
            arguments = config.arguments.copy()
            
            # Add dead letter exchange if specified
            if config.dead_letter_exchange:
                arguments["x-dead-letter-exchange"] = config.dead_letter_exchange
                if config.dead_letter_routing_key:
                    arguments["x-dead-letter-routing-key"] = config.dead_letter_routing_key
            
            # Add message TTL if specified
            if config.message_ttl:
                arguments["x-message-ttl"] = config.message_ttl
            
            # Add max length if specified
            if config.max_length:
                arguments["x-max-length"] = config.max_length
            
            # Add max priority for priority queues
            if config.max_priority > 0:
                arguments["x-max-priority"] = config.max_priority
            
            # Create main queue
            queue = await self.channel.declare_queue(
                name=config.name,
                durable=config.durable,
                exclusive=config.exclusive,
                auto_delete=config.auto_delete,
                arguments=arguments
            )
            
            self._queues[config.name] = queue
            
            # Create retry queue if not exists
            retry_queue_name = f"{config.name}.retry"
            if retry_queue_name not in self._queues:
                retry_config = QueueConfig(
                    name=retry_queue_name,
                    durable=config.durable,
                    arguments={
                        "x-message-ttl": 60000,  # 1 minute retry delay
                        "x-dead-letter-exchange": "amq.topic",
                        "x-dead-letter-routing-key": config.name
                    }
                )
                await self.create_queue(retry_config)
                self._retry_queues[config.name] = retry_queue_name
            
            # Create dead letter queue if not exists
            dlq_name = f"{config.name}.dlq"
            if dlq_name not in self._queues:
                dlq_config = QueueConfig(
                    name=dlq_name,
                    durable=config.durable
                )
                await self.create_queue(dlq_config)
                self._dead_letter_queues[config.name] = dlq_name
            
            logger.debug(
                "Queue created with enterprise features",
                queue=config.name,
                retry_queue=self._retry_queues.get(config.name),
                dead_letter_queue=self._dead_letter_queues.get(config.name),
                service=self.settings.service_name
            )
            
            return queue
            
        except Exception as e:
            logger.error(
                "Failed to create queue",
                queue=config.name,
                error=str(e),
                service=self.settings.service_name
            )
            raise
    
    async def publish_message(
        self,
        exchange_name: str,
        routing_key: str,
        message: Dict[str, Any],
        metadata: Optional[MessageMetadata] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: Optional[str] = None,
        reply_to: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> bool:
        """Publish a message with enterprise features"""
        if not self._initialized:
            raise RuntimeError("Message queue manager not initialized")
        
        if not self._circuit_breaker.can_execute():
            logger.warning(
                "Circuit breaker is open - message not published",
                exchange=exchange_name,
                routing_key=routing_key,
                service=self.settings.service_name
            )
            return False
        
        try:
            # Ensure exchange exists
            if exchange_name not in self._exchanges:
                await self.create_exchange(exchange_name)
            
            exchange = self._exchanges[exchange_name]
            
            # Create message metadata if not provided
            if metadata is None:
                import uuid
                metadata = MessageMetadata(
                    message_id=str(uuid.uuid4()),
                    correlation_id=correlation_id,
                    reply_to=reply_to,
                    priority=priority,
                    source_service=self.settings.service_name
                )
            
            # Prepare message headers
            headers = {
                "message_id": metadata.message_id,
                "timestamp": metadata.timestamp.isoformat(),
                "priority": metadata.priority.value,
                "source_service": metadata.source_service,
                "retry_count": metadata.retry_count,
                "max_retries": metadata.max_retries
            }
            
            # Add custom headers
            headers.update(metadata.custom_headers)
            
            # Prepare message properties
            properties = {
                "message_id": metadata.message_id,
                "correlation_id": metadata.correlation_id,
                "reply_to": metadata.reply_to,
                "headers": headers,
                "delivery_mode": DeliveryMode.PERSISTENT,
                "priority": self._get_priority_value(priority)
            }
            
            # Add TTL if specified
            if ttl:
                properties["expiration"] = str(ttl)
            
            # Serialize message body
            message_body = json.dumps({
                "data": message,
                "metadata": asdict(metadata)
            }).encode()
            
            # Create and publish message
            rabbitmq_message = Message(
                body=message_body,
                **properties
            )
            
            await exchange.publish(rabbitmq_message, routing_key=routing_key)
            
            # Store metadata for tracking
            self._message_metadata[metadata.message_id] = metadata
            
            # Update metrics
            self._metrics["messages_published"] += 1
            
            logger.debug(
                "Message published successfully",
                message_id=metadata.message_id,
                exchange=exchange_name,
                routing_key=routing_key,
                priority=priority.value,
                service=self.settings.service_name
            )
            
            self._circuit_breaker.on_success()
            return True
            
        except Exception as e:
            self._circuit_breaker.on_failure()
            self._metrics["messages_failed"] += 1
            
            logger.error(
                "Failed to publish message",
                exchange=exchange_name,
                routing_key=routing_key,
                error=str(e),
                service=self.settings.service_name
            )
            return False
    
    def _get_priority_value(self, priority: MessagePriority) -> int:
        """Convert priority enum to numeric value"""
        priority_map = {
            MessagePriority.LOW: 1,
            MessagePriority.NORMAL: 5,
            MessagePriority.HIGH: 8,
            MessagePriority.CRITICAL: 10
        }
        return priority_map.get(priority, 5)
    
    async def consume_messages(
        self,
        queue_name: str,
        callback: Callable,
        auto_ack: bool = False,
        prefetch_count: int = 10
    ) -> None:
        """Consume messages with enterprise features (retry, DLQ, etc.)"""
        if not self._initialized:
            raise RuntimeError("Message queue manager not initialized")
        
        try:
            # Ensure queue exists
            if queue_name not in self._queues:
                await self.create_queue(queue_name)
            
            queue = self._queues[queue_name]
            
            # Set QoS for this consumer
            await self.channel.set_qos(prefetch_count=prefetch_count)
            
            # Create wrapper callback with enterprise features
            async def enterprise_callback(message: aio_pika.IncomingMessage):
                await self._handle_message_with_retry(
                    message, callback, queue_name, auto_ack
                )
            
            # Start consuming
            consumer = await queue.consume(enterprise_callback, no_ack=auto_ack)
            self._consumers[queue_name] = consumer
            
            logger.info(
                "Started consuming messages",
                queue=queue_name,
                prefetch_count=prefetch_count,
                auto_ack=auto_ack,
                service=self.settings.service_name
            )
            
        except Exception as e:
            logger.error(
                "Failed to consume messages",
                queue=queue_name,
                error=str(e),
                service=self.settings.service_name
            )
            raise
    
    async def _handle_message_with_retry(
        self,
        message: aio_pika.IncomingMessage,
        callback: Callable,
        queue_name: str,
        auto_ack: bool
    ) -> None:
        """Handle message with retry logic and dead letter queue"""
        message_id = message.headers.get("message_id") if message.headers else None
        retry_count = message.headers.get("retry_count", 0) if message.headers else 0
        max_retries = message.headers.get("max_retries", 3) if message.headers else 3
        
        try:
            # Parse message
            message_data = json.loads(message.body.decode())
            data = message_data.get("data", {})
            metadata = message_data.get("metadata", {})
            
            # Update metadata
            if message_id and message_id in self._message_metadata:
                self._message_metadata[message_id].status = MessageStatus.PROCESSING
            
            # Call the user callback
            await callback(data, metadata, message)
            
            # Acknowledge message if not auto-ack
            if not auto_ack:
                message.ack()
            
            # Update metrics and status
            self._metrics["messages_consumed"] += 1
            if message_id and message_id in self._message_metadata:
                self._message_metadata[message_id].status = MessageStatus.COMPLETED
            
            logger.debug(
                "Message processed successfully",
                message_id=message_id,
                queue=queue_name,
                service=self.settings.service_name
            )
            
        except Exception as e:
            logger.error(
                "Message processing failed",
                message_id=message_id,
                queue=queue_name,
                retry_count=retry_count,
                error=str(e),
                service=self.settings.service_name
            )
            
            # Handle retry logic
            if retry_count < max_retries:
                await self._retry_message(message, queue_name, retry_count + 1)
                self._metrics["messages_retried"] += 1
                
                if message_id and message_id in self._message_metadata:
                    self._message_metadata[message_id].status = MessageStatus.RETRYING
                    self._message_metadata[message_id].retry_count = retry_count + 1
            else:
                # Send to dead letter queue
                await self._send_to_dead_letter_queue(message, queue_name, str(e))
                self._metrics["messages_dead_lettered"] += 1
                
                if message_id and message_id in self._message_metadata:
                    self._message_metadata[message_id].status = MessageStatus.DEAD_LETTER
            
            # Reject message if not auto-ack
            if not auto_ack:
                message.reject(requeue=False)
    
    async def _retry_message(
        self,
        message: aio_pika.IncomingMessage,
        original_queue: str,
        retry_count: int
    ) -> None:
        """Send message to retry queue"""
        try:
            retry_queue_name = self._retry_queues.get(original_queue)
            if not retry_queue_name:
                logger.warning(
                    "No retry queue found for original queue",
                    original_queue=original_queue,
                    service=self.settings.service_name
                )
                return
            
            # Update headers with new retry count
            headers = dict(message.headers) if message.headers else {}
            headers["retry_count"] = retry_count
            headers["original_queue"] = original_queue
            
            # Create new message for retry queue
            retry_message = Message(
                body=message.body,
                headers=headers,
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            # Publish to retry queue
            retry_exchange = self._exchanges.get("retry")
            if retry_exchange:
                await retry_exchange.publish(
                    retry_message,
                    routing_key=retry_queue_name
                )
            
            logger.info(
                "Message sent to retry queue",
                original_queue=original_queue,
                retry_queue=retry_queue_name,
                retry_count=retry_count,
                service=self.settings.service_name
            )
            
        except Exception as e:
            logger.error(
                "Failed to send message to retry queue",
                original_queue=original_queue,
                error=str(e),
                service=self.settings.service_name
            )
    
    async def _send_to_dead_letter_queue(
        self,
        message: aio_pika.IncomingMessage,
        original_queue: str,
        error_reason: str
    ) -> None:
        """Send message to dead letter queue"""
        try:
            dlq_name = self._dead_letter_queues.get(original_queue)
            if not dlq_name:
                logger.warning(
                    "No dead letter queue found for original queue",
                    original_queue=original_queue,
                    service=self.settings.service_name
                )
                return
            
            # Update headers with error information
            headers = dict(message.headers) if message.headers else {}
            headers["error_reason"] = error_reason
            headers["original_queue"] = original_queue
            headers["failed_at"] = datetime.utcnow().isoformat()
            
            # Create new message for dead letter queue
            dlq_message = Message(
                body=message.body,
                headers=headers,
                delivery_mode=DeliveryMode.PERSISTENT
            )
            
            # Publish to dead letter queue
            dlq_exchange = self._exchanges.get("dlx")
            if dlq_exchange:
                await dlq_exchange.publish(
                    dlq_message,
                    routing_key=dlq_name
                )
            
            logger.info(
                "Message sent to dead letter queue",
                original_queue=original_queue,
                dead_letter_queue=dlq_name,
                error_reason=error_reason,
                service=self.settings.service_name
            )
            
        except Exception as e:
            logger.error(
                "Failed to send message to dead letter queue",
                original_queue=original_queue,
                error=str(e),
                service=self.settings.service_name
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        try:
            if not self._initialized or not self.connection or not self.channel:
                return {
                    "status": "unhealthy",
                    "error": "Message queue manager not initialized",
                    "circuit_breaker_state": self._circuit_breaker.state.value
                }
            
            # Test connection
            await self.channel.connection.heartbeat()
            
            # Get queue information
            queue_info = {}
            for queue_name, queue in self._queues.items():
                try:
                    queue_info[queue_name] = {
                        "consumer_count": queue.declaration_result.consumer_count,
                        "message_count": queue.declaration_result.message_count
                    }
                except Exception:
                    queue_info[queue_name] = {"error": "Unable to get queue info"}
            
            return {
                "status": "healthy",
                "host": self.settings.rabbitmq_host,
                "port": self.settings.rabbitmq_port,
                "exchanges": len(self._exchanges),
                "queues": len(self._queues),
                "consumers": len(self._consumers),
                "circuit_breaker_state": self._circuit_breaker.state.value,
                "metrics": self._metrics,
                "queue_info": queue_info
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker_state": self._circuit_breaker.state.value,
                "metrics": self._metrics
            }
    
    async def get_message_status(self, message_id: str) -> Optional[MessageMetadata]:
        """Get message status and metadata"""
        return self._message_metadata.get(message_id)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get message queue metrics"""
        return {
            **self._metrics,
            "circuit_breaker_state": self._circuit_breaker.state.value,
            "active_consumers": len(self._consumers),
            "tracked_messages": len(self._message_metadata)
        }
    
    async def purge_queue(self, queue_name: str) -> bool:
        """Purge all messages from a queue"""
        try:
            if queue_name not in self._queues:
                return False
            
            queue = self._queues[queue_name]
            await queue.purge()
            
            logger.info(
                "Queue purged",
                queue=queue_name,
                service=self.settings.service_name
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to purge queue",
                queue=queue_name,
                error=str(e),
                service=self.settings.service_name
            )
            return False
    
    async def bind_queue_to_exchange(
        self,
        queue_name: str,
        exchange_name: str,
        routing_key: str = "#"
    ) -> bool:
        """Bind a queue to an exchange with routing key"""
        try:
            if queue_name not in self._queues or exchange_name not in self._exchanges:
                return False
            
            queue = self._queues[queue_name]
            exchange = self._exchanges[exchange_name]
            
            await queue.bind(exchange, routing_key)
            
            logger.info(
                "Queue bound to exchange",
                queue=queue_name,
                exchange=exchange_name,
                routing_key=routing_key,
                service=self.settings.service_name
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to bind queue to exchange",
                queue=queue_name,
                exchange=exchange_name,
                routing_key=routing_key,
                error=str(e),
                service=self.settings.service_name
            )
            return False

# Global message queue manager instance
_message_queue_manager: Optional[MessageQueueManager] = None

def get_message_queue_manager() -> Optional[MessageQueueManager]:
    """Get the global message queue manager instance"""
    return _message_queue_manager

def set_message_queue_manager(manager: MessageQueueManager) -> None:
    """Set the global message queue manager instance"""
    global _message_queue_manager
    _message_queue_manager = manager
