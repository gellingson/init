
// note: cannot be invoked on items already in a favlist, e.g. on dashboard
// however, defining this here along with unfav as it operates on listing rows
function fav(listing_id, title, elt){
	if (logged_in_user) {
		var csrf = $.cookie('csrftoken');
		$('#favcartitle').text(title)
		ajaxPost('/ajax/savecar', {'listing_id': listing_id}, function(content){
			elt.addClass('hidden');
			elt.parent().children('.unfav').removeClass('hidden');
			elt.parent().children('.editnote').removeClass('hidden');
			$('#favCarModal').modal();
		});
	} else {
		login('fav', elt); // come back to fav this after login (not impl)
	}
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

function clickthrough(listing_id){
	var url = '/goto?listing_id=' + listing_id
	var win = window.open(url, '_blank')
	// win.focus() seems to switch focus without this on osx safari?
	// alternatively can select
	self.focus() // to keep the focus on the carbyr window -- doesn't work?
}

function login_to_signup(event){
	$('.login-content').hide();
	$('.signup-content').show();
	$('#id_username').val($('#id_login').val());
	$('#id_password1').val($('#id_password').val());
	if (event) {
		event.stopPropagation();
	}
}

function signup_to_login(event){
	$('.login-content').show()
	$('.signup-content').hide()
	$('#id_login').val($('#id_username').val());
	$('#id_password').val($('#id_password1').val());
	if (event) {
		event.stopPropagation();
	}
}

// put up login modal
function login(to, elt){
	var csrf = $.cookie('csrftoken');

	signup_to_login();

	$('#loginModal').modal();
}

function view(row){
	// pull out the fav button as a referent so we can call fav()/unfav()
	var addfav_btn = row.find('.addfav')
	$('#viewModalLabel').text(row.attr('title'))
	ajaxPost('/ajax/viewcar', {'listing_id': row.attr('id')}, function(content){
		// the post registers the click and returns all the info we have
		$('#viewYear').text(content.listing.model_year)
		$('#viewMake').text(content.listing.make)
		$('#viewModel').text(content.listing.model)
		$('#viewDescription').text(content.listing.listing_text)
		$('#viewImage').attr('src', content.listing.pic_href)
		$('#viewCT').attr('href', '/goto?listing_id=' + content.listing.id)
		$('#viewCTbtn').unbind('click').click(function(event) {
			clickthrough(content.listing.id)
			$('#viewModal').modal('hide');
		});
		if (content.listing.favorite) {
			$('#viewFav').prop('disabled', true);
			$('#viewFavdiv').removeClass('hidden').text('This car is in your favorites')
		} else {
			$('#viewFavdiv').addClass('hidden').text('Not in favorite list')
			$('#viewFav').prop('disabled', false);
			$('#viewFav').unbind('click').click(function(event) {
				fav(content.listing.id, content.listing.title, addfav_btn)
			});
		}
		$('#viewModal').modal();
	});	
}

function flag(listing_id, title, elt){
	$('#flagcartitle').text(title);
	$('#flaglisting_id').val(listing_id);
	$('#flagform').unbind('submit').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			elt.closest('.listing-row').remove();
			Waypoint.refreshAll()
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
	// vanilla interface
	$('.listing-row').click(function(event) {
		clickthrough($(this).attr('id')) // yes, html elt id is listing_id
	});
	// test interface overrides this click
	$('.test.listing-row').unbind('click').click(function(event) {
		view($(this));
	});
	$('button.testlogin').click(function(event) {
		event.stopPropagation();
		login('', $(this)); // login with no specific next action
	});
	$('button.unfav').click(function(event) {
		event.stopPropagation();
		unfav($(this).attr('listing_id'), $(this).attr('ltitle'), $(this));
	});
	$('button.addfav').click(function(event) {
		event.stopPropagation();
		fav($(this).attr('listing_id'), $(this).attr('ltitle'), $(this));
	});
	$('button.flag').click(function(event) {
		event.stopPropagation();
		flag($(this).attr('listing_id'), $(this).attr('ltitle'), $(this));
	});
	$('button.editnote').click(function(event) {
		event.stopPropagation();
		editnote($(this).attr('listing_id'), $(this).attr('ltitle'), $(this));
	});
	$('a.editnote').click(function(event) {
		event.stopPropagation();
		editnote($(this).attr('listing_id'), $(this).attr('ltitle'), $(this));
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
