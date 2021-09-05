$("#email_settings").submit(function(e) {
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

function toggle_email_config(e) {
    var settings = document.getElementById('email_config');

    if (settings.style.display == 'block') {
        settings.style.display = 'none';
        e.innerHTML = 'Show Email Configuration';
    }
    else {
        settings.style.display = 'block';
        e.innerHTML = "Hide Email Configuration";
    }
}
