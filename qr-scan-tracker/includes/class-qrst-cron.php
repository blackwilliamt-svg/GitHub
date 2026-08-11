<?php
/**
 * Daily housekeeping: enforce the configured data retention window.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Cron {

	public function run_cleanup() {
		$settings = qrst_get_settings();
		$days     = isset( $settings['retention_days'] ) ? (int) $settings['retention_days'] : 0;

		if ( $days > 0 ) {
			QRST_Scans::delete_older_than( $days );
		}
	}
}
