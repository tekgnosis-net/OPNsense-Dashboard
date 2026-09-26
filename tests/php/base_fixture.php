<?php

/*
 * A typical router as OPNsense core 26.7.4 describes it: WAN igb0 with IPv4
 * and IPv6, LAN igb1, IOT igb2 without carrier, a monitored IPv4 gateway and
 * an unmonitored auto-generated IPv6 gateway.
 */
function base_fixture(): array
{
    $flags = ['up', 'broadcast', 'running', 'simplex', 'multicast'];
    return [
        'interfaces' => ['lan' => 'LAN', 'opt1' => 'IOT', 'wan' => 'WAN'],
        'devices' => ['wan' => 'igb0', 'lan' => 'igb1', 'opt1' => 'igb2'],
        'details' => [
            'igb0' => ['flags' => $flags, 'macaddr' => '00:0d:b9:aa:bb:01', 'status' => 'active'],
            'igb1' => ['flags' => $flags, 'macaddr' => '00:0d:b9:aa:bb:02', 'status' => 'active'],
            'igb2' => ['flags' => $flags, 'macaddr' => '00:0d:b9:aa:bb:03', 'status' => 'no carrier'],
        ],
        'primary4' => [
            'wan' => ['203.0.113.45', '203.0.113.0/24', 24, 'igb0'],
            'lan' => ['192.168.1.1', '192.168.1.0/24', 24, 'igb1'],
            'opt1' => ['10.0.50.1', '10.0.50.0/24', 24, 'igb2'],
        ],
        'primary6' => [
            'wan' => ['2001:db8:0:1::1a2b', '2001:db8:0:1::1a2b/128', 128, 'igb0'],
            'lan' => ['2001:db8:1:10::1', '2001:db8:1:10::/64', 64, 'igb1'],
        ],
        'gateways' => [
            'WAN_DHCP' => [
                'name' => 'WAN_DHCP', 'interface' => 'wan', 'descr' => 'Interface WAN_DHCP Gateway',
                'gateway' => '203.0.113.1', 'monitor' => '1.1.1.1', 'monitor_disable' => '0', 'if' => 'igb0',
            ],
            'WAN_DHCP6' => [
                'name' => 'WAN_DHCP6', 'interface' => 'wan', 'descr' => 'Interface WAN_DHCP6 Gateway',
                'gateway' => 'fe80::1%igb0', 'monitor_disable' => '1', 'if' => 'igb0',
            ],
        ],
        'dpinger' => [
            'WAN_DHCP' => ['status' => 'none', 'monitor' => '1.1.1.1', 'name' => 'WAN_DHCP',
                'stddev' => '0.4 ms', 'delay' => '12.3 ms', 'loss' => '0.0 %'],
            'WAN_DHCP6' => ['status' => 'none', 'monitor' => '~', 'name' => 'WAN_DHCP6',
                'stddev' => '~', 'delay' => '~', 'loss' => '~'],
        ],
    ];
}
