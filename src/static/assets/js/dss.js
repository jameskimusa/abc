$("#settings").submit(function(e) {
    e.preventDefault(); // prevent actual form submit
    var form = $(this);
    var url = form.attr('action'); 
    $.ajax({
         type: "POST",
         url: url,
         data: form.serialize(), // serializes form input
         success: function(data){
             console.log(data);
             alert("Settings Saved");
         }
    });
});

function toggle_config(e) {
    var settings = document.getElementById('config');

    if (settings.style.display == 'block') {
        settings.style.display = 'none';
        e.innerHTML = 'Show Configuration';
    }
    else {
        settings.style.display = 'block';
        e.innerHTML = "Hide Configuration";
    }
}

// Message Method
function disp_message(x){
    $('#scan_err').show();
    $("#err_msg").text(x);
    // $('#jerror').show();
}

// Error message
$('#scan_form').submit(function(event) {
    if($('#github').is(':checked')) { 
        var org = $.trim($("#otext").val());
        var user = $.trim($("#utext").val());
        if(org == "" && user == ""){
            event.preventDefault();
            disp_message(" Must indicate Github Orgs and/or Github Users");
            return;
        }
    } else if($('#bitbucket').is(':checked')){
        var bg = $.trim($("#BGurl").val());
        if(bg == ""){
            event.preventDefault();
            disp_message(" Must indicate Bitbucket URL");
            return;
        }
    } else if($('#gitlab').is(':checked')){
        var bg = $.trim($("#BGurl").val());
        if(bg == ""){
            event.preventDefault();
            disp_message(" Must indicate Gitlab URL");
            return;
        }
    } else if($('#azure').is(':checked')){
        var azure_organization = $.trim($("#azure_organization").val());
        if(azure_organization == ""){
            event.preventDefault();
            disp_message("Please supply an Azure Organization");
            return;
        }
    } else if($('#generic').is(':checked')){
        var git = $.trim($("#gtext").val());
        if(git == ""){
            event.preventDefault();
            disp_message(" Must indicate Git URLs");
            return;
        }
    }
    $("#scanning_msg").show();
});

// This function changes the source   
$(document).ready(function() {
    $("input[name$='gitgroup']").click(function(){
        var repo_type = $(this).val();
        $('.gitscan_form').hide();
		$('.gitscan_form.' + repo_type).show();
    });
});
