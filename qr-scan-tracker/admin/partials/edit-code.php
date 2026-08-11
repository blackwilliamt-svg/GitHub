<?php
/**
 * View: create/edit a QR code.
 *
 * @package QR_Scan_Tracker
 * @var object|null $code
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$is_edit = ! empty( $code );
?>
<div class="wrap qrst-wrap">
	<h1><?php echo $is_edit ? esc_html__( 'Edit QR Code', 'qr-scan-tracker' ) : esc_html__( 'Add New QR Code', 'qr-scan-tracker' ); ?></h1>

	<?php if ( isset( $_GET['qrst_error'] ) ) : ?>
		<div class="notice notice-error"><p><?php esc_html_e( 'Please provide a label and a valid destination URL.', 'qr-scan-tracker' ); ?></p></div>
	<?php endif; ?>

	<div class="qrst-edit-layout">
		<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" class="qrst-edit-form">
			<?php wp_nonce_field( 'qrst_save_code' ); ?>
			<input type="hidden" name="action" value="qrst_save_code" />
			<?php if ( $is_edit ) : ?>
				<input type="hidden" name="id" value="<?php echo esc_attr( $code->id ); ?>" />
			<?php endif; ?>

			<table class="form-table" role="presentation">
				<tr>
					<th><label for="qrst-label"><?php esc_html_e( 'Label', 'qr-scan-tracker' ); ?></label></th>
					<td>
						<input type="text" id="qrst-label" name="label" class="regular-text" required
							value="<?php echo esc_attr( $is_edit ? $code->label : '' ); ?>"
							placeholder="<?php esc_attr_e( 'e.g. Storefront window poster', 'qr-scan-tracker' ); ?>" />
						<p class="description"><?php esc_html_e( 'Internal name so you recognize this code in your reports.', 'qr-scan-tracker' ); ?></p>
					</td>
				</tr>
				<tr>
					<th><label for="qrst-target-url"><?php esc_html_e( 'Destination URL', 'qr-scan-tracker' ); ?></label></th>
					<td>
						<input type="url" id="qrst-target-url" name="target_url" class="regular-text" required
							value="<?php echo esc_attr( $is_edit ? $code->target_url : '' ); ?>"
							placeholder="https://example.com/landing-page" />
						<p class="description"><?php esc_html_e( 'Where the scanner ends up after being tracked. Can be any URL, on or off this site.', 'qr-scan-tracker' ); ?></p>
					</td>
				</tr>
				<tr>
					<th><label for="qrst-campaign"><?php esc_html_e( 'Campaign / Notes', 'qr-scan-tracker' ); ?></label></th>
					<td>
						<input type="text" id="qrst-campaign" name="campaign" class="regular-text"
							value="<?php echo esc_attr( $is_edit ? $code->campaign : '' ); ?>"
							placeholder="<?php esc_attr_e( 'e.g. Spring 2026 flyer run', 'qr-scan-tracker' ); ?>" />
					</td>
				</tr>
				<?php if ( $is_edit ) : ?>
				<tr>
					<th><label for="qrst-slug"><?php esc_html_e( 'Tracking slug', 'qr-scan-tracker' ); ?></label></th>
					<td>
						<input type="text" id="qrst-slug" name="slug" class="regular-text"
							value="<?php echo esc_attr( $code->slug ); ?>" />
						<p class="description">
							<?php
							printf(
								/* translators: %s: full tracking URL */
								esc_html__( 'Changing this changes the QR code\'s tracking URL: %s', 'qr-scan-tracker' ),
								'<code>' . esc_html( QRST_Codes::tracking_url( $code ) ) . '</code>'
							);
							?>
							<?php esc_html_e( 'Any QR codes you already printed with the old link will stop working — only rename before distributing.', 'qr-scan-tracker' ); ?>
						</p>
					</td>
				</tr>
				<?php endif; ?>
				<tr>
					<th><?php esc_html_e( 'Status', 'qr-scan-tracker' ); ?></th>
					<td>
						<label>
							<input type="radio" name="status" value="active" <?php checked( ! $is_edit || 'active' === $code->status ); ?> />
							<?php esc_html_e( 'Active', 'qr-scan-tracker' ); ?>
						</label>
						<br />
						<label>
							<input type="radio" name="status" value="inactive" <?php checked( $is_edit && 'inactive' === $code->status ); ?> />
							<?php esc_html_e( 'Inactive (scans will show a "not available" page)', 'qr-scan-tracker' ); ?>
						</label>
					</td>
				</tr>
			</table>

			<?php submit_button( $is_edit ? __( 'Save Changes', 'qr-scan-tracker' ) : __( 'Create QR Code', 'qr-scan-tracker' ) ); ?>
		</form>

		<?php if ( $is_edit ) :
			$tracking_url = QRST_Codes::tracking_url( $code );
			$image_url    = QRST_QR_Generator::image_url( $tracking_url, 260 );
			?>
			<div class="qrst-edit-sidebar">
				<div class="qrst-card">
					<h2><?php esc_html_e( 'Your QR Code', 'qr-scan-tracker' ); ?></h2>
					<img src="<?php echo esc_url( $image_url ); ?>" width="220" height="220" alt="<?php echo esc_attr( $code->label ); ?>" />
					<p>
						<a class="button button-secondary" href="<?php echo esc_url( $image_url ); ?>" download="qr-<?php echo esc_attr( $code->slug ); ?>.png"><?php esc_html_e( 'Download PNG', 'qr-scan-tracker' ); ?></a>
					</p>
					<p>
						<label><?php esc_html_e( 'Tracking link', 'qr-scan-tracker' ); ?></label><br />
						<input type="text" readonly class="widefat" onclick="this.select();" value="<?php echo esc_attr( $tracking_url ); ?>" />
					</p>
					<p>
						<a href="<?php echo esc_url( add_query_arg( array( 'page' => 'qrst-scans', 'code_id' => $code->id ), admin_url( 'admin.php' ) ) ); ?>" class="button button-primary">
							<?php esc_html_e( 'View Scan Activity', 'qr-scan-tracker' ); ?>
						</a>
					</p>
					<p class="description">
						<?php esc_html_e( 'Print this image, or embed it anywhere with the shortcode:', 'qr-scan-tracker' ); ?>
						<br /><code>[qrst_code id="<?php echo esc_html( $code->id ); ?>"]</code>
					</p>
				</div>
			</div>
		<?php endif; ?>
	</div>
</div>
