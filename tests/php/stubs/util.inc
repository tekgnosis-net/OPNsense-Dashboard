<?php

/* Test stub for OPNsense's util.inc (signatures as of core 26.7.4). */

function get_configured_interface_with_descr()
{
    return $GLOBALS['__fx']['interfaces'] ?? [];
}

function get_real_interface($interface = 'wan', $family = 'all')
{
    return $GLOBALS['__fx']['devices'][$interface] ?? $interface;
}
