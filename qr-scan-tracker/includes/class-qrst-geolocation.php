<?php
/**
 * Resolves an IP address to an approximate location (country/region/city
 * + lat/lng) using a remote geolocation API, with a persistent cache so
 * the same IP is never looked up twice.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Geolocation {

	/**
	 * Look up a location for an IP address. Returns an associative array
	 * with country/country_code/region/city/latitude/longitude — all
	 * empty strings / null when unknown or lookups are disabled.
	 */
	public static function locate( $ip ) {
		$empty = array(
			'country'      => '',
			'country_code' => '',
			'region'       => '',
			'city'         => '',
			'latitude'     => null,
			'longitude'    => null,
		);

		if ( empty( $ip ) || ! self::should_locate() ) {
			return $empty;
		}

		if ( self::is_private_ip( $ip ) ) {
			return $empty;
		}

		$ip_hash = hash( 'sha256', $ip . wp_salt( 'auth' ) );

		$cached = self::get_cached( $ip_hash );
		if ( null !== $cached ) {
			return $cached;
		}

		$result = self::lookup_remote( $ip );
		self::set_cached( $ip_hash, $result );

		return $result;
	}

	protected static function should_locate() {
		$settings = qrst_get_settings();
		return ! empty( $settings['collect_location'] );
	}

	protected static function is_private_ip( $ip ) {
		return false === filter_var(
			$ip,
			FILTER_VALIDATE_IP,
			FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE
		);
	}

	protected static function get_cached( $ip_hash ) {
		global $wpdb;

		$table = QRST_DB::geo_cache_table();
		$row   = $wpdb->get_row(
			$wpdb->prepare( "SELECT * FROM {$table} WHERE ip_hash = %s", $ip_hash ), // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
			ARRAY_A
		);

		if ( ! $row ) {
			return null;
		}

		return array(
			'country'      => $row['country'],
			'country_code' => $row['country_code'],
			'region'       => $row['region'],
			'city'         => $row['city'],
			'latitude'     => $row['latitude'],
			'longitude'    => $row['longitude'],
		);
	}

	protected static function set_cached( $ip_hash, $data ) {
		global $wpdb;

		$table = QRST_DB::geo_cache_table();
		$wpdb->replace(
			$table,
			array(
				'ip_hash'      => $ip_hash,
				'country'      => $data['country'],
				'country_code' => $data['country_code'],
				'region'       => $data['region'],
				'city'         => $data['city'],
				'latitude'     => $data['latitude'],
				'longitude'    => $data['longitude'],
				'cached_at'    => current_time( 'mysql' ),
			)
		);
	}

	/**
	 * Query the configured remote geolocation provider. Providers are
	 * intentionally free / keyless by default (ipapi.co) but a site can
	 * switch to ip-api.com or supply a custom endpoint via the
	 * `qrst_geolocation_result` filter instead of calling out at all.
	 */
	protected static function lookup_remote( $ip ) {
		$empty = array(
			'country'      => '',
			'country_code' => '',
			'region'       => '',
			'city'         => '',
			'latitude'     => null,
			'longitude'    => null,
		);

		/**
		 * Allows completely overriding/short-circuiting the remote lookup,
		 * e.g. to plug in a local GeoIP database instead of an HTTP call.
		 */
		$pre = apply_filters( 'qrst_pre_geolocation_result', null, $ip );
		if ( is_array( $pre ) ) {
			return wp_parse_args( $pre, $empty );
		}

		$settings = qrst_get_settings();
		$provider = isset( $settings['geo_provider'] ) ? $settings['geo_provider'] : 'ipapi_co';

		switch ( $provider ) {
			case 'ip_api_com':
				$url = 'http://ip-api.com/json/' . rawurlencode( $ip ) . '?fields=status,country,countryCode,regionName,city,lat,lon';
				break;
			case 'ipapi_co':
			default:
				$url = 'https://ipapi.co/' . rawurlencode( $ip ) . '/json/';
				break;
		}

		$response = wp_remote_get( $url, array( 'timeout' => 4 ) );

		if ( is_wp_error( $response ) || 200 !== wp_remote_retrieve_response_code( $response ) ) {
			return $empty;
		}

		$body = json_decode( wp_remote_retrieve_body( $response ), true );
		if ( ! is_array( $body ) ) {
			return $empty;
		}

		if ( 'ip_api_com' === $provider ) {
			if ( empty( $body['status'] ) || 'success' !== $body['status'] ) {
				return $empty;
			}
			$result = array(
				'country'      => isset( $body['country'] ) ? sanitize_text_field( $body['country'] ) : '',
				'country_code' => isset( $body['countryCode'] ) ? sanitize_text_field( $body['countryCode'] ) : '',
				'region'       => isset( $body['regionName'] ) ? sanitize_text_field( $body['regionName'] ) : '',
				'city'         => isset( $body['city'] ) ? sanitize_text_field( $body['city'] ) : '',
				'latitude'     => isset( $body['lat'] ) ? (float) $body['lat'] : null,
				'longitude'    => isset( $body['lon'] ) ? (float) $body['lon'] : null,
			);
		} else {
			if ( ! empty( $body['error'] ) ) {
				return $empty;
			}
			$result = array(
				'country'      => isset( $body['country_name'] ) ? sanitize_text_field( $body['country_name'] ) : '',
				'country_code' => isset( $body['country_code'] ) ? sanitize_text_field( $body['country_code'] ) : '',
				'region'       => isset( $body['region'] ) ? sanitize_text_field( $body['region'] ) : '',
				'city'         => isset( $body['city'] ) ? sanitize_text_field( $body['city'] ) : '',
				'latitude'     => isset( $body['latitude'] ) ? (float) $body['latitude'] : null,
				'longitude'    => isset( $body['longitude'] ) ? (float) $body['longitude'] : null,
			);
		}

		return apply_filters( 'qrst_geolocation_result', $result, $ip, $body );
	}
}
