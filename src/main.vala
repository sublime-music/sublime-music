using Soup;

int main(string[] args) {

    string url = "http://%s:%s/libresonic/rest/getMusicDirectory".printf(args[1], args[2]);
    var session = new Soup.Session();
    var message = new Soup.Message("POST", url);
    var form    = Soup.Form.encode("u",  args[3],
                                   "p",  args[4],
                                   "c",  "curl_zsh",
                                   "f",  "json",
                                   "v",  "1.14.0",
                                   "id", args[5]);

    stdout.printf("Form: %s\n", form);

    session.ssl_strict = false;

    message.request_headers.set_content_type(Soup.FORM_MIME_TYPE_URLENCODED, null);
    message.request_body.append_take(form.data);

    session.send_message(message);


    stdout.printf("Status Code: %u\n", message.status_code);
    stdout.printf("Message length: %lld\n", message.response_body.length);
    stdout.printf("Data: \n%s\n", (string) message.response_body.data);
    //stdout.printf("%s\n", message.tls_errors.to_string());

    return 0;
}