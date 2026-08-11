<?php
/**
 * Central place for table names and small shared DB helpers.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_DB {

	/**
	 * Table storing each QR code definition.
	 */
	public static function codes_table() {
		global $wpdb;
		return $wpdb->prefix . 'qrst_codes';
	}

	/**
	 * Table storing every recorded scan.
	 */
	public static function scans_table() {
		global $wpdb;
		return $wpdb->prefix . 'qrst_scans';
	}

	/**
	 * Table caching IP -> geolocation lookups so we don't hit the
	 * remote geolocation service more than necessary.
	 */
	public static function geo_cache_table() {
		global $wpdb;
		return $wpdb->prefix . 'qrst_geo_cache';
	}
}
