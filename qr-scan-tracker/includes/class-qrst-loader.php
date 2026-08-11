<?php
/**
 * Wires up all the hooks the plugin needs, in one predictable place.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Loader {

	public function run() {
		load_plugin_textdomain( 'qr-scan-tracker', false, dirname( QRST_PLUGIN_BASENAME ) . '/languages' );

		// Public-facing: rewrite rules + the actual scan/redirect handler.
		$rewrite = new QRST_Rewrite();
		add_action( 'init', array( $rewrite, 'register_rules' ) );
		add_filter( 'query_vars', array( $rewrite, 'register_query_vars' ) );
		add_action( 'template_redirect', array( $rewrite, 'maybe_handle_scan' ) );

		// Cron cleanup for retention policy.
		$cron = new QRST_Cron();
		add_action( 'qrst_daily_cleanup', array( $cron, 'run_cleanup' ) );

		// Shortcode to embed a QR code image anywhere.
		$shortcodes = new QRST_Shortcodes();
		add_action( 'init', array( $shortcodes, 'register' ) );

		// Lightweight REST endpoint used by the admin dashboard charts.
		$rest = new QRST_REST_API();
		add_action( 'rest_api_init', array( $rest, 'register_routes' ) );

		if ( is_admin() ) {
			$admin = new QRST_Admin();
			add_action( 'admin_menu', array( $admin, 'register_menu' ) );
			add_action( 'admin_notices', array( $admin, 'maybe_permalink_notice' ) );
			add_action( 'admin_enqueue_scripts', array( $admin, 'enqueue_assets' ) );
			add_action( 'admin_post_qrst_save_code', array( $admin, 'handle_save_code' ) );
			add_action( 'admin_post_qrst_delete_code', array( $admin, 'handle_delete_code' ) );
			add_action( 'admin_post_qrst_save_settings', array( $admin, 'handle_save_settings' ) );
			add_action( 'admin_post_qrst_export_csv', array( 'QRST_Export', 'handle_export' ) );
			add_filter( 'plugin_action_links_' . QRST_PLUGIN_BASENAME, array( $admin, 'plugin_action_links' ) );
		}
	}
}
