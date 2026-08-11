<?php
/**
 * CRUD helpers for QR code definitions.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Codes {

	public static function get( $id ) {
		global $wpdb;
		$table = QRST_DB::codes_table();
		return $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$table} WHERE id = %d", $id ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}

	public static function get_by_slug( $slug ) {
		global $wpdb;
		$table = QRST_DB::codes_table();
		return $wpdb->get_row( $wpdb->prepare( "SELECT * FROM {$table} WHERE slug = %s", $slug ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}

	public static function get_all( $args = array() ) {
		global $wpdb;
		$table = QRST_DB::codes_table();

		$defaults = array(
			'orderby' => 'created_at',
			'order'   => 'DESC',
			'search'  => '',
			'limit'   => 0,
			'offset'  => 0,
		);
		$args = wp_parse_args( $args, $defaults );

		$allowed_orderby = array( 'id', 'label', 'created_at', 'updated_at', 'status' );
		$orderby         = in_array( $args['orderby'], $allowed_orderby, true ) ? $args['orderby'] : 'created_at';
		$order           = 'ASC' === strtoupper( $args['order'] ) ? 'ASC' : 'DESC';

		$where  = 'WHERE 1=1';
		$params = array();

		if ( ! empty( $args['search'] ) ) {
			$where   .= ' AND (label LIKE %s OR target_url LIKE %s OR slug LIKE %s)';
			$like     = '%' . $wpdb->esc_like( $args['search'] ) . '%';
			$params[] = $like;
			$params[] = $like;
			$params[] = $like;
		}

		$sql = "SELECT * FROM {$table} {$where} ORDER BY {$orderby} {$order}";

		if ( ! empty( $args['limit'] ) ) {
			$sql     .= ' LIMIT %d OFFSET %d';
			$params[] = (int) $args['limit'];
			$params[] = (int) $args['offset'];
		}

		if ( $params ) {
			$sql = $wpdb->prepare( $sql, $params ); // phpcs:ignore WordPress.DB.PreparedSQL.NotPrepared
		}

		return $wpdb->get_results( $sql ); // phpcs:ignore WordPress.DB.PreparedSQL.NotPrepared
	}

	public static function count( $search = '' ) {
		global $wpdb;
		$table = QRST_DB::codes_table();

		if ( $search ) {
			$like = '%' . $wpdb->esc_like( $search ) . '%';
			return (int) $wpdb->get_var(
				$wpdb->prepare( "SELECT COUNT(*) FROM {$table} WHERE label LIKE %s OR target_url LIKE %s OR slug LIKE %s", $like, $like, $like ) // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			);
		}

		return (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table}" ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}

	public static function create( $data ) {
		global $wpdb;
		$table = QRST_DB::codes_table();

		$slug   = self::unique_slug( isset( $data['slug'] ) ? $data['slug'] : $data['label'] );
		$now    = current_time( 'mysql' );
		$status = isset( $data['status'] ) && in_array( $data['status'], array( 'active', 'inactive' ), true ) ? $data['status'] : 'active';

		$wpdb->insert(
			$table,
			array(
				'label'      => sanitize_text_field( $data['label'] ),
				'slug'       => $slug,
				'target_url' => esc_url_raw( $data['target_url'] ),
				'status'     => $status,
				'campaign'   => sanitize_text_field( $data['campaign'] ?? '' ),
				'created_by' => get_current_user_id(),
				'created_at' => $now,
				'updated_at' => $now,
			)
		);

		return (int) $wpdb->insert_id;
	}

	public static function update( $id, $data ) {
		global $wpdb;
		$table = QRST_DB::codes_table();

		$update = array( 'updated_at' => current_time( 'mysql' ) );

		if ( isset( $data['label'] ) ) {
			$update['label'] = sanitize_text_field( $data['label'] );
		}
		if ( isset( $data['target_url'] ) ) {
			$update['target_url'] = esc_url_raw( $data['target_url'] );
		}
		if ( isset( $data['status'] ) && in_array( $data['status'], array( 'active', 'inactive' ), true ) ) {
			$update['status'] = $data['status'];
		}
		if ( isset( $data['campaign'] ) ) {
			$update['campaign'] = sanitize_text_field( $data['campaign'] );
		}
		if ( ! empty( $data['slug'] ) ) {
			$update['slug'] = self::unique_slug( $data['slug'], $id );
		}

		return $wpdb->update( $table, $update, array( 'id' => (int) $id ) );
	}

	public static function delete( $id ) {
		global $wpdb;
		$id = (int) $id;

		$wpdb->delete( QRST_DB::scans_table(), array( 'code_id' => $id ) );
		return $wpdb->delete( QRST_DB::codes_table(), array( 'id' => $id ) );
	}

	/**
	 * Turns a label into a URL-safe, unique slug, e.g. "Storefront Poster"
	 * -> "storefront-poster" (or "storefront-poster-2" if taken).
	 */
	public static function unique_slug( $base, $ignore_id = 0 ) {
		global $wpdb;
		$table = QRST_DB::codes_table();

		$base = sanitize_title( $base );
		if ( '' === $base ) {
			$base = 'qr';
		}

		$slug  = $base;
		$i     = 2;
		while ( true ) {
			$sql = "SELECT id FROM {$table} WHERE slug = %s";
			$params = array( $slug );
			if ( $ignore_id ) {
				$sql     .= ' AND id != %d';
				$params[] = $ignore_id;
			}
			$existing = $wpdb->get_var( $wpdb->prepare( $sql, $params ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared

			if ( ! $existing ) {
				return $slug;
			}
			$slug = $base . '-' . $i;
			$i++;
		}
	}

	/**
	 * Full public tracking URL for a given QR code row.
	 */
	public static function tracking_url( $code ) {
		$settings = qrst_get_settings();
		$base     = trim( $settings['redirect_base'], '/' );
		return home_url( '/' . $base . '/' . rawurlencode( $code->slug ) . '/' );
	}
}
