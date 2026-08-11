<?php
/**
 * Runs on plugin deactivation. Tables and options are intentionally left
 * in place — they are only removed by uninstall.php if the user deletes
 * the plugin, so deactivating/reactivating never loses scan history.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Deactivator {

	public static function deactivate() {
		wp_clear_scheduled_hook( 'qrst_daily_cleanup' );
		flush_rewrite_rules();
	}
}
