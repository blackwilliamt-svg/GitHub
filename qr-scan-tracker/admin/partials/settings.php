<?php
/**
 * View: settings page.
 *
 * @package QR_Scan_Tracker
 * @var array $settings
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$roles = wp_roles()->get_names();
?>
<div class="wrap qrst-wrap">
	<h1><?php esc_html_e( 'QR Scan Tracker Settings', 'qr-scan-tracker' ); ?></h1>

	<?php if ( isset( $_GET['qrst_saved'] ) ) : ?>
		<div class="notice notice-success is-dismissible"><p><?php esc_html_e( 'Settings saved.', 'qr-scan-tracker' ); ?></p></div>
	<?php endif; ?>

	<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
		<?php wp_nonce_field( 'qrst_save_settings' ); ?>
		<input type="hidden" name="action" value="qrst_save_settings" />

		<h2 class="title"><?php esc_html_e( 'Location Tracking', 'qr-scan-tracker' ); ?></h2>
		<table class="form-table" role="presentation">
			<tr>
				<th><?php esc_html_e( 'Collect approximate location', 'qr-scan-tracker' ); ?></th>
				<td>
					<label>
						<input type="checkbox" name="collect_location" value="1" <?php checked( ! empty( $settings['collect_location'] ) ); ?> />
						<?php esc_html_e( 'Look up country/region/city from the scanner\'s IP address', 'qr-scan-tracker' ); ?>
					</label>
					<p class="description"><?php esc_html_e( 'Location is estimated from the IP address at the time of the scan, via an outside geolocation service. Accuracy is city-level at best, and can be off for mobile carriers/VPNs.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
			<tr>
				<th><label for="geo_provider"><?php esc_html_e( 'Geolocation provider', 'qr-scan-tracker' ); ?></label></th>
				<td>
					<select name="geo_provider" id="geo_provider">
						<option value="ipapi_co" <?php selected( $settings['geo_provider'], 'ipapi_co' ); ?>>ipapi.co</option>
						<option value="ip_api_com" <?php selected( $settings['geo_provider'], 'ip_api_com' ); ?>>ip-api.com</option>
					</select>
					<p class="description"><?php esc_html_e( 'Both are free, keyless services suitable for low/medium traffic. For high-volume sites, use the qrst_pre_geolocation_result filter to plug in your own GeoIP database.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
		</table>

		<h2 class="title"><?php esc_html_e( 'Privacy', 'qr-scan-tracker' ); ?></h2>
		<table class="form-table" role="presentation">
			<tr>
				<th><?php esc_html_e( 'Store raw IP addresses', 'qr-scan-tracker' ); ?></th>
				<td>
					<label>
						<input type="checkbox" name="store_raw_ip" value="1" <?php checked( ! empty( $settings['store_raw_ip'] ) ); ?> />
						<?php esc_html_e( 'Keep the scanner\'s IP address on each scan record', 'qr-scan-tracker' ); ?>
					</label>
					<p class="description"><?php esc_html_e( 'Off by default. Even with this off, a one-way hash of the IP is kept briefly to count unique scanners — no reversible IP is stored.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
			<tr>
				<th><?php esc_html_e( 'Anonymize stored IPs', 'qr-scan-tracker' ); ?></th>
				<td>
					<label>
						<input type="checkbox" name="anonymize_ip" value="1" <?php checked( ! empty( $settings['anonymize_ip'] ) ); ?> />
						<?php esc_html_e( 'Mask the last part of the IP address before storing it (only applies if raw IPs are stored above)', 'qr-scan-tracker' ); ?>
					</label>
				</td>
			</tr>
			<tr>
				<th><label for="retention_days"><?php esc_html_e( 'Auto-delete scans after', 'qr-scan-tracker' ); ?></label></th>
				<td>
					<input type="number" min="0" step="1" id="retention_days" name="retention_days" class="small-text" value="<?php echo esc_attr( $settings['retention_days'] ); ?>" />
					<?php esc_html_e( 'days (0 = keep forever)', 'qr-scan-tracker' ); ?>
					<p class="description"><?php esc_html_e( 'A daily cleanup job removes scan records older than this.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
		</table>

		<h2 class="title"><?php esc_html_e( 'Identifying Logged-In Scanners', 'qr-scan-tracker' ); ?></h2>
		<table class="form-table" role="presentation">
			<tr>
				<th><?php esc_html_e( 'Track logged-in WordPress users', 'qr-scan-tracker' ); ?></th>
				<td>
					<label>
						<input type="checkbox" name="track_logged_in" value="1" <?php checked( ! empty( $settings['track_logged_in'] ) ); ?> />
						<?php esc_html_e( 'If the person scanning is already logged into this site (e.g. staff badges, member cards), record their username', 'qr-scan-tracker' ); ?>
					</label>
				</td>
			</tr>
			<tr>
				<th><?php esc_html_e( 'Never identify these roles', 'qr-scan-tracker' ); ?></th>
				<td>
					<?php foreach ( $roles as $role_key => $role_name ) : ?>
						<label style="display:block;">
							<input type="checkbox" name="exclude_roles[]" value="<?php echo esc_attr( $role_key ); ?>" <?php checked( in_array( $role_key, (array) $settings['exclude_roles'], true ) ); ?> />
							<?php echo esc_html( $role_name ); ?>
						</label>
					<?php endforeach; ?>
					<p class="description"><?php esc_html_e( 'Scans by these roles are still counted, just recorded as anonymous.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
		</table>

		<h2 class="title"><?php esc_html_e( 'Tracking Links', 'qr-scan-tracker' ); ?></h2>
		<table class="form-table" role="presentation">
			<tr>
				<th><label for="redirect_base"><?php esc_html_e( 'URL prefix', 'qr-scan-tracker' ); ?></label></th>
				<td>
					<code><?php echo esc_html( home_url( '/' ) ); ?></code>
					<input type="text" id="redirect_base" name="redirect_base" value="<?php echo esc_attr( $settings['redirect_base'] ); ?>" class="regular-text" style="width:180px;" />
					<code>/your-slug/</code>
					<p class="description"><?php esc_html_e( 'Changing this updates every QR code\'s tracking link — codes you already printed will stop working unless you keep the old prefix too.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
		</table>

		<h2 class="title"><?php esc_html_e( 'Uninstalling', 'qr-scan-tracker' ); ?></h2>
		<table class="form-table" role="presentation">
			<tr>
				<th><?php esc_html_e( 'Delete all data on uninstall', 'qr-scan-tracker' ); ?></th>
				<td>
					<label>
						<input type="checkbox" name="delete_data_on_uninstall" value="1" <?php checked( ! empty( get_option( 'qrst_delete_data_on_uninstall' ) ) ); ?> />
						<?php esc_html_e( 'Permanently remove all QR codes, scan history, and settings when this plugin is deleted from the Plugins screen', 'qr-scan-tracker' ); ?>
					</label>
					<p class="description"><?php esc_html_e( 'Off by default, so deactivating/deleting by accident never loses your scan history.', 'qr-scan-tracker' ); ?></p>
				</td>
			</tr>
		</table>

		<?php submit_button( __( 'Save Settings', 'qr-scan-tracker' ) ); ?>
	</form>
</div>
