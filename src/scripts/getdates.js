var url = "https://www.billetweb.fr/api/events?user=153926&key=c4ca4238a0b923820dcc509a6f75849b&version=1"; //this is identification for my own billetweb account (Zamies Test)
var xmlHttp = new XMLHttpRequest();
xmlHttp.onreadystatechange = function() {
    if (xmlHttp.readyState == 4 && xmlHttp.status == 200)
        console.log(xmlHttp.responseText);
}
xmlHttp.open("GET", url, true); // true for asynchronous
xmlHttp.send(null);
