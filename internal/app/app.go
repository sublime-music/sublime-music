package app

import (
	"context"
	"net/http"
	"os"

	"github.com/a-h/templ"
	"github.com/beeper/libserv/pkg/requestlog"
	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	_ "github.com/mattn/go-sqlite3"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/hlog"
	"github.com/rs/zerolog/log"
	"github.com/wailsapp/wails/v2/pkg/logger"

	"github.com/sublime-music/sublime-music/internal/components"
	"github.com/sublime-music/sublime-music/internal/static"
	"github.com/sublime-music/sublime-music/pkg/wailszlog"
)

const VERSION = "0.0.1"

type App struct {
	ctx context.Context

	Router *chi.Mux
	log    *zerolog.Logger
}

// NewApp creates a new App application struct
func NewApp() *App {
	log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr}).Level(zerolog.TraceLevel)
	defaultContextLogger := log.Logger.With().Bool("default_context_log", true).Caller().Logger()
	zerolog.DefaultContextLogger = &defaultContextLogger

	app := App{
		log: &log.Logger,
	}
	app.Router = chi.NewRouter()
	app.Router.Use(hlog.NewHandler(log.Logger))
	app.Router.Use(requestlog.AccessLogger(true))
	app.Router.Use(middleware.Recoverer)
	app.Router.Use(func(h http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			h.ServeHTTP(w, r.WithContext(r.Context()))
		})
	})

	app.Router.Get("/", templ.Handler(components.Index()).ServeHTTP)
	app.Router.Get("/static/*", static.ServeStatic)

	app.Router.Get("/initial", app.initial)

	return &app
}

func (a *App) Logger() logger.Logger {
	return wailszlog.NewZLogger(a.log)
}

// OnStartup is called at application startup
func (a *App) OnStartup(ctx context.Context) {
	a.ctx = a.log.WithContext(ctx)
}

// OnDomReady is called after front-end resources have been loaded
func (a App) OnDomReady(ctx context.Context) {
	// Add your action here
}

// OnBeforeClose is called when the application is about to quit,
// either by clicking the window close button or calling runtime.Quit.
// Returning true will cause the application to continue, false will continue shutdown as normal.
func (a *App) OnBeforeClose(ctx context.Context) (prevent bool) {
	return false
}

// OnShutdown is called at application termination
func (a *App) OnShutdown(ctx context.Context) {
	a.log.Info().Msg("Shutting down")
}
