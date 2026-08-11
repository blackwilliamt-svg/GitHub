<?php
/**
 * CSV export of a QR code's scan log.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Export {

	public static function handle_export() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'You do not have permission to do that.', 'qr-scan-tracker' ) );
		}

		check_admin_referer( 'qrst_export_csv' );

		$code_id = isset( $_GET['code_id'] ) ? absint( $_GET['code_id'] ) : 0;
		$code    = $code_id ? QRST_Codes::get( $code_id ) : null;

		if ( $code_id && ! $code ) {
			wp_die( esc_html__( 'QR code not found.', 'qr-scan-tracker' ) );
		}

		global $wpdb;
		$table = QRST_DB::scans_table();

		if ( $code_id ) {
			$rows = $wpdb->get_results( $wpdb->prepare( "SELECT * FROM {$table} WHERE code_id = %d ORDER BY scanned_at DESC", $code_id ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			$filename = 'qr-scans-' . $code->slug . '.csv';
		} else {
			$rows = $wpdb->get_results( "SELECT * FROM {$table} ORDER BY scanned_at DESC" ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			$filename = 'qr-scans-all.csv';
		}

		nocache_headers();
		header( 'Content-Type: text/csv; charset=utf-8' );
		header( 'Content-Disposition: attachment; filename="' . $filename . '"' );

		$output = fopen( 'php://output', 'w' );

		fputcsv(
			$output,
			array(
				'Scan ID', 'QR Code ID', 'Scanned At', 'Country', 'Country Code', 'Region', 'City',
				'Latitude', 'Longitude', 'Device Type', 'Browser', 'OS', 'Language',
				'Referrer', 'WP User', 'User Agent',
			)
		);

		foreach ( $rows as $row ) {
			fputcsv(
				$output,
				array(
					$row->id,
					$row->code_id,
					$row->scanned_at,
					$row->country,
					$row->country_code,
					$row->region,
					$row->city,
					$row->latitude,
					$row->longitude,
					$row->device_type,
					$row->browser,
					$row->os,
					$row->language,
					$row->referrer,
					$row->wp_user_login,
					$row->user_agent,
				)
			);
		}

		fclose( $output );
		exit;
	}
}
