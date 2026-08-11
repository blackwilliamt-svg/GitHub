=== QR Scan Tracker ===
Contributors: qrscantracker
Tags: qr code, analytics, tracking, marketing, redirect
Requires at least: 5.8
Tested up to: 6.6
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Create trackable QR codes and see exactly where, when, and how they get scanned.

== Description ==

QR Scan Tracker lets you generate QR codes for any URL and automatically records every scan: location, device/browser, referring source, and the logged-in WordPress user when available.

**Features**

* Create unlimited trackable QR codes, each pointing at any destination URL.
* Every scan is logged with: date/time, approximate location (country/region/city + map link), device type, browser, OS, referrer, and browser language.
* If the scanner is logged into your site (staff badges, member cards, etc.) their username is recorded — configurable per-role.
* Dashboard with per-code stats: total scans, unique devices, a 30-day scans chart, top countries, and top devices.
* Downloadable PNG QR image for every code, plus a `[qrst_code id="1"]` shortcode to embed one in a post or page.
* CSV export of the full scan log, per code or site-wide.
* Privacy controls: location lookups can be turned off entirely; raw IP storage is off by default (only a one-way hash is kept to count unique scanners); optional IP anonymization; configurable data retention with automatic cleanup.
* Bot/crawler filtering so link-preview fetchers don't inflate your scan counts.

**How it works**

Each QR code you create gets its own tracking link, like `https://yoursite.com/qr/go/storefront-poster/`. The plugin generates a QR code image encoding that link. When someone scans it, WordPress logs the visit (location, device, etc.) and instantly redirects them to your real destination URL — the scanner never sees the tracking link.

Location and device lookups happen server-side; no tracking script runs in the visitor's browser.

== Installation ==

1. Upload the `qr-scan-tracker` folder to `/wp-content/plugins/`, or install the zip via Plugins -> Add New -> Upload Plugin.
2. Activate the plugin.
3. Go to **QR Codes -> Add New**, enter a label and destination URL, and save.
4. Download the generated QR image and use it wherever you like. Scans start appearing under **QR Codes -> View Scans** immediately.

== Frequently Asked Questions ==

= Does this track people who scan the code but don't have a WordPress account? =

Yes — every scan is logged regardless of login state. The scanner's WordPress username is only attached when they happen to already be logged into your site at the moment they scan (useful for internal use cases like staff/member badges). For the general public, you'll see anonymized location and device information instead of a name.

= How accurate is the location data? =

It's IP-based geolocation, so it's approximate — typically accurate to the city or region level, and can be inaccurate for mobile networks, VPNs, or corporate proxies.

= Does this store personal data? =

By default the plugin stores only a one-way hash of the IP address (for counting unique scanners), plus the derived approximate location, device/browser info, and referrer — no raw IP. You can optionally enable raw IP storage (with anonymization) in Settings, and you can set an automatic retention window to delete old scans. Review your applicable privacy laws (e.g. GDPR) before enabling raw IP storage or long retention windows.

= Can I use a QR code for a URL that isn't on my site? =

Yes, the destination can be any URL.

== Changelog ==

= 1.0.0 =
* Initial release.
