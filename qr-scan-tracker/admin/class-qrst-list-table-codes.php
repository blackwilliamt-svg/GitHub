<?php
/**
 * WP_List_Table showing every QR code with its scan count.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( ! class_exists( 'WP_List_Table' ) ) {
	require_once ABSPATH . 'wp-admin/includes/class-wp-list-table.php';
}

class QRST_List_Table_Codes extends WP_List_Table {

	public function __construct() {
		parent::__construct(
			array(
				'singular' => 'qr_code',
				'plural'   => 'qr_codes',
				'ajax'     => false,
			)
		);
	}

	public function get_columns() {
		return array(
			'label'      => __( 'Label', 'qr-scan-tracker' ),
			'target_url' => __( 'Destination', 'qr-scan-tracker' ),
			'tracking'   => __( 'Tracking Link / QR', 'qr-scan-tracker' ),
			'scans'      => __( 'Scans', 'qr-scan-tracker' ),
			'status'     => __( 'Status', 'qr-scan-tracker' ),
			'created_at' => __( 'Created', 'qr-scan-tracker' ),
		);
	}

	protected function get_sortable_columns() {
		return array(
			'label'      => array( 'label', false ),
			'status'     => array( 'status', false ),
			'created_at' => array( 'created_at', true ),
		);
	}

	public function prepare_items() {
		$per_page     = 20;
		$current_page = $this->get_pagenum();
		$search       = isset( $_REQUEST['s'] ) ? sanitize_text_field( wp_unslash( $_REQUEST['s'] ) ) : '';
		$orderby      = isset( $_REQUEST['orderby'] ) ? sanitize_key( $_REQUEST['orderby'] ) : 'created_at';
		$order        = isset( $_REQUEST['order'] ) ? sanitize_key( $_REQUEST['order'] ) : 'desc';

		$total_items = QRST_Codes::count( $search );

		$this->items = QRST_Codes::get_all(
			array(
				'search'  => $search,
				'orderby' => $orderby,
				'order'   => $order,
				'limit'   => $per_page,
				'offset'  => ( $current_page - 1 ) * $per_page,
			)
		);

		$this->_column_headers = array( $this->get_columns(), array(), $this->get_sortable_columns() );

		$this->set_pagination_args(
			array(
				'total_items' => $total_items,
				'per_page'    => $per_page,
				'total_pages' => ceil( $total_items / $per_page ),
			)
		);
	}

	public function get_bulk_actions() {
		return array();
	}

	protected function column_default( $item, $column_name ) {
		return isset( $item->$column_name ) ? esc_html( $item->$column_name ) : '';
	}

	protected function column_label( $item ) {
		$edit_url   = add_query_arg( array( 'page' => 'qrst-add-new', 'id' => $item->id ), admin_url( 'admin.php' ) );
		$delete_url = wp_nonce_url(
			add_query_arg(
				array( 'action' => 'qrst_delete_code', 'id' => $item->id ),
				admin_url( 'admin-post.php' )
			),
			'qrst_delete_code_' . $item->id
		);
		$scans_url  = add_query_arg( array( 'page' => 'qrst-scans', 'code_id' => $item->id ), admin_url( 'admin.php' ) );

		$actions = array(
			'edit'   => sprintf( '<a href="%s">%s</a>', esc_url( $edit_url ), esc_html__( 'Edit', 'qr-scan-tracker' ) ),
			'scans'  => sprintf( '<a href="%s">%s</a>', esc_url( $scans_url ), esc_html__( 'View Scans', 'qr-scan-tracker' ) ),
			'delete' => sprintf( '<a href="%s" class="qrst-delete-link">%s</a>', esc_url( $delete_url ), esc_html__( 'Delete', 'qr-scan-tracker' ) ),
		);

		if ( $item->campaign ) {
			$label_html = sprintf( '<strong><a href="%s">%s</a></strong><br /><span class="description">%s</span>', esc_url( $edit_url ), esc_html( $item->label ), esc_html( $item->campaign ) );
		} else {
			$label_html = sprintf( '<strong><a href="%s">%s</a></strong>', esc_url( $edit_url ), esc_html( $item->label ) );
		}

		return $label_html . $this->row_actions( $actions );
	}

	protected function column_target_url( $item ) {
		$url = $item->target_url;
		$display = strlen( $url ) > 60 ? substr( $url, 0, 57 ) . '…' : $url;
		return sprintf( '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>', esc_url( $url ), esc_html( $display ) );
	}

	protected function column_tracking( $item ) {
		$tracking_url = QRST_Codes::tracking_url( $item );
		$image_url    = QRST_QR_Generator::image_url( $tracking_url, 90 );

		return sprintf(
			'<div class="qrst-mini-qr"><img src="%1$s" width="60" height="60" alt="" /><div><code>%2$s</code><br /><a href="%3$s" target="_blank">%4$s</a></div></div>',
			esc_url( $image_url ),
			esc_html( $tracking_url ),
			esc_url( $image_url ),
			esc_html__( 'Download PNG', 'qr-scan-tracker' )
		);
	}

	protected function column_scans( $item ) {
		$count = QRST_Scans::count_for_code( $item->id );
		$scans_url = add_query_arg( array( 'page' => 'qrst-scans', 'code_id' => $item->id ), admin_url( 'admin.php' ) );
		return sprintf( '<a href="%s">%s</a>', esc_url( $scans_url ), esc_html( number_format_i18n( $count ) ) );
	}

	protected function column_status( $item ) {
		$class = 'active' === $item->status ? 'qrst-badge-active' : 'qrst-badge-inactive';
		$label = 'active' === $item->status ? __( 'Active', 'qr-scan-tracker' ) : __( 'Inactive', 'qr-scan-tracker' );
		return sprintf( '<span class="qrst-badge %s">%s</span>', esc_attr( $class ), esc_html( $label ) );
	}

	protected function column_created_at( $item ) {
		return esc_html( mysql2date( get_option( 'date_format' ), $item->created_at ) );
	}

	public function no_items() {
		esc_html_e( 'No QR codes yet. Click "Add New" to create your first trackable QR code.', 'qr-scan-tracker' );
	}
}
