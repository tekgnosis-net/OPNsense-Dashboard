<?php

/*
 * PPPoE WAN with IPv6 only, a VLAN and a WireGuard tunnel. Point-to-point
 * devices report no media status and an all-zero MAC (core 26.7.4 parser).
 */
$ptp = ['up', 'pointopoint', 'running', 'multicast'];
$GLOBALS['__fx'] = [
    'interfaces' => ['lan' => 'LAN', 'opt2' => 'GUEST', 'opt3' => 'VPN', 'wan' => 'WAN'],
    'devices' => ['wan' => 'pppoe0', 'lan' => 'igb1', 'opt2' => 'vlan0.10', 'opt3' => 'wg0'],
    'details' => [
        'pppoe0' => ['flags' => $ptp, 'macaddr' => '00:00:00:00:00:00', 'status' => ''],
        'igb1' => ['flags' => ['up', 'broadcast', 'running'], 'macaddr' => '00:0d:b9:aa:bb:02', 'status' => 'active'],
        'vlan0.10' => ['flags' => ['up', 'broadcast', 'running'], 'macaddr' => '00:0d:b9:aa:bb:02', 'status' => 'active'],
        'wg0' => ['flags' => $ptp, 'macaddr' => '00:00:00:00:00:00', 'status' => ''],
    ],
    'primary4' => [
        'lan' => ['192.168.1.1', '192.168.1.0/24', 24, 'igb1'],
        'opt2' => ['10.0.10.1', '10.0.10.0/24', 24, 'vlan0.10'],
        'opt3' => ['10.8.0.1', '10.8.0.0/24', 24, 'wg0'],
    ],
    'primary6' => [
        'wan' => ['2001:db8:0:1::1a2b', '2001:db8:0:1::1a2b/128', 128, 'pppoe0'],
    ],
    'gateways' => [],
    'dpinger' => [],
];
