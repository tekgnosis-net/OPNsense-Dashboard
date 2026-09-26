<?php

/* Test stub for OPNsense's interfaces.inc / interfaces.lib.inc (core 26.7.4). */

function legacy_interfaces_details($intf = null)
{
    $details = $GLOBALS['__fx']['details'] ?? [];
    return $intf === null ? $details : [$intf => $details[$intf] ?? []];
}

function interfaces_primary_address($interface, $ifconfig_details = null)
{
    return $GLOBALS['__fx']['primary4'][$interface] ?? [null, null, null, null];
}

function interfaces_primary_address6($interface, $ifconfig_details = null)
{
    return $GLOBALS['__fx']['primary6'][$interface] ?? [null, null, null, null];
}
