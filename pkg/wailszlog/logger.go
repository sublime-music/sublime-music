package wailszlog

import (
	"github.com/rs/zerolog"
)

type ZLogger struct {
	logger *zerolog.Logger
}

func NewZLogger(logger *zerolog.Logger) *ZLogger {
	return &ZLogger{logger: logger}
}

func (z *ZLogger) Print(msg string) {
	z.logger.Info().Msg(msg)
}

func (z *ZLogger) Trace(msg string) {
	z.logger.Trace().Msg(msg)
}

func (z *ZLogger) Debug(msg string) {
	z.logger.Debug().Msg(msg)
}

func (z *ZLogger) Info(msg string) {
	z.logger.Info().Msg(msg)
}

func (z *ZLogger) Warning(msg string) {
	z.logger.Warn().Msg(msg)
}

func (z *ZLogger) Error(msg string) {
	z.logger.Error().Msg(msg)
}

func (z *ZLogger) Fatal(msg string) {
	z.logger.Fatal().Msg(msg)
}
