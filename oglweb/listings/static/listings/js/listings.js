// google analytics
(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
	(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
						 m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
						})(window,document,'script','//www.google-analytics.com/analytics.js','ga');

ga('create', 'UA-55492403-1', 'auto');
ga('send', 'pageview');

// modal support

function login_to_signup(event){
	$('.login-content').hide();
	$('.signup-content').show();
	$('#id_username').val($('#id_login').val());
	$('#id_password1').val($('#id_password').val());
	$('#login_message').text('')
	if (event) {
		event.stopPropagation();
	}
}

function signup_to_login(event){
	$('.login-content').show()
	$('.signup-content').hide()
	$('#id_login').val($('#id_username').val());
	$('#id_password').val($('#id_password1').val());
	$('#login_message').text('')
	if (event) {
		event.stopPropagation();
	}
}

function login(msg){
	signup_to_login();
	if (msg.length > 0) {
		$('#login_message').text(msg)
	}
	$('#loginModal').modal();
}

function signup(msg){
	login_to_signup();
	if (msg.length > 0) {
		$('#login_message').text(msg)
	}
	$('#loginModal').modal();
}

function post_signup() {
	$('#postSignupModal').modal();
}

function post_login() {
	$('#postLoginModal').modal();
}
	
$(document).ready(function(){
	$('#login_link').click(function(event) {
		event.preventDefault();
		login('');
	});									 
	$('#signup_link').click(function(event) {
		event.preventDefault();
		signup('');
	});									 
	// pop any (first/single) modal requested via django.contrib.messages
	console.log('launching: ' + $('.modal_launcher').filter(':first').text())
	$('#' + $('.modal_launcher').filter(':first').text()).modal()
});
