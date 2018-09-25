project('libremsonic-ui', 'vala', 'c')

glib_dep = dependency('glib-2.0')
gobject_dep = dependency('gobject-2.0')
gtk_dep = dependency('gtk+-3.0')
libsoup_dep = dependency('libsoup-2.4')

executable('libremsonic-ui', 'src/main.vala',
               dependencies : [glib_dep, gobject_dep, gtk_dep, libsoup_dep])
