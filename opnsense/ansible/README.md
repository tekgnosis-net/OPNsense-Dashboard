# Ansible playbook

Installs the collector scripts and the Telegraf exec configuration from this
checkout onto an OPNsense 26.7 firewall. It also removes leftovers from
earlier versions of this project: the sudoers lines, the old Suricata files
and `/tmp/eve.json`.

It does not change GUI settings. See [docs/opnsense.md](../../docs/opnsense.md)
for those, including **Run as Root**, which the collectors need.

You need:
- ansible-core 2.21 or later on the machine you run it from;
- SSH access to the firewall as root;
- the os-telegraf plugin installed on the firewall.

```sh
cd opnsense/ansible
# edit inventory.ini: set your firewall's address
ansible-playbook -i inventory.ini -k playbook.yml
```

`-k` asks for the root SSH password. Leave it out if you use SSH keys.
