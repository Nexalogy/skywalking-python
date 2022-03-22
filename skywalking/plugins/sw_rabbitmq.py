#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from skywalking import Layer, Component
from skywalking.trace.carrier import Carrier
from skywalking.trace.context import get_context
from skywalking.trace.tags import TagMqBroker, TagMqTopic, TagMqQueue

link_vector = ['https://pika.readthedocs.io']
support_matrix = {
    'pika': {
        '>=3.6': ['1.2']
    }
}
note = """"""


def install():
    from pika.channel import Channel
    from pika.adapters.blocking_connection import _ConsumerInfo

    _basic_publish = Channel.basic_publish
    __on_deliver = Channel._on_deliver
    ___init__ = _ConsumerInfo.__init__
    Channel.basic_publish = _sw_basic_publish_func(_basic_publish)
    Channel._on_deliver = _sw__on_deliver_func(__on_deliver)
    _ConsumerInfo.__init__ = _sw_consumer_info___init__(___init__)


def _sw_basic_publish_func(_basic_publish):
    def _sw_basic_publish(this, exchange,
                          routing_key,
                          body,
                          properties=None,
                          mandatory=False):
        peer = f'{this.connection.params.host}:{this.connection.params.port}'
        context = get_context()
        carrier = get_carrier_from_properties(properties)

        import pika
        with context.new_exit_span(op=f'RabbitMQ/Topic/{exchange}/Queue/{routing_key}/Producer' or '/',
                                   peer=peer, component=Component.RabbitmqProducer, carrier=carrier) as span:
            carrier = span.inject()
            span.layer = Layer.MQ
            properties = pika.BasicProperties() if properties is None else properties

            if properties.headers is None:
                properties.headers = {}
            for item in carrier:
                properties.headers[item.key] = item.val

            res = _basic_publish(this, exchange,
                                 routing_key,
                                 body,
                                 properties=properties,
                                 mandatory=mandatory)
            span.tag(TagMqBroker(peer))
            span.tag(TagMqTopic(exchange))
            span.tag(TagMqQueue(routing_key))

            return res

    return _sw_basic_publish


def _sw__on_deliver_func(__on_deliver):
    def _sw__on_deliver(this, method_frame, header_frame, body):
        peer = f'{this.connection.params.host}:{this.connection.params.port}'
        context = get_context()
        exchange = method_frame.method.exchange
        routing_key = method_frame.method.routing_key
        carrier = Carrier()
        for item in carrier:
            try:
                if item.key in header_frame.properties.headers:
                    item.val = header_frame.properties.headers[item.key]
            except TypeError as te:
                pass

        with context.new_entry_span(op='RabbitMQ/Topic/' + exchange + '/Queue/' + routing_key
                                       + '/Consumer' or '', carrier=carrier) as span:
            header_frame.properties = save_carrier_async(context, span, carrier, header_frame.properties)
            span.layer = Layer.MQ
            span.component = Component.RabbitmqConsumer
            __on_deliver(this, method_frame, header_frame, body)
            span.tag(TagMqBroker(peer))
            span.tag(TagMqTopic(exchange))
            span.tag(TagMqQueue(routing_key))

    return _sw__on_deliver


def _sw_consumer_info___init__(___init__):
    def _sw___init__(this,
                 consumer_tag,
                 auto_ack,
                 on_message_callback=None,
                 alternate_event_sink=None):
        
        def _on_message_callback(that, method, properties, body):

            exchange = method.exchange
            routing_key = method.routing_key

            carrier = get_carrier_from_properties(properties)
            
            context = get_context()

            with context.new_local_span(op='on_message_callback: ' + 'RabbitMQ/Topic/' + exchange 
                                           + '/Queue/' + routing_key + '/Consumer' or '', carrier=carrier) as span:
                
                properties = save_carrier_async(context, span, carrier, properties)
                span.layer = Layer.MQ
                span.component = Component.RabbitmqConsumer
                on_message_callback(that, method, properties, body)
                span.tag(TagMqTopic(exchange))
                span.tag(TagMqQueue(routing_key))

        return ___init__(this, consumer_tag,
                 auto_ack,
                 _on_message_callback,
                 alternate_event_sink)

    return _sw___init__

def get_carrier_from_properties(properties):

    carrier = None

    in_carrier = Carrier()
    for item in in_carrier:
        try:
            if item.key in properties.headers:
                item.val = properties.headers[item.key]
        except TypeError as te:
            pass
    if(in_carrier.is_valid):
        carrier = in_carrier

    return carrier

def save_carrier_async(context, span, carrier, properties):
    if(carrier is not None and carrier.segment_id is not "" and context.segment.segment_id is not ""):
        carrier = span.inject_async()
        if properties.headers is None:
            properties.headers = {}
        for item in carrier:
            properties.headers[item.key] = item.val

    return properties