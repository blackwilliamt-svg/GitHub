<?php
/**
 * Admin UI: menu registration, page rendering, and form handlers.
 *
 * @package QR_Scan_Tracker
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QRST_Admin {

	const CAP = 'manage_options';

	public function register_menu() {
		$icon = 'data:image/svg+xml;base64,' . base64_encode(
			'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#a7aaad" d="M3 3h8v8H3V3zm2 2v4h4V5H5zm8-2h8v8h-8V3zm2 2v4h4V5h-4zM3 13h8v8H3v-8zm2 2v4h4v-4H5zm10-2h2v2h-2v-2zm4 0h2v2h-2v-2zm-4 4h2v2h-2v-2zm4 0h2v2h-2v-2zm-2 4h2v2h-2v-2zm-2-8h2v2h-2v-2z"/></svg>'
		);

		add_menu_page(
			__( 'QR Scan Tracker', 'qr-scan-tracker' ),
			__( 'QR Codes', 'qr-scan-tracker' ),
			self::CAP,
			'qr-scan-tracker',
			array( $this, 'render_list_page' ),
			$icon,
			26
		);

		add_submenu_page(
			'qr-scan-tracker',
			__( 'All QR Codes', 'qr-scan-tracker' ),
			__( 'All QR Codes', 'qr-scan-tracker' ),
			self::CAP,
			'qr-scan-tracker',
			array( $this, 'render_list_page' )
		);

		add_submenu_page(
			'qr-scan-tracker',
			__( 'Add New QR Code', 'qr-scan-tracker' ),
			__( 'Add New', 'qr-scan-tracker' ),
			self::CAP,
			'qrst-add-new',
			array( $this, 'render_edit_page' )
		);

		add_submenu_page(
			'qr-scan-tracker',
			__( 'Scan Log', 'qr-scan-tracker' ),
			__( 'Scan Log', 'qr-scan-tracker' ),
			self::CAP,
			'qrst-scans',
			array( $this, 'render_scans_page' )
		);

		add_submenu_page(
			'qr-scan-tracker',
			__( 'Settings', 'qr-scan-tracker' ),
			__( 'Settings', 'qr-scan-tracker' ),
			self::CAP,
			'qrst-settings',
			array( $this, 'render_settings_page' )
		);

		// Hide the "Add New" duplicate + keep "Scan Log" reachable only via row actions.
		remove_submenu_page( 'qr-scan-tracker', 'qrst-scans' );
	}

	public function enqueue_assets( $hook ) {
		if ( strpos( $hook, 'qr-scan-tracker' ) === false && strpos( $hook, 'qrst-' ) === false ) {
			return;
		}

		wp_enqueue_style( 'qrst-admin', QRST_PLUGIN_URL . 'admin/css/admin.css', array(), QRST_VERSION );
		wp_enqueue_script( 'qrst-admin', QRST_PLUGIN_URL . 'admin/js/admin.js', array( 'wp-api-fetch' ), QRST_VERSION, true );
		wp_localize_script(
			'qrst-admin',
			'QRST',
			array(
				'restUrl' => esc_url_raw( rest_url( 'qrst/v1/' ) ),
				'nonce'   => wp_create_nonce( 'wp_rest' ),
				'i18n'    => array(
					'confirmDelete' => __( 'Delete this QR code and all of its scan history? This cannot be undone.', 'qr-scan-tracker' ),
				),
			)
		);
	}

	public function maybe_permalink_notice() {
		if ( ! current_user_can( self::CAP ) || get_option( 'permalink_structure' ) ) {
			return;
		}

		$screen = get_current_screen();
		if ( ! $screen || ( false === strpos( $screen->id, 'qr-scan-tracker' ) && false === strpos( $screen->id, 'qrst-' ) ) ) {
			return;
		}

		printf(
			'<div class="notice notice-warning"><p>%s</p></div>',
			wp_kses_post(
				sprintf(
					/* translators: %s: link to Permalinks settings screen */
					__( 'QR Scan Tracker needs "pretty" permalinks to build working tracking links. Please choose any option other than "Plain" on the %s screen.', 'qr-scan-tracker' ),
					'<a href="' . esc_url( admin_url( 'options-permalink.php' ) ) . '">' . esc_html__( 'Permalinks', 'qr-scan-tracker' ) . '</a>'
				)
			)
		);
	}

	public function plugin_action_links( $links ) {
		$settings_link = '<a href="' . esc_url( admin_url( 'admin.php?page=qrst-settings' ) ) . '">' . esc_html__( 'Settings', 'qr-scan-tracker' ) . '</a>';
		array_unshift( $links, $settings_link );
		return $links;
	}

	/* ------------------------------------------------------------------ */
	/* Pages                                                              */
	/* ------------------------------------------------------------------ */

	public function render_list_page() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to access this page.', 'qr-scan-tracker' ) );
		}

		require_once QRST_PLUGIN_DIR . 'admin/class-qrst-list-table-codes.php';
		$list_table = new QRST_List_Table_Codes();
		$list_table->prepare_items();

		include QRST_PLUGIN_DIR . 'admin/partials/list-codes.php';
	}

	public function render_edit_page() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to access this page.', 'qr-scan-tracker' ) );
		}

		$code_id = isset( $_GET['id'] ) ? absint( $_GET['id'] ) : 0;
		$code    = $code_id ? QRST_Codes::get( $code_id ) : null;

		if ( $code_id && ! $code ) {
			wp_die( esc_html__( 'QR code not found.', 'qr-scan-tracker' ) );
		}

		include QRST_PLUGIN_DIR . 'admin/partials/edit-code.php';
	}

	public function render_scans_page() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to access this page.', 'qr-scan-tracker' ) );
		}

		$code_id = isset( $_GET['code_id'] ) ? absint( $_GET['code_id'] ) : 0;
		$code    = $code_id ? QRST_Codes::get( $code_id ) : null;

		if ( $code_id && ! $code ) {
			wp_die( esc_html__( 'QR code not found.', 'qr-scan-tracker' ) );
		}

		require_once QRST_PLUGIN_DIR . 'admin/class-qrst-list-table-scans.php';
		$list_table = new QRST_List_Table_Scans( $code_id );
		$list_table->prepare_items();

		include QRST_PLUGIN_DIR . 'admin/partials/view-scans.php';
	}

	public function render_settings_page() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to access this page.', 'qr-scan-tracker' ) );
		}

		$settings = qrst_get_settings();
		include QRST_PLUGIN_DIR . 'admin/partials/settings.php';
	}

	/* ------------------------------------------------------------------ */
	/* Form handlers                                                      */
	/* ------------------------------------------------------------------ */

	public function handle_save_code() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to do that.', 'qr-scan-tracker' ) );
		}
		check_admin_referer( 'qrst_save_code' );

		$id     = isset( $_POST['id'] ) ? absint( $_POST['id'] ) : 0;
		$label  = isset( $_POST['label'] ) ? sanitize_text_field( wp_unslash( $_POST['label'] ) ) : '';
		$url    = isset( $_POST['target_url'] ) ? esc_url_raw( wp_unslash( $_POST['target_url'] ) ) : '';
		$status = isset( $_POST['status'] ) && 'inactive' === $_POST['status'] ? 'inactive' : 'active';
		$camp   = isset( $_POST['campaign'] ) ? sanitize_text_field( wp_unslash( $_POST['campaign'] ) ) : '';
		$slug   = isset( $_POST['slug'] ) ? sanitize_title( wp_unslash( $_POST['slug'] ) ) : '';

		if ( '' === $label || '' === $url || ! filter_var( $url, FILTER_VALIDATE_URL ) ) {
			$redirect_args = array_filter(
				array(
					'page'       => 'qrst-add-new',
					'id'         => $id ? $id : null,
					'qrst_error' => 'invalid',
				)
			);
			wp_safe_redirect( add_query_arg( $redirect_args, admin_url( 'admin.php' ) ) );
			exit;
		}

		$data = array(
			'label'      => $label,
			'target_url' => $url,
			'status'     => $status,
			'campaign'   => $camp,
		);
		if ( $slug ) {
			$data['slug'] = $slug;
		}

		if ( $id ) {
			QRST_Codes::update( $id, $data );
		} else {
			$id = QRST_Codes::create( $data );
		}

		wp_safe_redirect( add_query_arg( array( 'page' => 'qr-scan-tracker', 'qrst_saved' => 1 ), admin_url( 'admin.php' ) ) );
		exit;
	}

	public function handle_delete_code() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to do that.', 'qr-scan-tracker' ) );
		}

		$id = isset( $_GET['id'] ) ? absint( $_GET['id'] ) : 0;
		check_admin_referer( 'qrst_delete_code_' . $id );

		if ( $id ) {
			QRST_Codes::delete( $id );
		}

		wp_safe_redirect( add_query_arg( array( 'page' => 'qr-scan-tracker', 'qrst_deleted' => 1 ), admin_url( 'admin.php' ) ) );
		exit;
	}

	public function handle_save_settings() {
		if ( ! current_user_can( self::CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to do that.', 'qr-scan-tracker' ) );
		}
		check_admin_referer( 'qrst_save_settings' );

		$roles = isset( $_POST['exclude_roles'] ) ? array_map( 'sanitize_key', (array) wp_unslash( $_POST['exclude_roles'] ) ) : array();

		$redirect_base = isset( $_POST['redirect_base'] ) ? sanitize_text_field( wp_unslash( $_POST['redirect_base'] ) ) : 'qr/go';
		$redirect_base = trim( $redirect_base, '/' );
		if ( '' === $redirect_base ) {
			$redirect_base = 'qr/go';
		}

		$settings = array(
			'collect_location' => ! empty( $_POST['collect_location'] ) ? 1 : 0,
			'geo_provider'     => isset( $_POST['geo_provider'] ) && 'ip_api_com' === $_POST['geo_provider'] ? 'ip_api_com' : 'ipapi_co',
			'store_raw_ip'     => ! empty( $_POST['store_raw_ip'] ) ? 1 : 0,
			'anonymize_ip'     => ! empty( $_POST['anonymize_ip'] ) ? 1 : 0,
			'retention_days'   => isset( $_POST['retention_days'] ) ? max( 0, absint( $_POST['retention_days'] ) ) : 0,
			'redirect_base'    => $redirect_base,
			'track_logged_in'  => ! empty( $_POST['track_logged_in'] ) ? 1 : 0,
			'exclude_roles'    => $roles,
		);

		update_option( 'qrst_delete_data_on_uninstall', ! empty( $_POST['delete_data_on_uninstall'] ) ? 1 : 0 );

		$old = qrst_get_settings();
		update_option( 'qrst_settings', $settings );

		if ( $old['redirect_base'] !== $settings['redirect_base'] ) {
			flush_rewrite_rules();
		}

		wp_safe_redirect( add_query_arg( array( 'page' => 'qrst-settings', 'qrst_saved' => 1 ), admin_url( 'admin.php' ) ) );
		exit;
	}
}
