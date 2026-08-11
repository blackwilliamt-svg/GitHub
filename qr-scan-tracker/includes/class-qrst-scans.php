<?php
/**
 * Records scans and provides the aggregate queries the admin reports use.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Scans {

	/**
	 * Log a single scan for a QR code. Called from the redirect handler.
	 */
	public static function record( $code_id ) {
		global $wpdb;

		$settings = qrst_get_settings();

		$ip = self::get_client_ip();
		$ua = isset( $_SERVER['HTTP_USER_AGENT'] ) ? sanitize_text_field( wp_unslash( $_SERVER['HTTP_USER_AGENT'] ) ) : '';
		$parsed = QRST_User_Agent_Parser::parse( $ua );

		// Skip logging obvious bots/crawlers/link-preview fetchers so
		// stats reflect real human scans.
		if ( ! empty( $parsed['is_bot'] ) && apply_filters( 'qrst_skip_bot_scans', true ) ) {
			return false;
		}

		$user_id    = 0;
		$user_login = '';
		if ( ! empty( $settings['track_logged_in'] ) && is_user_logged_in() ) {
			$user         = wp_get_current_user();
			$excluded     = isset( $settings['exclude_roles'] ) ? (array) $settings['exclude_roles'] : array();
			$has_excluded = array_intersect( $excluded, (array) $user->roles );
			if ( empty( $has_excluded ) ) {
				$user_id    = $user->ID;
				$user_login = $user->user_login;
			}
		}

		$geo = QRST_Geolocation::locate( $ip );

		$ip_hash = $ip ? hash( 'sha256', $ip . wp_salt( 'auth' ) ) : '';

		$referrer = '';
		if ( isset( $_SERVER['HTTP_REFERER'] ) ) {
			$referrer = esc_url_raw( wp_unslash( $_SERVER['HTTP_REFERER'] ) );
		}

		$language = '';
		if ( isset( $_SERVER['HTTP_ACCEPT_LANGUAGE'] ) ) {
			$lang = sanitize_text_field( wp_unslash( $_SERVER['HTTP_ACCEPT_LANGUAGE'] ) );
			$language = substr( strtok( $lang, ',' ), 0, 10 );
		}

		$table = QRST_DB::scans_table();

		$wpdb->insert(
			$table,
			array(
				'code_id'       => (int) $code_id,
				'scanned_at'    => current_time( 'mysql' ),
				'ip_hash'       => $ip_hash,
				'ip_address'    => ! empty( $settings['store_raw_ip'] ) ? self::maybe_anonymize( $ip, $settings ) : null,
				'country'       => $geo['country'],
				'country_code'  => $geo['country_code'],
				'region'        => $geo['region'],
				'city'          => $geo['city'],
				'latitude'      => $geo['latitude'],
				'longitude'     => $geo['longitude'],
				'device_type'   => $parsed['device_type'],
				'browser'       => $parsed['browser'],
				'os'            => $parsed['os'],
				'language'      => $language,
				'referrer'      => $referrer,
				'user_agent'    => $ua,
				'wp_user_id'    => $user_id ? $user_id : null,
				'wp_user_login' => $user_login,
			)
		);

		return (int) $wpdb->insert_id;
	}

	protected static function maybe_anonymize( $ip, $settings ) {
		if ( empty( $settings['anonymize_ip'] ) ) {
			return $ip;
		}
		return self::anonymize_ip( $ip );
	}

	public static function anonymize_ip( $ip ) {
		if ( strpos( $ip, ':' ) !== false ) {
			// IPv6: zero out the last 80 bits (keep /48).
			$parts = explode( ':', $ip );
			for ( $i = 3; $i < count( $parts ); $i++ ) {
				$parts[ $i ] = '0';
			}
			return implode( ':', $parts );
		}

		// IPv4: zero out the last octet.
		$parts = explode( '.', $ip );
		if ( count( $parts ) === 4 ) {
			$parts[3] = '0';
			return implode( '.', $parts );
		}

		return $ip;
	}

	public static function get_client_ip() {
		$candidates = array( 'HTTP_X_FORWARDED_FOR', 'HTTP_CLIENT_IP', 'REMOTE_ADDR' );

		foreach ( $candidates as $key ) {
			if ( empty( $_SERVER[ $key ] ) ) {
				continue;
			}
			$value = sanitize_text_field( wp_unslash( $_SERVER[ $key ] ) );
			// X-Forwarded-For can be a comma separated list; use the first.
			$ip = trim( explode( ',', $value )[0] );
			if ( filter_var( $ip, FILTER_VALIDATE_IP ) ) {
				return $ip;
			}
		}

		return '';
	}

	public static function count_for_code( $code_id ) {
		global $wpdb;
		$table = QRST_DB::scans_table();
		return (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(*) FROM {$table} WHERE code_id = %d", $code_id ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}

	public static function unique_visitors_for_code( $code_id ) {
		global $wpdb;
		$table = QRST_DB::scans_table();
		return (int) $wpdb->get_var( $wpdb->prepare( "SELECT COUNT(DISTINCT ip_hash) FROM {$table} WHERE code_id = %d AND ip_hash != ''", $code_id ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}

	public static function get_for_code( $code_id, $args = array() ) {
		global $wpdb;
		$table = QRST_DB::scans_table();

		$defaults = array(
			'limit'  => 50,
			'offset' => 0,
		);
		$args = wp_parse_args( $args, $defaults );

		$sql = $wpdb->prepare(
			"SELECT * FROM {$table} WHERE code_id = %d ORDER BY scanned_at DESC LIMIT %d OFFSET %d", // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			$code_id,
			$args['limit'],
			$args['offset']
		);

		return $wpdb->get_results( $sql );
	}

	/**
	 * Scans-per-day for the last N days, for the dashboard sparkline/chart.
	 */
	public static function scans_per_day( $code_id = 0, $days = 30 ) {
		global $wpdb;
		$table = QRST_DB::scans_table();

		$where  = 'WHERE scanned_at >= %s';
		$params = array( gmdate( 'Y-m-d 00:00:00', strtotime( "-{$days} days" ) ) );

		if ( $code_id ) {
			$where   .= ' AND code_id = %d';
			$params[] = (int) $code_id;
		}

		$sql = "SELECT DATE(scanned_at) AS day, COUNT(*) AS total FROM {$table} {$where} GROUP BY DATE(scanned_at) ORDER BY day ASC";

		return $wpdb->get_results( $wpdb->prepare( $sql, $params ), ARRAY_A ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared
	}

	public static function top_breakdown( $code_id, $column, $limit = 5 ) {
		global $wpdb;
		$table = QRST_DB::scans_table();

		$allowed = array( 'country', 'city', 'device_type', 'browser', 'os' );
		if ( ! in_array( $column, $allowed, true ) ) {
			return array();
		}

		$where  = "WHERE {$column} != ''";
		$params = array();

		if ( $code_id ) {
			$where   .= ' AND code_id = %d';
			$params[] = (int) $code_id;
		}
		$params[] = (int) $limit;

		$sql = "SELECT {$column} AS label, COUNT(*) AS total FROM {$table} {$where} GROUP BY {$column} ORDER BY total DESC LIMIT %d";

		return $wpdb->get_results( $wpdb->prepare( $sql, $params ), ARRAY_A ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared, WordPress.DB.PreparedSQL.NotPrepared
	}

	public static function delete_older_than( $days ) {
		global $wpdb;
		$table = QRST_DB::scans_table();
		$cutoff = gmdate( 'Y-m-d 00:00:00', strtotime( "-{$days} days" ) );
		return $wpdb->query( $wpdb->prepare( "DELETE FROM {$table} WHERE scanned_at < %s", $cutoff ) ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}
}
