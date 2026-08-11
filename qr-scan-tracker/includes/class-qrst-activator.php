<?php
/**
 * Runs on plugin activation: creates/upgrades database tables,
 * seeds default options, and registers + flushes rewrite rules.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Activator {

	public static function activate() {
		self::create_tables();
		self::set_default_options();

		// Make sure the /qr/go/{slug} route exists, then flush.
		require_once QRST_PLUGIN_DIR . 'includes/class-qrst-rewrite.php';
		QRST_Rewrite::register_rules();
		flush_rewrite_rules();

		if ( ! wp_next_scheduled( 'qrst_daily_cleanup' ) ) {
			wp_schedule_event( time() + HOUR_IN_SECONDS, 'daily', 'qrst_daily_cleanup' );
		}
	}

	public static function create_tables() {
		global $wpdb;

		require_once ABSPATH . 'wp-admin/includes/upgrade.php';

		$charset_collate = $wpdb->get_charset_collate();

		$codes_table = QRST_DB::codes_table();
		$scans_table = QRST_DB::scans_table();
		$geo_table   = QRST_DB::geo_cache_table();

		$sql = "CREATE TABLE {$codes_table} (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			label VARCHAR(191) NOT NULL,
			slug VARCHAR(64) NOT NULL,
			target_url TEXT NOT NULL,
			status VARCHAR(20) NOT NULL DEFAULT 'active',
			campaign VARCHAR(191) DEFAULT '',
			created_by BIGINT UNSIGNED DEFAULT 0,
			created_at DATETIME NOT NULL,
			updated_at DATETIME NOT NULL,
			PRIMARY KEY  (id),
			UNIQUE KEY slug (slug)
		) {$charset_collate};

		CREATE TABLE {$scans_table} (
			id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
			code_id BIGINT UNSIGNED NOT NULL,
			scanned_at DATETIME NOT NULL,
			ip_hash VARCHAR(64) DEFAULT '',
			ip_address VARCHAR(45) DEFAULT NULL,
			country VARCHAR(100) DEFAULT '',
			country_code VARCHAR(5) DEFAULT '',
			region VARCHAR(100) DEFAULT '',
			city VARCHAR(100) DEFAULT '',
			latitude DECIMAL(10,7) DEFAULT NULL,
			longitude DECIMAL(10,7) DEFAULT NULL,
			device_type VARCHAR(20) DEFAULT '',
			browser VARCHAR(50) DEFAULT '',
			os VARCHAR(50) DEFAULT '',
			language VARCHAR(10) DEFAULT '',
			referrer TEXT,
			user_agent TEXT,
			wp_user_id BIGINT UNSIGNED DEFAULT NULL,
			wp_user_login VARCHAR(191) DEFAULT '',
			PRIMARY KEY  (id),
			KEY code_id (code_id),
			KEY scanned_at (scanned_at),
			KEY ip_hash (ip_hash)
		) {$charset_collate};

		CREATE TABLE {$geo_table} (
			ip_hash VARCHAR(64) NOT NULL,
			country VARCHAR(100) DEFAULT '',
			country_code VARCHAR(5) DEFAULT '',
			region VARCHAR(100) DEFAULT '',
			city VARCHAR(100) DEFAULT '',
			latitude DECIMAL(10,7) DEFAULT NULL,
			longitude DECIMAL(10,7) DEFAULT NULL,
			cached_at DATETIME NOT NULL,
			PRIMARY KEY  (ip_hash)
		) {$charset_collate};";

		dbDelta( $sql );

		update_option( 'qrst_db_version', QRST_DB_VERSION );
	}

	public static function set_default_options() {
		$defaults = array(
			'collect_location'  => 1,
			'geo_provider'      => 'ipapi_co',
			'geo_api_key'       => '',
			'store_raw_ip'      => 0,
			'anonymize_ip'      => 1,
			'retention_days'    => 0, // 0 = keep forever.
			'redirect_base'     => 'qr/go',
			'track_logged_in'   => 1,
			'exclude_roles'     => array( 'administrator' ),
		);

		if ( false === get_option( 'qrst_settings' ) ) {
			add_option( 'qrst_settings', $defaults );
		}
	}
}
