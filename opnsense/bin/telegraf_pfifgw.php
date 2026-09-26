#!/usr/local/bin/php
<?php

/*
 * Telegraf exec input for OPNsense-Dashboard.
 *
 * Prints InfluxDB line protocol for two measurements:
 *   interface  one line per enabled interface: addresses, MAC, description, status
 *   gateways   one line per gateway: monitor, dpinger delay/stddev/loss, status
 * Telegraf adds the host tag. Needs Services > Telegraf > General > Run as Root.
 * Written against opnsense/core 26.7.4.
 */

// Keep PHP errors off stdout so they can never corrupt the line protocol.
ini_set('display_errors', 'stderr');

require_once 'config.inc';
require_once 'util.inc';
require_once 'interfaces.inc';
require_once 'plugins.inc.d/dpinger.inc';

/* Tag value: escape the characters line protocol uses as separators. */
function lp_tag($value, string $fallback): string
{
    $value = trim(str_replace(["\r", "\n"], ' ', (string)$value));
    if ($value === '') {
        $value = $fallback;
    }
    return str_replace([',', '=', ' '], ['\,', '\=', '\ '], $value);
}

/* String field value: double-quoted, with backslashes and quotes escaped. */
function lp_string($value, string $fallback): string
{
    $value = trim(str_replace(["\r", "\n"], ' ', (string)$value));
    if ($value === '') {
        $value = $fallback;
    }
    return '"' . str_replace(['\\', '"'], ['\\\\', '\\"'], $value) . '"';
}

/* dpinger reports "12.3 ms" or "0.0 %", and "~" while it has no data yet. */
function lp_number($value): ?string
{
    if (!is_string($value) || !preg_match('/^\s*(-?[0-9]+(?:\.[0-9]+)?)/', $value, $match)) {
        return null;
    }
    return (string)(float)$match[1];
}

/* 1 = up, 0 = down, 2 = unknown; the rule OPNsense's interface overview uses. */
function interface_status(?array $details): int
{
    if ($details === null) {
        return 2;
    }
    $status = in_array('up', $details['flags'] ?? [], true) ? 'up' : 'down';
    if (!empty($details['status']) && !in_array($details['status'], ['active', 'running'], true)) {
        $status = $details['status'];
    }
    if ($status === 'up' || $status === 'associated') {
        return 1;
    }
    if ($status === 'down' || strpos($status, 'no carrier') === 0) {
        return 0;
    }
    return 2;
}

/* "1" online, "0" offline, "2" degraded (delay and/or loss above threshold). */
function gateway_status(?string $status): string
{
    switch ($status) {
        case 'none':
            return '1';
        case 'down':
        case 'force_down':
            return '0';
        case 'delay':
        case 'loss':
        case 'delay+loss':
            return '2';
        default:
            return 'Unavailable';
    }
}

$details = legacy_interfaces_details();

foreach (get_configured_interface_with_descr() as $ifname => $descr) {
    $device = get_real_interface($ifname);
    $ifinfo = $details[$device] ?? null;
    [$ip4, $net4] = interfaces_primary_address($ifname, $details);
    [$ip6, $net6] = interfaces_primary_address6($ifname, $details);
    printf(
        "interface,name=%s,ip4_address=%s,ip4_subnet=%s,ip6_address=%s,ip6_subnet=%s,"
        . "mac_address=%s,friendlyname=%s,source=pfconfig status=%d\n",
        lp_tag($device, 'Unassigned'),
        lp_tag($ip4, 'Unassigned'),
        lp_tag($net4, 'Unassigned'),
        lp_tag($ip6, 'Unassigned'),
        lp_tag($net6, 'Unassigned'),
        lp_tag($ifinfo['macaddr'] ?? null, 'Unavailable'),
        lp_tag($descr, strtoupper($ifname)),
        interface_status($ifinfo)
    );
}

$dpinger = dpinger_status();

foreach ((new \OPNsense\Routing\Gateways())->gatewaysIndexedByName() as $name => $gateway) {
    $state = $dpinger[$name] ?? [];
    $monitor = !empty($gateway['monitor_disable']) ? 'Unmonitored' : ($gateway['monitor'] ?? '');
    $fields = [
        'monitor=' . lp_string($monitor, 'Unavailable'),
        'source=' . lp_string($gateway['gateway'] ?? '', 'Unavailable'),
        'gwdescr=' . lp_string($gateway['descr'] ?? '', 'Unassigned'),
    ];
    foreach (['delay', 'stddev', 'loss'] as $key) {
        $number = lp_number($state[$key] ?? null);
        if ($number !== null) {
            $fields[] = "{$key}={$number}";
        }
    }
    $fields[] = 'status=' . lp_string(gateway_status($state['status'] ?? null), 'Unavailable');
    printf(
        "gateways,interface=%s,gateway_name=%s %s\n",
        lp_tag($gateway['interface'] ?? '', 'Unassigned'),
        lp_tag($name, 'Unassigned'),
        implode(',', $fields)
    );
}
