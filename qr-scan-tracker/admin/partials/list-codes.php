<?php
/**
 * View: list of all QR codes.
 *
 * @package QR_Scan_Tracker
 * @var QRST_List_Table_Codes $list_table
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}
?>
<div class="wrap qrst-wrap">
	<h1 class="wp-heading-inline"><?php esc_html_e( 'QR Scan Tracker', 'qr-scan-tracker' ); ?></h1>
	<a href="<?php echo esc_url( admin_url( 'admin.php?page=qrst-add-new' ) ); ?>" class="page-title-action"><?php esc_html_e( 'Add New', 'qr-scan-tracker' ); ?></a>
	<hr class="wp-header-end" />

	<?php if ( isset( $_GET['qrst_saved'] ) ) : ?>
		<div class="notice notice-success is-dismissible"><p><?php esc_html_e( 'QR code saved.', 'qr-scan-tracker' ); ?></p></div>
	<?php endif; ?>
	<?php if ( isset( $_GET['qrst_deleted'] ) ) : ?>
		<div class="notice notice-success is-dismissible"><p><?php esc_html_e( 'QR code deleted.', 'qr-scan-tracker' ); ?></p></div>
	<?php endif; ?>

	<form method="get">
		<input type="hidden" name="page" value="qr-scan-tracker" />
		<?php $list_table->search_box( __( 'Search QR codes', 'qr-scan-tracker' ), 'qrst-search' ); ?>
		<?php $list_table->display(); ?>
	</form>
</div>
