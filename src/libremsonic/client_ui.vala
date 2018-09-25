namespace libremsonic
{
    public class Client : Gtk.Application
    {
        libremsonic.Server server_inst;
        Gtk.Grid song_grid;
        Gtk.ScrolledWindow scrolled_window;

        public Client(libremsonic.Server server)
        {
            Object (
                application_id: "com.gitlab.sumner.libremsonic",
                flags: ApplicationFlags.FLAGS_NONE
            );
            server_inst = server;
        }

        protected override void activate()
        {
            var main_window = new Gtk.ApplicationWindow(this);
            main_window.default_height = 300;
            main_window.default_width = 300;
            main_window.title = "libremsonic";

            var grid = new Gtk.Grid();
            
            //var view_port = new Gtk.Viewport(null, null);

            var button_hello = new Gtk.Button.with_label("Refresh");
            button_hello.margin = 12;
            button_hello.clicked.connect(() => {
                song_grid = new Gtk.Grid();
                song_grid.orientation = Gtk.Orientation.VERTICAL;

                if (scrolled_window != null) {
                    grid.remove(scrolled_window);
                }

                scrolled_window = new Gtk.ScrolledWindow(null, null);
                scrolled_window.min_content_width = 600;
                scrolled_window.min_content_height = 900;
                scrolled_window.add(song_grid);
                grid.add(scrolled_window);
                //view_port.add(song_grid);
                add_array_list_to_grid();
                main_window.show_all();
            });
            var label = new Gtk.Label("libremsonic");

            grid.orientation = Gtk.Orientation.VERTICAL;
            grid.add(label);
            grid.add(button_hello);
            //grid.add(scrolled_window);
            //grid.add(view_port);
            main_window.add(grid);
            main_window.show_all();
        }

        void add_array_list_to_grid()
        {
            var index_array = server_inst.get_index_array();
            index_array.foreach_element(index_array_element);
        }

        void artist_array_element(Json.Array array, uint index, Json.Node element_node)
        {
            var element_object = element_node.dup_object();
            var but = new Gtk.Button.with_label(element_object.get_string_member("name"));
            song_grid.add(but);
            return;
        }
        void index_array_element(Json.Array array, uint index, Json.Node element_node)
        {
            var element_object = element_node.dup_object();
            element_object.get_array_member("artist").foreach_element(artist_array_element);
            return;
        }

    }
}
