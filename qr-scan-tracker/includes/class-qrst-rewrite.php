<?php
/**
 * Registers the public /qr/go/{slug}/ route and handles the actual
 * "someone scanned this code" request: log it, then 302 to the target.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Rewrite {

	const QUERY_VAR = 'qrst_slug';

	public function register_rules() {
		$settings = qrst_get_settings();
		$base     = trim( $settings['redirect_base'], '/' );
		$base     = $base ? $base : 'qr/go';

		add_rewrite_rule(
			'^' . $base . '/([^/]+)/?$',
			'index.php?' . self::QUERY_VAR . '=$matches[1]',
			'top'
		);
	}

	public function register_query_vars( $vars ) {
		$vars[] = self::QUERY_VAR;
		return $vars;
	}

	public function maybe_handle_scan() {
		$slug = get_query_var( self::QUERY_VAR );

		if ( empty( $slug ) ) {
			return;
		}

		$slug = sanitize_title( $slug );
		$code = QRST_Codes::get_by_slug( $slug );

		if ( ! $code || 'active' !== $code->status ) {
			status_header( 404 );
			nocache_headers();
			wp_die( esc_html__( 'This QR code link is not available.', 'qr-scan-tracker' ), '', array( 'response' => 404 ) );
		}

		/**
		 * Fires right before a scan is recorded, in case something needs
		 * to run first (e.g. a custom bot filter).
		 */
		do_action( 'qrst_before_record_scan', $code );

		QRST_Scans::record( $code->id );

		do_action( 'qrst_after_record_scan', $code );

		nocache_headers();
		wp_redirect( esc_url_raw( $code->target_url ), 302 );
		exit;
	}
}
