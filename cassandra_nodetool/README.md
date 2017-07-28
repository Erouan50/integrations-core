# Agent Check: Cassandra Nodetool

# Overview

This check collects metrics for your Cassandra cluster that are not available through [jmx integration](https://github.com/DataDog/integrations-core/tree/master/cassandra).
It uses the `nodetool` utility to collect them.

# Installation

The varnish check is packaged with the Agent, so simply [install the Agent](https://app.datadoghq.com/account/settings#agent) on your cassandra nodes.
If you need the newest version of the check, install the `dd-check-cassandra_nodetool` package.

# Configuration

Create a file `cassandra_nodetool.yaml` in the Agent's `conf.d` directory:
```
init_config:
  # command or path to nodetool (e.g. /usr/bin/nodetool or docker exec container nodetool)
  # can be overwritten on an instance
  # nodetool: /usr/bin/nodetool

instances:

  # the list of keyspaces to monitor
  - keyspaces: []

  # host that nodetool will connect to.
  # host: localhost

  # the port JMX is listening to for connections.
  # port: 7199

  # a set of credentials to connect to the host. These are the credentials for the JMX server.
  # For the check to work, this user must have a read/write access so that nodetool can execute the `status` command
  # username:
  # password:

  # a list of additionnal tags to be sent with the metrics
  # tags: []
```

# Validation

When you run `datadog-agent info` you should see something like the following:

    Checks
    ======

        cassandra_nodetool
        -----------
          - instance #0 [OK]
          - Collected 39 metrics, 0 events & 7 service checks

# Compatibility

The `cassandra_nodetool` check is compatible with all major platforms