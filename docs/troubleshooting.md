# Troubleshooting


### Telegraf Plugins

- You can run most plugins from a shell/ssh session to verify the output. (the environment vars may be different when telegraf is executing the plugin)
- If you're copying from a windows system, make sure the [CRLF is correct](https://www.cyberciti.biz/faq/howto-unix-linux-convert-dos-newlines-cr-lf-unix-text-format/)
- The below command should display unix line endings (\n or LF) as $ and Windows line endings (\r\n or CRLF) as ^M$.

`cat -e /usr/local/bin/telegraf_pfifgw.php`

### Telegraf Troubleshooting
If you get no good output from running the plugin directly, try the following command before moving to the step below.

`sudo su -m telegraf -c 'telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d'`

To troubleshoot plugins further, enable Debug Log and disable Quiet Log in the Telegraf GUI then click Save. Run the above command again.

`sudo su -m telegraf -c 'telegraf --test --config /usr/local/etc/telegraf.conf --config-directory /usr/local/etc/telegraf.d'`


### InfluxDB
When in doubt, run a few queries to see if the data you are looking for is being populated.
I recommend doing this in Grafana's Explore tab.

### View measurements
    import "influxdata/influxdb/schema"

    schema.measurements(bucket: "opnsense")

### View field values

    from(bucket: "opnsense")
      |> range(start: -24h)
      |> filter(fn: (r) => r["_measurement"] == "system")
      |> limit(n:10)

### How to drop an InfluxDB v2 measurement

You must access your InfluxDB instance's shell to do this.

To do so run

`sudo docker exec -it influxdb /bin/bash`

on your docker host.

Then use the following

```
influx delete --bucket "$YourBucket" --predicate '_measurement="$Example"' -o $organization --start "1970-01-01T00:00:00Z" --stop "2050-12-31T23:59:00Z" --token "$YourAPIToken"
```

### Learn more about Flux queries

https://docs.influxdata.com/influxdb/cloud/query-data/flux/query-fields/

https://docs.influxdata.com/influxdb/cloud/query-data/flux/explore-schema/

### Suricata Troubleshooting

If there is no data on the Suricata dashboard, verify if there are any alerts in /tmp/eve.json.

If there is nothing in /tmp/eve.json, verify that /usr/local/opnsense/service/templates/OPNsense/IDS/custom.yaml and /usr/local/etc/suricata/custom.yaml are identical to the one in this repo.

If /usr/local/etc/suricata/custom.yaml is not identical, but /usr/local/opnsense/service/templates/OPNsense/IDS/custom.yaml is, you will need to reload Suricata from the GUI. To do so you would uncheck Enable in the Suricata GUI, click Apply, then check Enable, and click Apply again. You will need to wait for Suricata to reload. If you have a lot of rules this can take some time. 

If you've verified and done all the steps above, and still see nothing, you could try using [tmNIDS](https://github.com/3CORESec/testmynids.org) to generate alerts. You will need bash installed on your OPNsense system for this. 

`sudo pkg install bash`

Once you have bash installed, you can use this one-liner to download and execute tmNIDS.

```
curl https://raw.githubusercontent.com/3CORESec/testmynids.org/master/tmNIDS -o /tmp/tmNIDS && chmod +x /tmp/tmNIDS && bash /tmp/tmNIDS
```

You can then run the tests through the CLI.
### Map Issues

If you see no GeoIP data on the map make sure you rearranged the Message Processors in System -> Configurations, and reorder like so:
