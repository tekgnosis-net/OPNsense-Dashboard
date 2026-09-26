<?php

require __DIR__ . '/../../base_fixture.php';
$fx = base_fixture();
$fx['interfaces'] = ['lan' => 'My LAN, main=1'];
$fx['gateways'] = [
    'GW_ESC' => [
        'name' => 'GW_ESC', 'interface' => 'wan', 'descr' => "Fibre \"backup\"\nC:\\link",
        'gateway' => '198.51.100.1', 'monitor' => '192.0.2.1', 'monitor_disable' => '0',
    ],
];
$fx['dpinger'] = ['GW_ESC' => ['status' => 'none', 'delay' => '5.0 ms', 'stddev' => '1.0 ms', 'loss' => '0.0 %']];
$GLOBALS['__fx'] = $fx;
