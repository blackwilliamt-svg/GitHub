<?php
/**
 * WP_List_Table showing individual scan events (the "who/where/when").
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! class_exists( 'WP_List_Table' ) ) {
	require_once ABSPATH . 'wp-admin/includes/class-wp-list-table.php';
}

class QRST_List_Table_Scans extends WP_List_Table {

	protected $code_id;

	public function __construct( $code_id = 0 ) {
		$this->code_id = (int) $code_id;

		parent::__construct(
			array(
				'singular' => 'scan',
				'plural'   => 'scans',
				'ajax'     => false,
			)
		);
	}

	public function get_columns() {
		$columns = array(
			'scanned_at'  => __( 'When', 'qr-scan-tracker' ),
			'location'    => __( 'Location', 'qr-scan-tracker' ),
			'device'      => __( 'Device / Browser', 'qr-scan-tracker' ),
			'who'         => __( 'Who', 'qr-scan-tracker' ),
			'referrer'    => __( 'Referrer', 'qr-scan-tracker' ),
		);

		if ( ! $this->code_id ) {
			$columns = array( 'code' => __( 'QR Code', 'qr-scan-tracker' ) ) + $columns;
		}

		return $columns;
	}

	public function prepare_items() {
		$per_page     = 30;
		$current_page = $this->get_pagenum();

		$this->items = QRST_Scans::get_for_code(
			$this->code_id,
			array(
				'limit'  => $per_page,
				'offset' => ( $current_page - 1 ) * $per_page,
			)
		);

		$total_items = $this->code_id ? QRST_Scans::count_for_code( $this->code_id ) : $this->count_all();

		$this->_column_headers = array( $this->get_columns(), array(), array() );

		$this->set_pagination_args(
			array(
				'total_items' => $total_items,
				'per_page'    => $per_page,
				'total_pages' => ceil( $total_items / $per_page ),
			)
		);
	}

	protected function count_all() {
		global $wpdb;
		$table = QRST_DB::scans_table();
		return (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table}" ); // phpcs:ignore WordPress.DB.PreparedSQL.InterpolatedNotPrepared
	}

	protected function column_default( $item, $column_name ) {
		return isset( $item->$column_name ) ? esc_html( $item->$column_name ) : '';
	}

	protected function column_code( $item ) {
		$code = QRST_Codes::get( $item->code_id );
		if ( ! $code ) {
			return '—';
		}
		$url = add_query_arg( array( 'page' => 'qrst-scans', 'code_id' => $code->id ), admin_url( 'admin.php' ) );
		return sprintf( '<a href="%s">%s</a>', esc_url( $url ), esc_html( $code->label ) );
	}

	protected function column_scanned_at( $item ) {
		$formatted = mysql2date( get_option( 'date_format' ) . ' ' . get_option( 'time_format' ), $item->scanned_at );
		return esc_html( $formatted );
	}

	protected function column_location( $item ) {
		$parts = array_filter( array( $item->city, $item->region, $item->country ) );
		if ( empty( $parts ) ) {
			return '<span class="description">' . esc_html__( 'Unknown', 'qr-scan-tracker' ) . '</span>';
		}

		$label = implode( ', ', $parts );

		if ( $item->latitude && $item->longitude ) {
			$map_url = sprintf( 'https://www.openstreetmap.org/?mlat=%1$s&mlon=%2$s#map=10/%1$s/%2$s', esc_attr( $item->latitude ), esc_attr( $item->longitude ) );
			return sprintf( '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>', esc_url( $map_url ), esc_html( $label ) );
		}

		return esc_html( $label );
	}

	protected function column_device( $item ) {
		$icon = array(
			'mobile'  => '📱',
			'tablet'  => '💻',
			'desktop' => '🖥️',
			'bot'     => '🤖',
		);
		$emoji = isset( $icon[ $item->device_type ] ) ? $icon[ $item->device_type ] : '❓';

		return sprintf(
			'%s %s / %s',
			$emoji,
			esc_html( $item->browser ?: __( 'Unknown browser', 'qr-scan-tracker' ) ),
			esc_html( $item->os ?: __( 'Unknown OS', 'qr-scan-tracker' ) )
		);
	}

	protected function column_who( $item ) {
		if ( ! empty( $item->wp_user_login ) ) {
			$user = get_user_by( 'id', $item->wp_user_id );
			$name = $user ? $user->display_name : $item->wp_user_login;
			return '<span class="qrst-badge qrst-badge-active">' . esc_html( $name ) . '</span>';
		}

		return '<span class="description">' . esc_html__( 'Anonymous', 'qr-scan-tracker' ) . '</span>';
	}

	protected function column_referrer( $item ) {
		if ( empty( $item->referrer ) ) {
			return '<span class="description">' . esc_html__( 'Direct scan', 'qr-scan-tracker' ) . '</span>';
		}
		$host = wp_parse_url( $item->referrer, PHP_URL_HOST );
		return sprintf( '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>', esc_url( $item->referrer ), esc_html( $host ? $host : $item->referrer ) );
	}

	public function no_items() {
		esc_html_e( 'No scans recorded yet.', 'qr-scan-tracker' );
	}
}
