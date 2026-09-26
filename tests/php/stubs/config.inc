<?php

/*
 * Test stub for OPNsense's config.inc. In OPNsense, requiring config.inc
 * registers the MVC autoloader that provides this class (core 26.7.4).
 */

namespace OPNsense\Routing {
    class Gateways
    {
        public function gatewaysIndexedByName($disabled = false, $localhost = false, $inactive = false)
        {
            return $GLOBALS['__fx']['gateways'] ?? [];
        }
    }
}
