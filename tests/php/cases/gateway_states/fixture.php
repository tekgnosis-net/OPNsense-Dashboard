<?php

/*
 * Every dpinger state (core 26.7.4 dpinger_status()): down, partial loss
 * (PR #35), startup with no data yet ("~"), the three degraded states,
 * force_down, a gateway dpinger does not report, and a dynamic gateway with no
 * address yet plus a config-side 'loss' key that must be ignored (#79: "1.2 ms").
 */
$gw = static function (string $name, array $extra = []): array {
    return array_merge([
        'name' => $name, 'interface' => 'wan', 'descr' => "$name gateway",
        'gateway' => '198.51.100.1', 'monitor' => '192.0.2.1', 'monitor_disable' => '0',
    ], $extra);
};
$dynamic = $gw('GW_DYNAMIC', ['monitor' => '', 'loss' => '99', 'dynamic' => true]);
unset($dynamic['gateway']);

$GLOBALS['__fx'] = [
    'interfaces' => [],
    'gateways' => [
        'GW_DOWN' => $gw('GW_DOWN'),
        'GW_LOSSY' => $gw('GW_LOSSY'),
        'GW_STARTING' => $gw('GW_STARTING'),
        'GW_DELAY' => $gw('GW_DELAY'),
        'GW_LOSS' => $gw('GW_LOSS'),
        'GW_BOTH' => $gw('GW_BOTH'),
        'GW_FORCED' => $gw('GW_FORCED'),
        'GW_MISSING' => $gw('GW_MISSING'),
        'GW_DYNAMIC' => $dynamic,
    ],
    'dpinger' => [
        'GW_DOWN' => ['status' => 'down', 'delay' => '0.0 ms', 'stddev' => '0.0 ms', 'loss' => '100.0 %'],
        'GW_LOSSY' => ['status' => 'none', 'delay' => '25.1 ms', 'stddev' => '3.2 ms', 'loss' => '12.5 %'],
        'GW_STARTING' => ['status' => 'down', 'delay' => '~', 'stddev' => '~', 'loss' => '~'],
        'GW_DELAY' => ['status' => 'delay', 'delay' => '250.0 ms', 'stddev' => '10.0 ms', 'loss' => '0.0 %'],
        'GW_LOSS' => ['status' => 'loss', 'delay' => '30.0 ms', 'stddev' => '2.0 ms', 'loss' => '25.0 %'],
        'GW_BOTH' => ['status' => 'delay+loss', 'delay' => '300.0 ms', 'stddev' => '20.0 ms', 'loss' => '30.0 %'],
        'GW_FORCED' => ['status' => 'force_down', 'delay' => '~', 'stddev' => '~', 'loss' => '~'],
        'GW_DYNAMIC' => ['status' => 'none', 'delay' => '1.2 ms', 'stddev' => '0.1 ms', 'loss' => '0.0 %'],
    ],
];
