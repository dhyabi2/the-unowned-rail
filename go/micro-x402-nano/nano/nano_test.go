package nano

import (
	"context"
	"encoding/hex"
	"math/big"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

// Published accounts: the burn address (all-zero key) and the genesis account.
const (
	burnAddr    = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
	genesisKey  = "E89208DD038FBB269987689621D52292AE9C35941A7484756ECCED92A65093BA"
	genesisAddr = "nano_3t6k35gi95xu6tergt6p69ck76ogmitsa8mnijtpxm9fkcm736xtoncuohr3"
)

func key(t *testing.T, h string) [32]byte {
	t.Helper()
	var k [32]byte
	b, err := hex.DecodeString(h)
	if err != nil || len(b) != 32 {
		t.Fatalf("bad key %q", h)
	}
	copy(k[:], b)
	return k
}

func TestAddressKnownAnswers(t *testing.T) {
	if got := Encode([32]byte{}); got != burnAddr {
		t.Fatalf("burn: got %s", got)
	}
	if got := Encode(key(t, genesisKey)); got != genesisAddr {
		t.Fatalf("genesis: got %s", got)
	}
	k, err := Decode(genesisAddr)
	if err != nil || k != key(t, genesisKey) {
		t.Fatalf("decode genesis: %v", err)
	}
	k2, err := Decode("xrb_" + genesisAddr[5:])
	if err != nil || k2 != k {
		t.Fatalf("xrb_ form: %v", err)
	}
	if c, _ := Canonical("xrb_" + genesisAddr[5:]); c != genesisAddr {
		t.Fatalf("canonical: %s", c)
	}
}

func TestAddressRefusals(t *testing.T) {
	bad := []string{
		"",
		genesisAddr[:len(genesisAddr)-1] + "1", // checksum one character off
		genesisAddr[:10] + "4" + genesisAddr[11:], // key character changed, checksum kept
		"nano_" + strings.Repeat("1", 59),         // short
		"nano_" + strings.Repeat("1", 59) + "0",   // 0 is not in the alphabet
		"ban_" + genesisAddr[5:],                  // another prefix
		"nano_" + "4" + genesisAddr[6:],           // top bits set past 256
	}
	for _, a := range bad {
		if _, err := Decode(a); err == nil {
			t.Errorf("accepted %q", a)
		}
	}
}

func TestRawPerXNO(t *testing.T) {
	if s := RawPerXNO.String(); s != "1"+strings.Repeat("0", 30) {
		t.Fatalf("RawPerXNO = %s", s)
	}
	milli := new(big.Int).Quo(RawPerXNO, big.NewInt(1000))
	got, err := ParseRaw(milli.String())
	if err != nil || got.Cmp(milli) != 0 {
		t.Fatalf("0.001 XNO: %v", err)
	}
}

func TestParseRawRefusals(t *testing.T) {
	for _, s := range []string{"", "0", "-5", "+5", " 5", "5 ", "1e27", "0x10", "1.5",
		strings.Repeat("9", 40), "340282366920938463463374607431768211456"} { // 2^128
		if _, err := ParseRaw(s); err == nil {
			t.Errorf("accepted %q", s)
		}
	}
	if _, err := ParseRaw("340282366920938463463374607431768211455"); err != nil { // 2^128-1
		t.Errorf("refused the largest balance: %v", err)
	}
}

func TestCommitmentKnownAnswer(t *testing.T) {
	// Computed independently with Python's hashlib (sha256, blake2b digest_size=5).
	order := "/paid#" + strings.Repeat("00", 16)
	price := new(big.Int).Quo(RawPerXNO, big.NewInt(1000)).String()
	want := "nano_3wjgnucj77576og5qfjo6y7euidztuttx3fo4b5dktopmx957z6htgb7yby7"
	if got := Commitment(order, genesisAddr, price); got != want {
		t.Fatalf("commitment %s", got)
	}
	// Each field moves it.
	if Commitment(order+"0", genesisAddr, price) == want ||
		Commitment(order, burnAddr, price) == want ||
		Commitment(order, genesisAddr, price+"0") == want {
		t.Fatal("commitment ignores a field")
	}
}

func TestOrderBinding(t *testing.T) {
	o, err := NewOrder("/paid")
	if err != nil {
		t.Fatal(err)
	}
	if !BoundTo(o, "/paid") {
		t.Fatalf("own order refused: %s", o)
	}
	o2, _ := NewOrder("/paid")
	if o == o2 {
		t.Fatal("two orders are equal")
	}
	for _, bad := range []string{"/paid", "/paid#", "/paid#zz" + strings.Repeat("0", 30),
		"/paid#" + strings.Repeat("A", 32), "/other#" + strings.Repeat("0", 32), "/paid/x#" + strings.Repeat("0", 32)} {
		if BoundTo(bad, "/paid") {
			t.Errorf("bound %q", bad)
		}
	}
}

func TestPaymentRoundTrip(t *testing.T) {
	h := strings.Repeat("ab", 32)
	p, err := DecodePayment(EncodePayment(h, "/paid#x"))
	if err != nil || p.Payload.Block != strings.ToUpper(h) || p.Payload.Order != "/paid#x" || p.Network != Network {
		t.Fatalf("%+v %v", p, err)
	}
	for _, bad := range []string{"", "!!", "e30=", EncodePayment("abc", "o"), EncodePayment(h, "")} {
		if _, err := DecodePayment(bad); err == nil {
			t.Errorf("accepted %q", bad)
		}
	}
}

func TestBlockInfoAndCheckSend(t *testing.T) {
	payTo := key(t, genesisKey)
	rep := Commitment("/p#"+strings.Repeat("0", 32), genesisAddr, "1000")
	answer := `{"block_account":"` + burnAddr + `","amount":"1000","confirmed":"true","subtype":"send",
		"contents":{"link_as_account":"` + genesisAddr + `","representative":"` + rep + `"}}`
	node := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case strings.Contains(r.URL.Path, "500"):
			w.WriteHeader(500)
		case strings.Contains(r.URL.Path, "err"):
			w.Write([]byte(`{"error":"Block not found"}`))
		default:
			w.Write([]byte(answer))
		}
	}))
	defer node.Close()
	ctx := context.Background()
	b, err := BlockInfo(ctx, nil, node.URL, "H")
	if err != nil || b.Account != burnAddr || !b.Confirmed {
		t.Fatalf("%+v %v", b, err)
	}
	if r := CheckSend(b, payTo, big.NewInt(1000), rep, true); r != "" {
		t.Fatalf("good block refused: %s", r)
	}
	cases := map[string]func(Block) (Block, *big.Int, string){
		"not-send":        func(b Block) (Block, *big.Int, string) { b.Subtype = "receive"; return b, big.NewInt(1000), rep },
		"wrong-recipient": func(b Block) (Block, *big.Int, string) { b.LinkAsAccount = burnAddr; return b, big.NewInt(1000), rep },
		"short":           func(b Block) (Block, *big.Int, string) { return b, big.NewInt(1001), rep },
		"unbound":         func(b Block) (Block, *big.Int, string) { return b, big.NewInt(1000), burnAddr },
		"unconfirmed":     func(b Block) (Block, *big.Int, string) { b.Confirmed = false; return b, big.NewInt(1000), rep },
	}
	for want, f := range cases {
		bb, price, r := f(b)
		if got := CheckSend(bb, payTo, price, r, true); got != want {
			t.Errorf("%s: got %q", want, got)
		}
	}
	if _, err := BlockInfo(ctx, nil, node.URL+"/500", "H"); err == nil {
		t.Error("HTTP 500 was not an error")
	}
	if _, err := BlockInfo(ctx, nil, node.URL+"/err", "H"); err == nil {
		t.Error("RPC error was not an error")
	}
}

func TestFileSeenSurvivesRestart(t *testing.T) {
	path := filepath.Join(t.TempDir(), "seen")
	h := strings.Repeat("cd", 32)
	s, err := OpenFileSeen(path)
	if err != nil {
		t.Fatal(err)
	}
	if fresh, err := s.Claim(strings.Repeat("12", 32), "/a path\nwith breaks#1"); !fresh || err != nil {
		t.Fatalf("order with spaces: %v %v", fresh, err)
	}
	if fresh, err := s.Claim(h, "/p#1"); !fresh || err != nil {
		t.Fatalf("first claim: %v %v", fresh, err)
	}
	if fresh, _ := s.Claim(strings.ToUpper(h), "/q#2"); fresh {
		t.Fatal("second claim (other order) was fresh")
	}
	s.Close()
	s2, err := OpenFileSeen(path) // the restart
	if err != nil {
		t.Fatal(err)
	}
	defer s2.Close()
	if seen, _ := s2.Seen(strings.Repeat("12", 32)); !seen {
		t.Fatal("restart forgot the block whose order had spaces")
	}
	if seen, _ := s2.Seen(h); !seen {
		t.Fatal("restart forgot the block")
	}
	if fresh, _ := s2.Claim(h, "/p#3"); fresh {
		t.Fatal("claim after restart was fresh")
	}
	if _, err := s2.Claim("nothex", "o"); err == nil {
		t.Fatal("stored a non-hash")
	}
}

func TestMemorySeenConcurrentClaims(t *testing.T) {
	s := NewMemorySeen()
	var wg sync.WaitGroup
	var mu sync.Mutex
	fresh := 0
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if ok, _ := s.Claim(strings.Repeat("ef", 32), "o"); ok {
				mu.Lock()
				fresh++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	if fresh != 1 {
		t.Fatalf("%d fresh claims of one block", fresh)
	}
}

func TestBudgetConcurrent(t *testing.T) {
	unit := new(big.Int).Quo(RawPerXNO, big.NewInt(1000))
	b := &Budget{Cap: new(big.Int).Mul(unit, big.NewInt(3))}
	var wg sync.WaitGroup
	var mu sync.Mutex
	ok := 0
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if b.Reserve(unit) == nil {
				mu.Lock()
				ok++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	if ok != 3 || b.Spent().Cmp(b.Cap) != 0 {
		t.Fatalf("%d reservations, spent %s", ok, b.Spent())
	}
	b.Release(unit)
	if b.Reserve(unit) != nil {
		t.Fatal("released reservation not reusable")
	}
}
