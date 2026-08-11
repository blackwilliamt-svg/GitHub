<?php
/**
 * Small, dependency-free User-Agent parser. It doesn't aim to be as
 * exhaustive as a full library — it aims to correctly bucket the vast
 * majority of real-world traffic into device type / browser / OS so the
 * "who's scanning" report is useful at a glance.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_User_Agent_Parser {

	/**
	 * @param string $ua Raw User-Agent header.
	 * @return array{device_type:string,browser:string,os:string,is_bot:bool}
	 */
	public static function parse( $ua ) {
		$ua = (string) $ua;

		return array(
			'is_bot'      => self::is_bot( $ua ),
			'device_type' => self::device_type( $ua ),
			'browser'     => self::browser( $ua ),
			'os'          => self::os( $ua ),
		);
	}

	protected static function is_bot( $ua ) {
		return (bool) preg_match( '/bot|crawl|spider|slurp|facebookexternalhit|preview|whatsapp|telegrambot|curl|wget|python-requests|headless/i', $ua );
	}

	protected static function device_type( $ua ) {
		if ( self::is_bot( $ua ) ) {
			return 'bot';
		}
		if ( preg_match( '/iPad|Tablet(?!.*Mobile)|Nexus (7|9|10)/i', $ua ) ) {
			return 'tablet';
		}
		if ( preg_match( '/Mobi|iPhone|iPod|Android.*Mobile|Windows Phone|BlackBerry/i', $ua ) ) {
			return 'mobile';
		}
		if ( '' === trim( $ua ) ) {
			return 'unknown';
		}
		return 'desktop';
	}

	protected static function browser( $ua ) {
		$map = array(
			'EdgA|Edge|Edg/'        => 'Edge',
			'OPR/|Opera'            => 'Opera',
			'SamsungBrowser'        => 'Samsung Internet',
			'UCBrowser'             => 'UC Browser',
			'FBAN|FBAV'             => 'Facebook App',
			'Instagram'             => 'Instagram App',
			'MicroMessenger'        => 'WeChat',
			'CriOS|Chrome'          => 'Chrome',
			'FxiOS|Firefox'         => 'Firefox',
			'Version.*Safari|Safari' => 'Safari',
			'MSIE|Trident'          => 'Internet Explorer',
		);

		foreach ( $map as $pattern => $name ) {
			if ( preg_match( '/' . $pattern . '/i', $ua ) ) {
				return $name;
			}
		}

		return $ua ? 'Other' : 'Unknown';
	}

	protected static function os( $ua ) {
		$map = array(
			'Windows NT 10\.0'   => 'Windows 10/11',
			'Windows NT 6\.3'    => 'Windows 8.1',
			'Windows NT 6\.2'    => 'Windows 8',
			'Windows NT 6\.1'    => 'Windows 7',
			'Windows'            => 'Windows',
			'iPhone|iPad|iPod'   => 'iOS',
			'Mac OS X'           => 'macOS',
			'Android'            => 'Android',
			'CrOS'               => 'Chrome OS',
			'Linux'              => 'Linux',
		);

		foreach ( $map as $pattern => $name ) {
			if ( preg_match( '/' . $pattern . '/i', $ua ) ) {
				return $name;
			}
		}

		return $ua ? 'Other' : 'Unknown';
	}
}
