// waypoint infinite scrolling
$('.listings').waypoint('infinite', {
	  container: 'auto',
	  items: '.listing-row',
	  more: '.more-listings-link',
	  offset: 'bottom-in-view',
	  loadingClass: 'infinite-loading',
	  onBeforePageLoad: $.noop,
	  onAfterPageLoad: setup_buttons
	});

function fav(listing_id){
	ajaxPost("/ajax/savecar", {'listing_id': listing_id}, function(content){
		window.alert("Added " + listing_id + "to your favorite cars list. View these cars in your <a href='f'>dashboard</a>.");
	});
	return false;
}
function flag(listing_id){
	window.alert("flagging " + listing_id);
	return false;
}
function setup_buttons(){
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
	setup_buttons();
});
