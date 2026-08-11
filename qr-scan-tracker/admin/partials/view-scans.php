<?php
/**
 * View: scan activity report, either for one QR code or across all of them.
 *
 * @package QR_Scan_Tracker
 * @var object|null              $code
 * @var int                      $code_id
 * @var QRST_List_Table_Scans    $list_table
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

$total   = QRST_Scans::count_for_code( $code_id );
$unique  = QRST_Scans::unique_visitors_for_code( $code_id );
$countries = QRST_Scans::top_breakdown( $code_id, 'country', 5 );
$devices   = QRST_Scans::top_breakdown( $code_id, 'device_type', 5 );

$export_url = wp_nonce_url(
	add_query_arg(
		array_filter( array( 'action' => 'qrst_export_csv', 'code_id' => $code_id ) ),
		admin_url( 'admin-post.php' )
	),
	'qrst_export_csv'
);
?>
<div class="wrap qrst-wrap">
	<h1>
		<?php
		if ( $code ) {
			printf( esc_html__( 'Scan Activity: %s', 'qr-scan-tracker' ), esc_html( $code->label ) );
		} else {
			esc_html_e( 'Scan Activity: All QR Codes', 'qr-scan-tracker' );
		}
		?>
	</h1>

	<p>
		<a href="<?php echo esc_url( admin_url( 'admin.php?page=qr-scan-tracker' ) ); ?>">&larr; <?php esc_html_e( 'Back to all QR codes', 'qr-scan-tracker' ); ?></a>
		<a href="<?php echo esc_url( $export_url ); ?>" class="button" style="margin-left: 12px;"><?php esc_html_e( 'Export CSV', 'qr-scan-tracker' ); ?></a>
	</p>

	<div class="qrst-stat-cards">
		<div class="qrst-stat-card">
			<span class="qrst-stat-number"><?php echo esc_html( number_format_i18n( $total ) ); ?></span>
			<span class="qrst-stat-label"><?php esc_html_e( 'Total Scans', 'qr-scan-tracker' ); ?></span>
		</div>
		<div class="qrst-stat-card">
			<span class="qrst-stat-number"><?php echo esc_html( number_format_i18n( $unique ) ); ?></span>
			<span class="qrst-stat-label"><?php esc_html_e( 'Unique Devices', 'qr-scan-tracker' ); ?></span>
		</div>
		<div class="qrst-stat-card">
			<span class="qrst-stat-number"><?php echo esc_html( $countries ? $countries[0]['label'] : '—' ); ?></span>
			<span class="qrst-stat-label"><?php esc_html_e( 'Top Country', 'qr-scan-tracker' ); ?></span>
		</div>
		<div class="qrst-stat-card">
			<span class="qrst-stat-number"><?php echo esc_html( $devices ? ucfirst( $devices[0]['label'] ) : '—' ); ?></span>
			<span class="qrst-stat-label"><?php esc_html_e( 'Top Device', 'qr-scan-tracker' ); ?></span>
		</div>
	</div>

	<div class="qrst-report-grid">
		<div class="qrst-card qrst-chart-card">
			<h2><?php esc_html_e( 'Scans Over Time (last 30 days)', 'qr-scan-tracker' ); ?></h2>
			<canvas id="qrst-scans-chart" data-code-id="<?php echo esc_attr( $code_id ); ?>" height="90"></canvas>
		</div>
		<div class="qrst-card">
			<h2><?php esc_html_e( 'Top Locations', 'qr-scan-tracker' ); ?></h2>
			<?php if ( $countries ) : ?>
				<ul class="qrst-breakdown-list">
					<?php foreach ( $countries as $row ) : ?>
						<li><span><?php echo esc_html( $row['label'] ); ?></span><strong><?php echo esc_html( number_format_i18n( $row['total'] ) ); ?></strong></li>
					<?php endforeach; ?>
				</ul>
			<?php else : ?>
				<p class="description"><?php esc_html_e( 'No location data yet.', 'qr-scan-tracker' ); ?></p>
			<?php endif; ?>
		</div>
		<div class="qrst-card">
			<h2><?php esc_html_e( 'Devices', 'qr-scan-tracker' ); ?></h2>
			<?php if ( $devices ) : ?>
				<ul class="qrst-breakdown-list">
					<?php foreach ( $devices as $row ) : ?>
						<li><span><?php echo esc_html( ucfirst( $row['label'] ) ); ?></span><strong><?php echo esc_html( number_format_i18n( $row['total'] ) ); ?></strong></li>
					<?php endforeach; ?>
				</ul>
			<?php else : ?>
				<p class="description"><?php esc_html_e( 'No device data yet.', 'qr-scan-tracker' ); ?></p>
			<?php endif; ?>
		</div>
	</div>

	<h2><?php esc_html_e( 'Individual Scans', 'qr-scan-tracker' ); ?></h2>
	<form method="get">
		<input type="hidden" name="page" value="qrst-scans" />
		<?php if ( $code_id ) : ?>
			<input type="hidden" name="code_id" value="<?php echo esc_attr( $code_id ); ?>" />
		<?php endif; ?>
		<?php $list_table->display(); ?>
	</form>
</div>
