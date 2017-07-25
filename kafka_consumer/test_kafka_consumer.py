# (C) Datadog, Inc. 2010-2016
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

# stdlib
import copy
import os
import time
import threading

# 3p
from nose.plugins.attrib import attr
from nose import SkipTest
from kafka import KafkaConsumer, KafkaProducer

from kazoo.client import KazooClient
from kazoo.exceptions import NoNodeError

# project
from tests.checks.common import AgentCheckTest


instance = [{
    'kafka_connect_str': '172.17.0.1:9092',
    'zk_connect_str': 'localhost:2181',
    # 'zk_prefix': '/0.8',
    'consumer_groups': {
        'my_consumer': {
            'marvel': [0]
        }
    }
}]

METRICS = [
    'kafka.broker_offset',
    'kafka.consumer_offset',
    'kafka.consumer_lag',
]

TOPICS = ['marvel', 'dc']
PARTITIONS = [0, 1]

SHUTDOWN = False

class Producer(threading.Thread):
    daemon = True

    def run(self):
        producer = KafkaProducer(bootstrap_servers=instance[0]['kafka_connect_str'])

        while not SHUTDOWN:
            producer.send('marvel', b"Peter Parker")
            producer.send('marvel', b"Bruce Banner")
            producer.send('marvel', b"Tony Stark")
            producer.send('marvel', b"Johhny Blaze")
            producer.send('marvel', b"\xc2BoomShakalaka")
            producer.send('dc', b"Diana Prince")
            producer.send('dc', b"Bruce Wayne")
            producer.send('dc', b"Clark Kent")
            producer.send('dc', b"Arthur Curry")
            producer.send('dc', b"\xc2ShakalakaBoom")
            time.sleep(1)


class Consumer(threading.Thread):
    daemon = True

    def run(self):
        zk_path_topic_tmpl = '/consumers/my_consumer/offsets/'
        zk_path_partition_tmpl = zk_path_topic_tmpl + '{topic}/'

        zk_conn = KazooClient(instance[0]['zk_connect_str'], timeout=10)
        zk_conn.start()

        for topic in TOPICS:
            for partition in PARTITIONS:
                node_path = os.path.join(zk_path_topic_tmpl.format(topic), str(partition))
                node = zk_conn.exists(node_path)
                if not node:
                    zk_conn.ensure_path(node_path)

        consumer = KafkaConsumer(bootstrap_servers=instance[0]['kafka_connect_str'],
                                 group_id="my_consumer",
                                 auto_offset_reset='earliest',
                                 enable_auto_commit=False)
        consumer.subscribe()

        while not SHUTDOWN:
            response = consumer.poll(timeout_ms=500, max_records=10)
            zk_trans = zk_conn.transaction()
            for tp, records in response:
                topic = tp.topic
                partition = tp.partition

                offset = None
                for record in records:
                    if offset is None or record.offset > offset:
                        offset = record.offset

                zk_trans.set_data(
                    os.path.join(zk_path_topic_tmpl.format(topic), str(partition)),
                    offset
                )

            zk_trans.commit()

        zk_conn.stop()


@attr(requires='kafka_consumer')
class TestKafka(AgentCheckTest):
    """Basic Test for kafka_consumer integration."""
    CHECK_NAME = 'kafka_consumer'

    def __init__(self, *args, **kwargs):
        super(TestKafka, self).__init__(*args, **kwargs)

        self.threads = [
            Producer(),
            Consumer()
        ]

    def setUp(self):
	self.threads[0].start()
        time.sleep(45)
	self.threads[1].start()
        time.sleep(15)

    def tearDown(self):
        SHUTDOWN = True
        for t in self.threads:
            t.join(5)

    def test_check(self):
        """
        Testing Kafka_consumer check.
        """

        if os.environ.get('FLAVOR_OPTIONS','').lower() == "kafka":
            raise SkipTest("Skipping test - environment not configured for ZK consumer offsets")

        self.run_check({'instances': instance})

        for mname in METRICS:
            self.assertMetric(mname, at_least=1)

        self.coverage_report()


    def test_check_nogroups(self):
        """
        Testing Kafka_consumer check grabbing groups from ZK
        """

        if os.environ.get('FLAVOR_OPTIONS','').lower() == "kafka":
            raise SkipTest("Skipping test - environment not configured for ZK consumer offsets")

        nogroup_instance = copy.copy(instance)
        nogroup_instance[0].pop('consumer_groups')
        nogroup_instance[0]['monitor_unlisted_consumer_groups'] = True

        self.run_check({'instances': instance})

        for mname in METRICS:
            self.assertMetric(mname, at_least=1)

        self.coverage_report()
        raise Exception
