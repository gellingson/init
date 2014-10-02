
// keep search box on simple & advanced tabs in sync
$(document).ready(function(){
	$(".search-sync").keyup(function(){
		$(".search-sync").val($(this).val());
	});
});

// GEE TODO: should be unused, clean these up

// v 0.2 jquery toggle
$('#MSOButton').on('click', function(e) {
	$('#MSOPanel').toggleClass('hidden');
	$(this).text($('#MSOPanel').hasClass('hidden') ? 'More Options' : 'Simple Search');
//	$(this).find('span').toggleClass('glyphicon-collapse-down glyphicon-collapse-up');
})

// v0.1 non-jquery way to togglt
function toggleMSO() {
	// get the MSO
	var MSO_drawer = document.getElementById('MSO');

	// get the current value of the MSO's display property
	var displaySetting = MSO_drawer.style.display;

	// also get the MSO button, so we can change what it says
	var MSOButton = document.getElementById('MSO_button');

	// now toggle the MSO and the button text, depending on current state
	if (displaySetting == 'block') {
		// MSO is visible. hide it
		MSO_drawer.toggle();
		// change button text
		MSOButton.innerHTML = 'Show MSO';
	}
	else {
		// MSO is hidden. show it
		MSO_drawer.style.display = 'block';
		// change button text
		MSOButton.innerHTML = 'Hide MSO';
	}
}  
