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

function unfav(listing_id, title, elt){
	$('#unfavcartitle').text(title)
	$('#unfavlisting_id').val(listing_id);
	$('#unfavform').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
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

function flag(listing_id, title, elt){
	$('#flagcartitle').text(title);
	$('#flaglisting_id').val(listing_id);
	$('#flagform').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			elt.closest('.listing-row').remove();
		});
		event.preventDefault();
		$('#flagCarModal').modal('hide');
	});
	$('#flagCarModal').modal();
}

function editnote(listing_id, title, elt){
	$('#notecartitle').text(title);
	$('#notelisting_id').val(listing_id);
	current_note = elt.closest('.listing-row').find('.note').text();
	$('#note_text').val(current_note);
	$('#noteform').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			elt.closest('.listing-row').find('.note').text(content.newcontents);
			if (content.newcontents) {
				elt.closest('.listing-row').children('.noteframe').removeClass('hidden');
			} else {
				elt.closest('listing-row').children('.noteframe').addClass('hidden');
			}
		});
		event.preventDefault();
		$('#editNoteModal').modal('hide');
	});
	$('#editNoteModal').modal();
}

function setup_listing_buttons(){
	$('button.unfav').click(function() {
		unfav($(this).attr('listing_id'), $(this).attr('title'), $(this));
	});
	$('button.addfav').click(function() {
		fav($(this).attr('listing_id'), $(this).attr('title'), $(this));
	});
	$('button.flag').click(function() {
		flag($(this).attr('listing_id'), $(this).attr('title'), $(this));
	});
	$('button.editnote').click(function() {
		editnote($(this).attr('listing_id'), $(this).attr('title'), $(this));
	});
	$('a.editnote').click(function() {
		editnote($(this).attr('listing_id'), $(this).attr('title'), $(this));
	});
}

$(document).ready(function(){
	// keep search box on simple & advanced tabs in sync
	$('.search-sync').keyup(function(){
		$('.search-sync').val($(this).val());
	});
	setup_listing_buttons();
});
