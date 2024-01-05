package main

import (
	_ "embed"
	"log"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/logger"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/mac"
	"github.com/wailsapp/wails/v2/pkg/options/windows"

	"github.com/sublime-music/sublime-music/internal/app"
)

//go:embed logo/logo.png
var icon []byte

func main() {
	app := app.NewApp()
	err := wails.Run(&options.App{
		Title:             "sublime-music",
		Width:             1200,
		Height:            800,
		MinWidth:          900,
		MinHeight:         500,
		DisableResize:     false,
		Fullscreen:        false,
		Frameless:         false,
		StartHidden:       false,
		HideWindowOnClose: false,
		BackgroundColour:  &options.RGBA{R: 255, G: 255, B: 255, A: 255},
		AssetServer:       &assetserver.Options{Assets: nil, Handler: app.Router},
		Menu:              nil,
		Logger:            app.Logger(),
		LogLevel:          logger.DEBUG,
		OnStartup:         app.OnStartup,
		OnDomReady:        app.OnDomReady,
		OnBeforeClose:     app.OnBeforeClose,
		OnShutdown:        app.OnShutdown,
		WindowStartState:  options.Normal,
		Bind:              []any{app},
		// Windows platform specific options
		Windows: &windows.Options{
			WebviewIsTransparent: false,
			WindowIsTranslucent:  false,
			DisableWindowIcon:    false,
			// DisableFramelessWindowDecorations: false,
			WebviewUserDataPath: "",
			ZoomFactor:          1.0,
		},
		// Mac platform specific options
		Mac: &mac.Options{
			TitleBar: &mac.TitleBar{
				TitlebarAppearsTransparent: true,
				HideTitle:                  false,
				HideTitleBar:               false,
				FullSizeContent:            false,
				UseToolbar:                 false,
				HideToolbarSeparator:       true,
			},
			Appearance:           mac.NSAppearanceNameDarkAqua,
			WebviewIsTransparent: true,
			WindowIsTranslucent:  true,
			About: &mac.AboutInfo{
				Title:   "sublime-music",
				Message: "",
				Icon:    icon,
			},
		},
	})

	if err != nil {
		log.Fatal(err)
	}
}
