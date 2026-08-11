<?php
/**
 * Builds the actual QR code image for a tracking link.
 *
 * Generating a correct QR code matrix (data encoding, error correction,
 * masking, etc.) from scratch is a lot of intricate, easy-to-get-wrong
 * code, so by default this class delegates image rendering to the free,
 * keyless QR generation endpoint at goqr.me (api.qrserver.com) — the
 * same approach used by many QR plugins. This only happens when an
 * admin views/downloads a code's image; it is never called while
 * tracking a scan. Sites that want a fully self-hosted generator can
 * swap it out with the `qrst_qr_image_url` filter.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_QR_Generator {

	/**
	 * Get a URL that renders a PNG QR code for the given data.
	 *
	 * @param string $data  The text/URL to encode.
	 * @param int    $size  Image size in pixels (square).
	 * @param string $ecc   Error correction level: L, M, Q, H.
	 */
	public static function image_url( $data, $size = 400, $ecc = 'M' ) {
		$size = max( 100, min( 1000, (int) $size ) );

		$url = add_query_arg(
			array(
				'size'    => $size . 'x' . $size,
				'ecc'     => $ecc,
				'data'    => rawurlencode( $data ),
				'margin'  => 10,
			),
			'https://api.qrserver.com/v1/create-qr-code/'
		);

		return apply_filters( 'qrst_qr_image_url', $url, $data, $size, $ecc );
	}
}
