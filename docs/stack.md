# Monitoring host setup

## Docker


To simplify everything, we'll use a Docker Compose file.

You will need to have Docker and Docker Compose installed on a server that will host the dashboard.

[Install Docker](https://docs.docker.com/engine/install/)

[Install Docker Compose](https://docs.docker.com/compose/install/)

After you've installed Docker and Docker Compose, download the docker-compose.yaml from this repo.

`curl https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/docker-compose.yaml -o docker-compose.yaml`

It's important that you change the TZ environment variable to your timezone for everything to work properly.
I also recommend you change the passwords in this compose file as well.
After you've made the necessary changes, run `docker-compose up -d` in the same directory as your docker-compose.yaml.
Once you have your docker containers running, follow the steps below.

## Configuring InfluxDB

After InfluxDB is started, go to http://(ip of docker server):8086, you will need to setup your username, password, bucket and organization here. Once that is done navigate to the Data tab, click on Telegraf, and create a configuration for a system. Name it, and copy your API token, you will need this for your Telegraf configuration. You will also need to generate another API token for Grafana. Click on API tokens -> Generate API Token -> Read/Write Access -> Click on your bucket under Read -> and Save. Copy this somewhere as well, you'll need it for Grafana.


## Configuring Graylog


### Add GeoIP to Graylog

To make the map work on Grafana, you must create a MaxMind account here https://www.maxmind.com/en/geolite2/signup. Then generate a license key by going to Account -> Manage License Keys -> Generate New License Key. Copy this key somewhere because you'll need it again soon.

You'll need to download the GeoIP database file to your Graylog container. Access your Graylog container's shell from your Docker host like so

`sudo docker exec -it graylog /bin/bash`

Then download the database file, replace `YOUR_LICENSE_KEY` with the key you generated above.

```
curl "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-Country&license_key=YOUR_LICENSE_KEY&suffix=tar.gz" -o GeoLite2-Country.tar.gz \
&& tar -xzvf GeoLite2-Country.tar.gz \
&& mv GeoLite2-Country_*/GeoLite2-Country.mmdb /usr/share/graylog/data/data/
```

### Configure Additional Settings

In a browser navigate to http://(ip of docker server):9000 and login.

For Graylog, it's recommended to create an index set. To do so, navigate to System -> Indices. Create an index set with the name "OPNsense / filterlog" and set the index prefix to `opnsense_filterlog`.

Once that's done, download the [content pack](https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/graylog/OPNsense-pack.json) and install it on Graylog by navigating to System -> Content Packs -> Upload, choose the pack, Upload, then Install.

Now, add your index set from earlier to the "OPNsense / filterlog" stream. Navigate to Streams -> More Actions -> Edit Stream -> select your index set and save.

There's one more step we need to do here, navigate to System -> Configurations -> click on Update under Message Processors, and reorder like so:

Ensure that all of these are enabled, and click save.

## Configuring Grafana


### Add InfluxDB and ElasticSearch data sources

You will need to add the data sources on Grafana. Navigate to http://(ip of docker server):3000, login and click on the cog wheel and Add a Data Source.

For InfluxDB, make the following configurations

Query Language: Flux

URL: http://influxdb:8086

Organization: Your InfluxDB Organization

Token: Your Grafana InfluxDB API Token

Default Bucket: Your opnsense bucket. This will be the bucket that the panel queries will use.

For ElasticSearch, make the following configurations

URL: http://elasticsearch:9200

Time field name: timestamp

Version: 7.10+

### Import Dashboard

To import the dashboard, copy the JSON from [OPNsense-Grafana-Dashboard.json](https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/grafana/dashboards/opnsense.json) and navigate to Dashboards -> Browse -> Import and paste under Import via panel json.

### Configure Variables

Dashboard Settings -> Variables -> Click on a variable to edit

WAN - $WAN is the variable for our WAN interface panels. It is currently set to igb0 under Custom options. Use a comma-separated list for multiple WAN interfaces.

LAN - $LAN uses a regex to remove any interfaces you don't want to be grouped as LAN. The filtering happens in the "Regex" field. I use a negative lookahead regex to match the interfaces I want excluded.  It should be pretty easy to understand what you need to do here. I have excluded igb0 (WAN),igb2,igb3,ovpnc1, and wg0.

iface - $iface is the interface variable for the Firewall panels, I have it set to igb0 by default. You can either remove igb0 so you can select all interfaces, or use a comma separated list of interfaces.

dataSource - dataSource is the variable for our InfluxDB data source. It is the data source that will be used for all panels with InfluxDB queries. You should see a preview of values you can pick from. Under Instance name filter, use the name of the InfluxDB data source you created for OPNsense if you have multiple InfluxDB data sources.

ESdataSource - ESdataSource is the variable four our Elasticsearch data source. It is the data source that will be used for all panels with Elasticsearch queries. You should see a preview of values you can pick from. Under Instance name filter, use the name of the Elastisearch data source you created for OPNsense if you have multiple Elasticsearch data sources.

Lastly, I don't recommend setting the time range beyond 24 hours, due to how many data points that will return in Grafana.

## Configuration for the Suricata dashboard #Optional

### Import the Suricata Dashboard

To import the dashboard, copy the JSON from [OPNsense-Grafana-Dashboard-Suricata.json](https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/grafana/dashboards/opnsense-suricata.json) and navigate to Dashboards -> Browse -> Import and paste under Import via panel json.
