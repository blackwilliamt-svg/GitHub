<?php
/**
 * Plugin Name:       QR Scan Tracker
 * Plugin URI:        https://example.com/qr-scan-tracker
 * Description:       Create trackable QR codes and see where, when, and on what device they get scanned — location, device/browser, referrer, and (when available) the logged-in WordPress user.
 * Version:           1.0.0
 * Requires at least: 5.8
 * Requires PHP:      7.4
 * Author:            QR Scan Tracker
 * License:           GPL v2 or later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       qr-scan-tracker
 * Domain Path:       /languages
 */

// Block direct access.
if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

/**
 * Core plugin constants.
 */
define( 'QRST_VERSION', '1.0.0' );
define( 'QRST_DB_VERSION', '1' );
define( 'QRST_PLUGIN_FILE', __FILE__ );
define( 'QRST_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'QRST_PLUGIN_URL', plugin_dir_url( __FILE__ ) );
define( 'QRST_PLUGIN_BASENAME', plugin_basename( __FILE__ ) );

/**
 * Composer-free autoload of plugin classes.
 */
require_once QRST_PLUGIN_DIR . 'includes/qrst-functions.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-db.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-activator.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-deactivator.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-user-agent-parser.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-geolocation.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-qr-generator.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-codes.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-scans.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-rewrite.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-cron.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-export.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-shortcodes.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-rest-api.php';
require_once QRST_PLUGIN_DIR . 'includes/class-qrst-loader.php';

if ( is_admin() ) {
	require_once QRST_PLUGIN_DIR . 'admin/class-qrst-admin.php';
	require_once QRST_PLUGIN_DIR . 'admin/class-qrst-list-table-codes.php';
	require_once QRST_PLUGIN_DIR . 'admin/class-qrst-list-table-scans.php';
}

/**
 * Activation / deactivation hooks.
 */
register_activation_hook( __FILE__, array( 'QRST_Activator', 'activate' ) );
register_deactivation_hook( __FILE__, array( 'QRST_Deactivator', 'deactivate' ) );

/**
 * Boot the plugin once all plugins are loaded.
 */
function qrst_run() {
	$loader = new QRST_Loader();
	$loader->run();
}
add_action( 'plugins_loaded', 'qrst_run' );
