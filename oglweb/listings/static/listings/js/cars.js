
// note: cannot be invoked on items already in a favlist, e.g. on dashboard
// however, defining this here along with unfav as it operates on listing rows
function fav(listing_id, title, elt){
	$('#favcartitle').text(title)
	ajaxPost('/ajax/savecar', {'listing_id': listing_id}, function(content){
		elt.addClass('hidden');
		elt.parent().children('.unfav').removeClass('hidden');
		elt.parent().children('.editnote').removeClass('hidden');
		$('#favCarModal').modal();
	});
}

function unfav(listing_id, title, elt){
	// elt is the actual button instance that was pressed
	$('#unfavcartitle').text(title);
	$('#unfavlisting_id').val(listing_id);
	$('#unfavform').unbind('submit').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			// after unfav action take appropriate action on the listing
			if (elt.closest('.favlist')) {
				// remove the row that was just unfavorited from the containing favlist
				elt.closest('.listing-row').remove()
			} else {
				// change component visibilities to reflect the listing's new status
				elt.addClass('hidden');
				elt.parent().children('.addfav').removeClass('hidden');
				elt.parent().children('.editnote').addClass('hidden');
				elt.closest('.listing-row').children('.noteframe').addClass('hidden');
			}
		});
		event.preventDefault();
		$('#unFavCarModal').modal('hide');
	});
	$('#unFavCarModal').modal();
}

function flag(listing_id, title, elt){
	$('#flagcartitle').text(title);
	$('#flaglisting_id').val(listing_id);
	$('#flagform').unbind('submit').submit(function(event) {
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
	$('#noteform').unbind('submit').submit(function(event) {
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
	setup_listing_buttons();
	// save modal: focus() on the query description field of the modal
	$('#saveModal').on('shown.bs.modal', function () {
	    $('#query_descr').focus();
	})
	// notes modal: focus() on notes text field
	$('#editNoteModal').on('shown.bs.modal', function () {
	    $('#note_text').focus();
	})
});
