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

// unfav version for searchpage
// another version exists for dashboard page -- KEEP THEM IN SYNC!
function unfav(listing_id, title, elt){
	$('#unfavcartitle').text(title)
	$('#unfavlisting_id').val(listing_id);
	$('#unfavform').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			// on search page, unfav = change buttons
			elt.addClass('hidden');
			elt.parent().children('.addfav').removeClass('hidden');
			elt.parent().children('.editnote').addClass('hidden');
			elt.closest('.listing-row').children('.noteframe').addClass('hidden');
		});
		event.preventDefault();
		$('#unFavCarModal').modal('hide');
	});
	$('#unFavCarModal').modal();
}

function fav(listing_id, title, elt){
	$('#favcartitle').text(title)
	ajaxPost('/ajax/savecar', {'listing_id': listing_id}, function(content){
		elt.addClass('hidden');
		elt.parent().children('.unfav').removeClass('hidden');
		elt.parent().children('.editnote').removeClass('hidden');
		$('#favCarModal').modal();
	});
}

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
	$('.search-sync').keyup(function(){
		$('.search-sync').val($(this).val());
	});
	setup_header_buttons();
});
