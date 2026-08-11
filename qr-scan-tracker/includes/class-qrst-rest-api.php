<?php
/**
 * Small internal REST endpoint that feeds the admin dashboard chart via
 * fetch(), so the scans-per-day view can be re-queried without a full
 * page reload when the date range changes.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_REST_API {

	public function register_routes() {
		register_rest_route(
			'qrst/v1',
			'/stats/(?P<code_id>\d+)',
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_stats' ),
				'permission_callback' => function () {
					return current_user_can( 'manage_options' );
				},
				'args'                => array(
					'code_id' => array(
						'validate_callback' => function ( $param ) {
							return is_numeric( $param );
						},
					),
					'days'    => array(
						'default'           => 30,
						'validate_callback' => function ( $param ) {
							return is_numeric( $param );
						},
					),
				),
			)
		);
	}

	public function get_stats( $request ) {
		$code_id = (int) $request['code_id'];
		$days    = max( 1, min( 365, (int) $request->get_param( 'days' ) ) );

		if ( $code_id ) {
			$code = QRST_Codes::get( $code_id );
			if ( ! $code ) {
				return new WP_REST_Response( array( 'message' => 'Not found' ), 404 );
			}
		}

		$data = array(
			'per_day'   => QRST_Scans::scans_per_day( $code_id, $days ),
			'countries' => QRST_Scans::top_breakdown( $code_id, 'country', 5 ),
			'devices'   => QRST_Scans::top_breakdown( $code_id, 'device_type', 5 ),
			'browsers'  => QRST_Scans::top_breakdown( $code_id, 'browser', 5 ),
			'total'     => QRST_Scans::count_for_code( $code_id ),
			'unique'    => QRST_Scans::unique_visitors_for_code( $code_id ),
		);

		return new WP_REST_Response( $data, 200 );
	}
}
