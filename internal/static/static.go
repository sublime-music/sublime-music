package static

import (
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/rs/zerolog"
)

//go:generate go run generator.go
//go:generate goimports -w js.gen.go css.gen.go fonts.gen.go

type staticFile struct {
	data        []byte
	contentType string
}

var staticfiles = map[string]staticFile{}

func ServeStatic(w http.ResponseWriter, r *http.Request) {
	log := zerolog.Ctx(r.Context()).With().
		Str("path", r.URL.Path).
		Logger()
	if file, found := staticfiles[chi.URLParam(r, "*")]; !found {
		log.Warn().Msg("couldn't find file to serve")
		w.WriteHeader(http.StatusNotFound)
	} else {
		log.Info().Msg("serving static file")
		w.Header().Add("Content-Type", file.contentType)
		w.Write(file.data)
	}
}
