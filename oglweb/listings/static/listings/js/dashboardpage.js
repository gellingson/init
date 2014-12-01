// unfav version for dashboardpage
// another version exists for search page -- KEEP THEM IN SYNC!
function unfav(listing_id, title, elt){
	$('#unfavcartitle').text(title)
	$('#unfavlisting_id').val(listing_id);
	$('#unfavform').submit(function(event) {
		var form = $(this);
		ajaxPost(form.attr('action'), form.serialize(), function(content){
			// on dashboard page, unfav = del
			elt.closest('.listing-row').remove()
		});
		event.preventDefault();
		$('#unFavCarModal').modal('hide');
	});
	$('#unFavCarModal').modal();
}

$(document).ready(function(){
	// nothing unique to the dashboard page (yet)
});
