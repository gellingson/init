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

function unfav(listing_id){
	ajaxPost("/ajax/unsavecar", {'listing_id': listing_id}, function(content){
		window.alert("This car has been removed from your favorite cars list. You can track your favorite cars in your dashboard.");
	});
	return false;
}

function fav(listing_id){
	ajaxPost("/ajax/savecar", {'listing_id': listing_id}, function(content){
		window.alert("This car has been added to your favorite cars list. You can track your favorite cars in your dashboard.");
	});
	return false;
}

function flag(listing_id){
	ajaxPost("/ajax/adminflag", {'listing_id': listing_id}, function(content){
		window.alert("flagging " + listing_id);
	});
	return false;
}

function setup_listing_buttons(){
	$("button.unfav").click(function() {
		unfav($(this).attr("listingid"));
	});
	$("button.addfav").click(function() {
		fav($(this).attr("listingid"));
	});
	$("button.flag").click(function() {
		flag($(this).attr("listingid"));
	});
}

$(document).ready(function(){
	// keep search box on simple & advanced tabs in sync
	$(".search-sync").keyup(function(){
		$(".search-sync").val($(this).val());
	});
	setup_listing_buttons();
});
