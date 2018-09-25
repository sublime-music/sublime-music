using Soup;

namespace libremsonic
{
    class Server : GLib.Object
    {
        Soup.Session session;
        string url;
        string username;
        string password;

        public Server(string url, string username, string password)
        {
            session = new Soup.Session();
            this.url = url;
            this.username = username;
            this.password = password;
            session.ssl_strict = false;
            var ping_endpoint = "%s/rest/ping".printf(url);
            stdout.printf("%s\n", ping_endpoint);
            var message = new Soup.Message("POST", ping_endpoint);
            var form    = Soup.Form.encode("u",  username,
                                           "p",  password,
                                           "c",  "libremsonic",
                                           "f",  "json",
                                           "v",  "1.14.0");
            stdout.printf("Form: %s\n", form);
            message.request_headers.set_content_type(Soup.FORM_MIME_TYPE_URLENCODED, null);
            message.request_body.append_take(form.data);
            session.send_message(message);

            if (message.status_code != 200){
                stderr.printf("Error, Status code: %u\n", message.status_code);
                GLib.Process.exit(1);
            }

            var parser = new Json.Parser();
            parser.load_from_data((string)message.response_body.flatten().data, -1);
            var root_object = parser.get_root().get_object();
            var response = root_object.get_object_member("subsonic-response");
            
            if (response == null) {
                stderr.printf("No subsonic-response object in Json\n");
                GLib.Process.exit(1);
            }

            var status = response.get_string_member("status");
            
            if (status == null) {
                stderr.printf("No status object in subsonic-response\n");
                GLib.Process.exit(1);
            }

            if (status == "failed") {
                var error = response.get_object_member("error");
                if (error == null) {
                    GLib.Process.exit(1);
                }
                stderr.printf("Error Code: %lld. %s\n",
                              error.get_int_member("code"), error.get_string_member("message"));
            }
        }

        public Json.Array get_index_array()
        {
            
            //string url = "http://%s:%s/libresonic/rest/getIndexes".printf(args[1], args[2]);
            string index_endpoint = "%s/rest/getIndexes".printf(url);

            var message = new Soup.Message("POST", index_endpoint);
            var form    = Soup.Form.encode("u",  username,
                                           "p",  password,
                                           "c",  "libremsonic",
                                           "f",  "json",
                                           "v",  "1.14.0");
            stdout.printf("Form: %s\n", form);
            message.request_headers.set_content_type(Soup.FORM_MIME_TYPE_URLENCODED, null);
            message.request_body.append_take(form.data);
            session.send_message(message);

            var parser = new Json.Parser();

            parser.load_from_data((string)message.response_body.flatten().data, -1);
            var root_object = parser.get_root ().get_object ();
            var response = root_object.get_object_member("subsonic-response");
            var indexes = response.get_object_member("indexes");
            return indexes.get_array_member("index");
            
        }

        public Json.Array get_playlist_array()
        {
            string index_endpoint = "%s/rest/getPlaylists".printf(url);

            var message = new Soup.Message("POST", index_endpoint);
            var form    = Soup.Form.encode("u",  username,
                                           "p",  password,
                                           "c",  "libremsonic",
                                           "f",  "json",
                                           "v",  "1.14.0");
            stdout.printf("Form: %s\n", form);
            message.request_headers.set_content_type(Soup.FORM_MIME_TYPE_URLENCODED, null);
            message.request_body.append_take(form.data);
            session.send_message(message);

            var parser = new Json.Parser();

            parser.load_from_data((string)message.response_body.flatten().data, -1);
            var root_object = parser.get_root ().get_object ();
            var response = root_object.get_object_member("subsonic-response");
            var playlists = response.get_object_member("playlists");
            return playlists.get_array_member("playlist");
        }
    }
}