# (C) Datadog, Inc. 2010-2016
# All rights reserved
# Licensed under Simplified BSD License (see LICENSE)

# stdlib
import re
import shlex

# project
from checks import AgentCheck
from utils.subprocess_output import get_subprocess_output
from collections import defaultdict

EVENT_TYPE = SOURCE_TYPE_NAME = 'cassandra_nodetool'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '7199'
TO_BYTES = {
    'B': 1,
    'KB': 1e3,
    'MB': 1e6,
    'GB': 1e9,
    'TB': 1e12,
}

class CassandraNodetoolCheck(AgentCheck):

    datacenter_name_re = re.compile('^Datacenter: (.*)')
    node_status_re = re.compile('^(?P<status>[UD])[NLJM] +(?P<address>\d+\.\d+\.\d+\.\d+) +'
                                '(?P<load>\d+\.\d*) (?P<load_unit>(K|M|G|T)?B) +\d+ +'
                                '(?P<owns>(\d+\.\d+%)|\?) +(?P<id>[a-fA-F0-9-]*) +(?P<rack>.*)')

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.nodetool_cmd = init_config.get("nodetool", "/usr/bin/nodetool")

    def check(self, instance):
        # Allow to specify a complete command for nodetool such as `docker exec container nodetool`
        nodetool_cmd = shlex.split(instance.get("nodetool", self.nodetool_cmd))
        host = instance.get("host", DEFAULT_HOST)
        port = instance.get("port", DEFAULT_PORT)
        keyspaces = instance.get("keyspaces", [])
        username = instance.get("username", "")
        password = instance.get("password", "")
        tags = instance.get("tags", [])

        for keyspace in keyspaces:
            # Build the nodetool command
            cmd = nodetool_cmd + ['-h', host, '-p', port]
            if username and password:
                cmd += ['-u', username, '-pw', password]
            cmd += ['status', '--', keyspace]

            # Execute the command
            out, err, _ = get_subprocess_output(cmd, self.log, False)
            if err or 'Error:' in out:
                self.log.error('Error executing nodetool status: %s', err or out)
            nodes = self._process_nodetool_output(out)

            percent_up_by_dc = defaultdict(float)
            percent_total_by_dc = defaultdict(float)
            for node in nodes:
                if node['status'] == 'U' and node['owns'] != '?':
                    percent_up_by_dc[node['datacenter']] += float(node['owns'][:-1])
                percent_total_by_dc[node['datacenter']] += float(node['owns'][:-1])

                node_tags = ['node_address:%s' % node['address'],
                             'node_id:%s' % node['id'],
                             'datacenter:%s' % node['datacenter'],
                             'rack:%s' % node['rack']]

                self.gauge('cassandra.nodetool.status.status', 1 if node['status'] == 'U' else 0,
                           tags=tags + node_tags)
                self.gauge('cassandra.nodetool.status.load', float(node['load']) * TO_BYTES[node['load_unit']],
                           tags=tags + node_tags)
                self.gauge('cassandra.nodetool.status.owns', float(node['owns'][:-1]),
                           tags=tags + node_tags)

            for datacenter, percent_up in percent_up_by_dc.items():
                self.gauge('cassandra.nodetool.status.replication_availability', percent_up,
                           tags=tags + ['keyspace:%s' % keyspace, 'datacenter:%s' % datacenter])
            for datacenter, percent_total in percent_total_by_dc.items():
                self.gauge('cassandra.nodetool.status.replication_factor', int(round(percent_total / 100)),
                           tags=tags + ['keyspace:%s' % keyspace, 'datacenter:%s' % datacenter])

    def _process_nodetool_output(self, output):
        nodes = []
        datacenter_name = ""
        for line in output.splitlines():
            # Ouput of nodetool
            # Datacenter: dc1
            # ===============
            # Status=Up/Down
            # |/ State=Normal/Leaving/Joining/Moving
            # --  Address     Load       Tokens  Owns (effective)  Host ID                               Rack
            # UN  172.21.0.3  184.8 KB   256     38.4%             7501ef03-eb63-4db0-95e6-20bfeb7cdd87  RAC1
            # UN  172.21.0.4  223.34 KB  256     39.5%             e521a2a4-39d3-4311-a195-667bf56450f4  RAC1

            match = self.datacenter_name_re.search(line)
            if match:
                datacenter_name = match.group(1)
                continue

            match = self.node_status_re.search(line)
            if match:
                node = {
                    'status': match.group('status'),
                    'address': match.group('address'),
                    'load': match.group('load'),
                    'load_unit': match.group('load_unit'),
                    'owns': match.group('owns'),
                    'id': match.group('id'),
                    'rack': match.group('rack'),
                    'datacenter': datacenter_name
                }
                nodes.append(node)

        return nodes