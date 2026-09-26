# OPNsense (router) setup

## Configuring Telegraf


### For previous users

If you previously used the pkg install version of telegraf, follow these instructions.

Run `sudo pkg remove telegraf` to remove telegraf.

Delete the line that starts with telegraf in /usr/local/etc/sudoers.

Once those are done you can continue with the new configuration.


### Install the plugin and configure options
Install the Telegraf plugin on OPNsense, to do so, navigate to System -> Firmware -> Plugins -> Search for telegraf, and click the plus icon to install.

Navigate to Services -> Telegraf -> Input

Enable Network and PF Inputs.

Then click Save.

Now navigate to Services -> Telegraf -> Output

Enable Influx v2 Output and fill in the following:

Influx v2 Token: Your InfluxDB Token

Influx v2 URL: Your InfluxDB URL, this will be the IP address or hostname of your system that is running InfluxDB. E.g http://192.168.1.10:8086

Influx v2 Organization: Your InfluxDB Organization

Influx v2 Bucket: Your InfluxDB Bucket

Then click Save.


### Alternative OPNSense Configuration via Ansible

You can use Ansible to automate a few sections. Install [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/installation_distros.html) on your linux server and use the files at [opnsense/ansible](../opnsense/ansible/). If you use this method you can skip these sections: Add telegraf to sudoers, Telegraf Plugins, and Configuration for the Suricata dashboard.

### Add telegraf to sudoers

After that, we need to add telegraf to sudoers and use nopasswd to restrict telegraf to only what it needs to run as root.

```
printf 'telegraf ALL=(root) NOPASSWD: /usr/local/bin/telegraf_pfifgw.php\n' | sudo tee -a /usr/local/etc/sudoers > /dev/null
```

You may also wish to disable sudo logging for telegraf_pfifgw.php, otherwise you'll see many sudo logs from telegraf running the script every 10 seconds.

```
printf 'Cmnd_Alias PFIFGW = /usr/local/bin/telegraf_pfifgw.php\n' | sudo tee -a /usr/local/etc/sudoers > /dev/null
printf 'Defaults!PFIFGW !log_allowed\n' | sudo tee -a /usr/local/etc/sudoers > /dev/null
```

Add the  [custom.conf](../opnsense/telegraf.d/custom.conf) telegraf config to /usr/local/etc/telegraf.d

```
sudo mkdir /usr/local/etc/telegraf.d
sudo chown telegraf:telegraf /usr/local/etc/telegraf.d
sudo chmod 750 /usr/local/etc/telegraf.d
sudo curl https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/telegraf.d/custom.conf -o /usr/local/etc/telegraf.d/custom.conf
```

### Telegraf Plugins

**Plugins must be copied to your OPNsense system**

Place [telegraf_pfifgw.php](https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/bin/telegraf_pfifgw.php) and [telegraf_temperature.sh](https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/bin/telegraf_temperature.sh) in /usr/local/bin and chmod them to 755.

```
curl "https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/bin/telegraf_pfifgw.php" -o /usr/local/bin/telegraf_pfifgw.php
curl "https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/bin/telegraf_temperature.sh" -o /usr/local/bin/telegraf_temperature.sh
chmod 755 /usr/local/bin/telegraf_temperature.sh /usr/local/bin/telegraf_pfifgw.php
```

Test these out before starting the telegraf service by executing them

`sudo telegraf_pfifgw.php`

`telegraf_temperature.sh`

The temperature plugin may not work on every system, if you receive `sysctl: unknown oid 'hw.acpi.thermal'` comment out or remove that line from the plugin.

After this is done, navigate to Services -> Telegraf -> General -> Enable Telegraf Agent.

Lastly, check if Telegraf is running

`sudo service telegraf status`

## Configuring Graylog

### Add Graylog server as syslog target on OPNsense

Once that is all done, login to your OPNsense router and navigate to System -> Settings -> Logging / targets. Add a new target with the following options:

- Transport: UDP(4)
- Applications: filter (filterlog)
- Hostname: the Docker host running Graylog
- Port: 1514
- RFC5424: checked

Add a description if you'd like, then click save.

## Configuration for the Suricata dashboard #Optional

This section assumes you have already configured Suricata.

### Add the necessary files

Add [suricata.conf](../config/suricata/suricata.conf) to /usr/local/etc/telegraf.d

```
sudo curl 'https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/config/suricata/suricata.conf' -o /usr/local/etc/telegraf.d/suricata.conf
```

Add [custom.yaml](../config/suricata/custom.yaml) to /usr/local/opnsense/service/templates/OPNsense/IDS

```
sudo curl 'https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/config/suricata/custom.yaml' -o /usr/local/opnsense/service/templates/OPNsense/IDS/custom.yaml
```

Create the log file and give telegraf permissions to read it

```
sudo touch /tmp/eve.json
sudo chown :telegraf /tmp/eve.json
sudo chmod 640 /tmp/eve.json
```

### Restart Suricata and Telegraf

Restart Suricata from Services -> Intrusion Detection -> Administration

Uncheck Enabled and click Apply.

Check Enabled and click Apply.

Restart telegraf by running

`sudo service telegraf restart`


## Plugin reference

### Installing the Plugins
Place these plugins in "/usr/local/bin". The easiest way of doing this would be to SSH into your router, navigate to "/usr/local/bin" and use curl to download the files, like so:


`curl https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/bin/telegraf_pfifgw.php -o telegraf_pfifgw.php`

`curl https://raw.githubusercontent.com/tekgnosis-net/OPNsense-Dashboard/master/opnsense/bin/telegraf_temperature.sh -o telegraf_temperature.sh`

Make sure to set the permissions to "755"

### telegraf_pfifgw.php

This single script collects information for Interfaces and gateways.

**Interfaces:**
* Interface name
* IP4 address
* IP4 subnet
* IP6 address
* IP6 subnet
* MAC address
* Friendly name
* Status (Online/Offline/Etc.)

**Gateways:**
* Interface name
* Monitor IP
* Source IP
* GW Description
* Delay
* Stddev
* Loss (%)
* Status (Online/Offline/etc.)


### telegraf_temperature.sh

Provides temperature sensor information.
