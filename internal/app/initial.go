package app

import (
	"net/http"

	"github.com/a-h/templ"

	"github.com/sublime-music/sublime-music/internal/components"
)

func (a *App) initial(w http.ResponseWriter, r *http.Request) {
	templ.Handler(components.Main()).ServeHTTP(w, r)
}
