<?php
/**
 * [qrst_code] shortcode: drop a trackable QR code image into any post,
 * page, or widget.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Shortcodes {

	public function register() {
		add_shortcode( 'qrst_code', array( $this, 'render' ) );
	}

	/**
	 * Usage: [qrst_code id="3" size="300"] or [qrst_code slug="storefront-poster"]
	 */
	public function render( $atts ) {
		$atts = shortcode_atts(
			array(
				'id'   => 0,
				'slug' => '',
				'size' => 300,
				'alt'  => '',
			),
			$atts,
			'qrst_code'
		);

		$code = null;
		if ( ! empty( $atts['slug'] ) ) {
			$code = QRST_Codes::get_by_slug( sanitize_title( $atts['slug'] ) );
		} elseif ( ! empty( $atts['id'] ) ) {
			$code = QRST_Codes::get( absint( $atts['id'] ) );
		}

		if ( ! $code ) {
			return '';
		}

		$tracking_url = QRST_Codes::tracking_url( $code );
		$image_url    = QRST_QR_Generator::image_url( $tracking_url, absint( $atts['size'] ) );
		$alt          = $atts['alt'] ? $atts['alt'] : $code->label;

		return sprintf(
			'<img class="qrst-qr-code" src="%1$s" width="%2$d" height="%2$d" alt="%3$s" loading="lazy" />',
			esc_url( $image_url ),
			absint( $atts['size'] ),
			esc_attr( $alt )
		);
	}
}
