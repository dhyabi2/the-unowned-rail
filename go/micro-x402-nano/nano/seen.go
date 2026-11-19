package nano

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
)

// SeenStore credits each block hash once. Claim returns fresh=false when the
// hash was claimed before, for any order.
type SeenStore interface {
	Seen(hash string) (bool, error)
	Claim(hash, order string) (fresh bool, err error)
}

// MemorySeen is a SeenStore that lives as long as the process. A restart
// forgets it; use FileSeen for replay refusal that survives a restart.
type MemorySeen struct {
	mu sync.Mutex
	m  map[string]string
}

// NewMemorySeen returns an empty in-memory store.
func NewMemorySeen() *MemorySeen { return &MemorySeen{m: map[string]string{}} }

func (s *MemorySeen) Seen(hash string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, ok := s.m[strings.ToUpper(hash)]
	return ok, nil
}

func (s *MemorySeen) Claim(hash, order string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	h := strings.ToUpper(hash)
	if _, ok := s.m[h]; ok {
		return false, nil
	}
	s.m[h] = order
	return true, nil
}

// FileSeen is a SeenStore backed by an append-only file: one line
// "<HASH> <quoted order>" per credited block, synced to disk before Claim returns.
// Reopening the file after a restart refuses every hash it holds.
type FileSeen struct {
	mu sync.Mutex
	m  map[string]bool
	f  *os.File
}

// OpenFileSeen opens (or creates) the store at path and loads what it holds.
func OpenFileSeen(path string) (*FileSeen, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR|os.O_APPEND, 0o600)
	if err != nil {
		return nil, err
	}
	s := &FileSeen{m: map[string]bool{}, f: f}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		if fields := strings.Fields(sc.Text()); len(fields) > 0 {
			s.m[strings.ToUpper(fields[0])] = true
		}
	}
	if err := sc.Err(); err != nil {
		f.Close()
		return nil, err
	}
	return s, nil
}

func (s *FileSeen) Seen(hash string) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.m[strings.ToUpper(hash)], nil
}

func (s *FileSeen) Claim(hash, order string) (bool, error) {
	if !IsBlockHash(hash) {
		return false, fmt.Errorf("nano: refusing to store %q", hash)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	h := strings.ToUpper(hash)
	if s.m[h] {
		return false, nil
	}
	if _, err := s.f.WriteString(h + " " + strconv.Quote(order) + "\n"); err != nil {
		return false, err
	}
	if err := s.f.Sync(); err != nil {
		return false, err
	}
	s.m[h] = true
	return true, nil
}

// Close closes the file.
func (s *FileSeen) Close() error { return s.f.Close() }
