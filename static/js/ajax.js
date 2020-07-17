function ajaxConnect(path, callback, context=null, send=null, method="GET", async=true) {
	var xmlhttp = new XMLHttpRequest();
	xmlhttp.onreadystatechange=function(){
		if (xmlhttp.readyState==4 && xmlhttp.status==200)
		{
		    if (context !== null)
		        callback.call(context, xmlhttp.responseText);
            else
		    	callback(xmlhttp.responseText);
		}
	}
    xmlhttp.open(method, path ,async);
    xmlhttp.send();
}