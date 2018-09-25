public class MyApp : Gtk.Application
{
    public MyApp()
    {
        Object (
            application_id: "com.gitlab.sumner.libremsonic",
            flags: ApplicationFlags.FLAGS_NONE
        );
    }

    protected override void activate()
    {
        var main_window = new Gtk.ApplicationWindow(this);
        main_window.default_height = 300;
        main_window.default_width = 300;
        main_window.title = "Hello World";

        var button_hello = new Gtk.Button.with_label("Click me!");
        button_hello.margin = 12;
        button_hello.clicked.connect(() => {
            button_hello.label = "Hello World!";
            button_hello.sensitive = false;
        });
        var label = new Gtk.Label("Hello Again World!");

        var grid = new Gtk.Grid();
        grid.orientation = Gtk.Orientation.VERTICAL;
        grid.add(label);
        grid.add(button_hello);
        main_window.add(grid);
        main_window.show_all();
    }

    public static int main(string[] args)
    {
        var app = new MyApp();
        return app.run (args);
    }
}
