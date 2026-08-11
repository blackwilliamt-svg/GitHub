<?php
/**
 * Small standalone helper functions shared across the plugin.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! function_exists( 'qrst_get_settings' ) ) {
	/**
	 * Get plugin settings merged with defaults, so new options added in
	 * later versions never come back empty for existing installs.
	 */
	function qrst_get_settings() {
		$defaults = array(
			'collect_location' => 1,
			'geo_provider'     => 'ipapi_co',
			'geo_api_key'      => '',
			'store_raw_ip'     => 0,
			'anonymize_ip'     => 1,
			'retention_days'   => 0,
			'redirect_base'    => 'qr/go',
			'track_logged_in'  => 1,
			'exclude_roles'    => array( 'administrator' ),
		);

		$settings = get_option( 'qrst_settings', array() );

		return wp_parse_args( $settings, $defaults );
	}
}
