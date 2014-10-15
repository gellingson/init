// waypoint infinite scrolling
$('.listings').waypoint('infinite', {
	  container: 'auto',
	  items: '.listing-row',
	  more: '.more-listings-link',
	  offset: 'bottom-in-view',
	  loadingClass: 'infinite-loading',
	  onBeforePageLoad: $.noop,
	  onAfterPageLoad: $.noop
	});

// keep search box on simple & advanced tabs in sync
$(document).ready(function(){
	$(".search-sync").keyup(function(){
		$(".search-sync").val($(this).val());
	});
});
