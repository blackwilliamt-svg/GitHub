<?php
/**
 * Fires when the plugin is deleted from the Plugins screen. Only removes
 * data if the site owner explicitly opted in via Settings ->
 * "Delete all data on uninstall" — otherwise everything is left in place
 * so a re-install picks up right where things left off.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

if ( ! get_option( 'qrst_delete_data_on_uninstall' ) ) {
	return;
}

global $wpdb;

$tables = array(
	$wpdb->prefix . 'qrst_scans',
	$wpdb->prefix . 'qrst_codes',
	$wpdb->prefix . 'qrst_geo_cache',
);

foreach ( $tables as $table ) {
	$wpdb->query( "DROP TABLE IF EXISTS {$table}" ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
}

delete_option( 'qrst_settings' );
delete_option( 'qrst_db_version' );
delete_option( 'qrst_delete_data_on_uninstall' );

wp_clear_scheduled_hook( 'qrst_daily_cleanup' );
