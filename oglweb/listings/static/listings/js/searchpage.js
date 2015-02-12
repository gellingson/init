// waypoint infinite scrolling
$('.listings').waypoint('infinite', {
	  container: 'auto',
	  items: '.listing-row',
	  more: '.more-listings-link',
	  offset: 'bottom-in-view',
	  loadingClass: 'infinite-loading',
	  onBeforePageLoad: $.noop,
	  onAfterPageLoad: setup_listing_buttons
	});

function show_buttons(elt){
	// the label is getting the click event, not the radio input
	button = $(elt).find('input');
	console.log($(button).attr('act'));
	$('#showaction').val($(button).attr('act'));
	$(elt).closest('form').submit();
}

function setup_header_buttons(){
	$('.showcontrol').click(function(event) {
		show_buttons(this);
	});
}

$(document).ready(function(){
	// keep search box on simple & advanced tabs in sync
	// doing this as a keyup fucks up using the keyboard to select & delete
	// the field contents; thus changing this to blur
	// $('.search-sync').keyup(function(){
	//	$('.search-sync').val($(this).val());
	//});
	$('.search-sync').blur(function(){
		$('.search-sync').val($(this).val());
	});
	$('#search_form').on('submit', function(e) {
		if ($('#query_string_dup').is(':focus')) {
			// may have been modified & not triggered blur()
			$('#query_string').val($('#query_string_dup').val());
		}
	});
	setup_header_buttons();
});
