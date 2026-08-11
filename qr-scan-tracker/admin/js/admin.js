( function () {
	'use strict';

	document.addEventListener( 'DOMContentLoaded', function () {
		confirmDeleteLinks();
		drawScansChart();
	} );

	function confirmDeleteLinks() {
		var links = document.querySelectorAll( '.qrst-delete-link' );
		links.forEach( function ( link ) {
			link.addEventListener( 'click', function ( e ) {
				var message = ( window.QRST && QRST.i18n && QRST.i18n.confirmDelete ) || 'Delete this item?';
				if ( ! window.confirm( message ) ) {
					e.preventDefault();
				}
			} );
		} );
	}

	function drawScansChart() {
		var canvas = document.getElementById( 'qrst-scans-chart' );
		if ( ! canvas || ! window.QRST ) {
			return;
		}

		var codeId = canvas.getAttribute( 'data-code-id' ) || '0';

		wp.apiFetch( {
			url: QRST.restUrl + 'stats/' + codeId + '?days=30',
		} )
			.then( function ( data ) {
				renderChart( canvas, data.per_day || [] );
			} )
			.catch( function () {
				// Silently leave the canvas empty if the request fails.
			} );
	}

	function renderChart( canvas, perDay ) {
		var ctx = canvas.getContext( '2d' );
		var dpr = window.devicePixelRatio || 1;
		var rect = canvas.getBoundingClientRect();
		var width = rect.width || 600;
		var height = canvas.height || 90;

		canvas.width = width * dpr;
		canvas.height = height * dpr;
		ctx.scale( dpr, dpr );

		ctx.clearRect( 0, 0, width, height );

		if ( ! perDay.length ) {
			ctx.fillStyle = '#646970';
			ctx.font = '13px sans-serif';
			ctx.fillText( 'No scans yet in this period.', 10, height / 2 );
			return;
		}

		var totals = perDay.map( function ( row ) {
			return parseInt( row.total, 10 ) || 0;
		} );
		var max = Math.max.apply( null, totals.concat( [ 1 ] ) );

		var padding = 20;
		var chartWidth = width - padding * 2;
		var chartHeight = height - padding * 2;
		var stepX = perDay.length > 1 ? chartWidth / ( perDay.length - 1 ) : 0;

		ctx.beginPath();
		ctx.strokeStyle = '#2271b1';
		ctx.lineWidth = 2;

		perDay.forEach( function ( row, i ) {
			var x = padding + i * stepX;
			var y = padding + chartHeight - ( totals[ i ] / max ) * chartHeight;
			if ( 0 === i ) {
				ctx.moveTo( x, y );
			} else {
				ctx.lineTo( x, y );
			}
		} );
		ctx.stroke();

		ctx.fillStyle = 'rgba(34, 113, 177, 0.12)';
		ctx.lineTo( padding + ( perDay.length - 1 ) * stepX, padding + chartHeight );
		ctx.lineTo( padding, padding + chartHeight );
		ctx.closePath();
		ctx.fill();

		ctx.fillStyle = '#2271b1';
		perDay.forEach( function ( row, i ) {
			var x = padding + i * stepX;
			var y = padding + chartHeight - ( totals[ i ] / max ) * chartHeight;
			ctx.beginPath();
			ctx.arc( x, y, 2.5, 0, Math.PI * 2 );
			ctx.fill();
		} );
	}
} )();
