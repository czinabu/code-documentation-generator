package ratelimit

import (
	"sync"
	"time"
)

// Limiter is a token bucket.
type Limiter struct {
	mu       sync.Mutex
	capacity float64
	tokens   float64
	rate     float64
	last     time.Time
}

func New(capacity int, perSecond float64) *Limiter {
	return &Limiter{capacity: float64(capacity), tokens: float64(capacity), rate: perSecond, last: time.Now()}
}

func (l *Limiter) Allow() bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	l.tokens = min(l.capacity, l.tokens+now.Sub(l.last).Seconds()*l.rate)
	l.last = now
	if l.tokens < 1 {
		return false
	}
	l.tokens--
	return true
}
