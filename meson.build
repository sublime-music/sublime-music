project('libremsonic', 'vala', 'c')

glib_dep = dependency('glib-2.0')
gobject_dep = dependency('gobject-2.0')
libsoup_dep = dependency('libsoup-2.4')

executable('libremsonic', 'src/main.vala',
               dependencies : [glib_dep, gobject_dep,
                               libsoup_dep])