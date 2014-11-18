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
	$("#unfavcartitle").text(title)
	$("#unfavlisting_id").val(listing_id);
	$("#unfavform").submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			elt.parent().children('.addfav').removeClass('hidden');
			elt.addClass('hidden');
		});
		event.preventDefault();
		$('#unFavCarModal').modal('hide');
	});
	$("#unFavCarModal").modal();
}

function fav(listing_id, title, elt){
	$("#favcartitle").text(title)
	ajaxPost("/ajax/savecar", {'listing_id': listing_id}, function(content){
		elt.parent().children('.unfav').removeClass('hidden');
		elt.addClass('hidden');
		$("#favCarModal").modal();
	});
}

function flag(listing_id, title, elt){
	$("#flagcartitle").text(title);
	$("#flaglisting_id").val(listing_id);
	$("#flagform").submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			//elt.closest(".listing_row").hide();
			elt.closest(".listing-row").remove();
		});
		event.preventDefault();
		$('#flagCarModal').modal('hide');
	});
	$("#flagCarModal").modal();
}

function setup_listing_buttons(){
	$("button.unfav").click(function() {
		unfav($(this).attr("listing_id"), $(this).attr("title"), $(this));
	});
	$("button.addfav").click(function() {
		fav($(this).attr("listing_id"), $(this).attr("title"), $(this));
	});
	$("button.flag").click(function() {
		flag($(this).attr("listing_id"), $(this).attr("title"), $(this));
	});
}

$(document).ready(function(){
	// keep search box on simple & advanced tabs in sync
	$(".search-sync").keyup(function(){
		$(".search-sync").val($(this).val());
	});
	setup_listing_buttons();
});
