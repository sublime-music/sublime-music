using Soup;


void print_artist_array_element(Json.Array array, uint index, Json.Node element_node) {
    var element_object = element_node.dup_object();
    stdout.printf("    %s\n", element_object.get_string_member("name"));
    return;
}
void print_index_array_element(Json.Array array, uint index, Json.Node element_node) {
    var element_object = element_node.dup_object();
    stdout.printf("%s: \n", element_object.get_string_member("name"));
    element_object.get_array_member("artist").foreach_element(print_artist_array_element);
    return;
}


int main(string[] args) {

    string url = "http://%s:%s/libresonic/rest/getIndexes".printf(args[1], args[2]);
    var session = new Soup.Session();
    var message = new Soup.Message("POST", url);
    var form    = Soup.Form.encode("u",  args[3],
                                   "p",  args[4],
                                   "c",  "curl_zsh",
                                   "f",  "json",
                                   "v",  "1.14.0");                                   

    stdout.printf("Form: %s\n", form);

    session.ssl_strict = false;

    message.request_headers.set_content_type(Soup.FORM_MIME_TYPE_URLENCODED, null);
    message.request_body.append_take(form.data);

    session.send_message(message);


    stdout.printf("Status Code: %u\n", message.status_code);
    stdout.printf("Message length: %lld\n", message.response_body.length);

    var parser = new Json.Parser();

    parser.load_from_data((string)message.response_body.flatten().data, -1);
    var root_object = parser.get_root ().get_object ();
    var response = root_object.get_object_member("subsonic-response");
    var indexes = response.get_object_member("indexes");
    var index_list = indexes.get_array_member("index");
    if (index_list == null) {
        stdout.printf("NULL-Y BOI\n");
    }

    index_list.foreach_element(print_index_array_element);

    //stdout.printf("index_list[%d]: %s\n", 0, index_list.get_element(0).dup_object().get_string_member("name"));
    //stdout.printf("Data: \n%s\n", (string) message.response_body.data);
    //stdout.printf("Member: %s\n", );
    //stdout.printf("%s\n", message.tls_errors.to_string());

    return 0;
}