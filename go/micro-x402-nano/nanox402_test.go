package nanox402

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"

	"go-micro.dev/v6/wrapper/x402"

	"github.com/dhyabi2/the-unowned-rail/go/micro-x402-nano/nano"
)

const (
	seller = "nano_3t6k35gi95xu6tergt6p69ck76ogmitsa8mnijtpxm9fkcm736xtoncuohr3"
	buyer  = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
)

var milli = new(big.Int).Quo(nano.RawPerXNO, big.NewInt(1000)) // 0.001 XNO = 10^27 raw

// fakeNode answers block_info from blocks the fake wallet published.
type fakeNode struct {
	mu     sync.Mutex
	blocks map[string]map[string]any
	fail   atomic.Bool
}

func newNode() (*fakeNode, *httptest.Server) {
	n := &fakeNode{blocks: map[string]map[string]any{}}
	return n, httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if n.fail.Load() {
			w.WriteHeader(500)
			return
		}
		var q map[string]string
		_ = json.NewDecoder(r.Body).Decode(&q)
		n.mu.Lock()
		b, ok := n.blocks[q["hash"]]
		n.mu.Unlock()
		if q["action"] != "block_info" || !ok {
			json.NewEncoder(w).Encode(map[string]string{"error": "Block not found"})
			return
		}
		json.NewEncoder(w).Encode(b)
	}))
}

func (n *fakeNode) put(subtype, to, amount, rep string, confirmed bool) string {
	var h [32]byte
	rand.Read(h[:])
	hash := strings.ToUpper(hex.EncodeToString(h[:]))
	n.mu.Lock()
	n.blocks[hash] = map[string]any{"block_account": buyer, "amount": amount, "subtype": subtype,
		"confirmed": map[bool]string{true: "true", false: "false"}[confirmed],
		"contents":  map[string]string{"link_as_account": to, "representative": rep}}
	n.mu.Unlock()
	return hash
}

// wallet is a fake Payer: it publishes the send it is asked for to the fake node.
type wallet struct {
	node  *fakeNode
	calls atomic.Int32
	edit  func(*Send) // lets a test publish a block other than the one asked for
}

func (w *wallet) Pay(_ context.Context, s Send) (string, error) {
	w.calls.Add(1)
	if w.edit != nil {
		w.edit(&s)
	}
	return w.node.put("send", s.To, s.Amount.String(), s.Representative, true), nil
}

func paidServer(t *testing.T, f *Facilitator, amount string) *httptest.Server {
	t.Helper()
	cfg := x402.Config{PayTo: seller, Network: Network, Amount: amount, Facilitator: f, RequireSettlement: true}
	return httptest.NewServer(x402.Middleware(cfg)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, "paid content")
	})))
}

func get(t *testing.T, c interface {
	Do(*http.Request) (*http.Response, error)
}, url string) (*http.Response, error) {
	t.Helper()
	req, _ := http.NewRequest(http.MethodGet, url, nil)
	return c.Do(req)
}

// The wall this package exists for: go-micro's own client refuses a real Nano price.
func TestGoMicroClientCannotPayNano(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	srv := paidServer(t, &Facilitator{Node: ns.URL}, milli.String())
	defer srv.Close()
	c := &x402.Client{Payer: payerFunc(func(context.Context, x402.Requirements) (string, error) { return "x", nil })}
	_, err := get(t, c, srv.URL+"/tool")
	if err == nil || !strings.Contains(err.Error(), "invalid maxAmountRequired") {
		t.Fatalf("go-micro client: %v", err)
	}
	_ = node
}

type payerFunc func(context.Context, x402.Requirements) (string, error)

func (p payerFunc) Pay(ctx context.Context, r x402.Requirements) (string, error) { return p(ctx, r) }

// The real client-to-middleware path: go-micro's Middleware with this
// Facilitator, paid by this Client, through a node.
func TestEndToEndThroughGoMicroMiddleware(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	seen, err := nano.OpenFileSeen(filepath.Join(t.TempDir(), "seen"))
	if err != nil {
		t.Fatal(err)
	}
	defer seen.Close()
	srv := paidServer(t, &Facilitator{Node: ns.URL, Seen: seen}, milli.String())
	defer srv.Close()
	w := &wallet{node: node}
	c := &Client{Payer: w}
	resp, err := get(t, c, srv.URL+"/tool")
	if err != nil {
		t.Fatal(err)
	}
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != 200 || string(b) != "paid content" {
		t.Fatalf("%d %q", resp.StatusCode, b)
	}
	if resp.Header.Get(x402.PaymentResponseHeader) == "" {
		t.Error("no settlement header")
	}
	if c.Spent().Cmp(milli) != 0 || w.calls.Load() != 1 {
		t.Fatalf("spent %s, %d payments", c.Spent(), w.calls.Load())
	}
}

func TestReplayRefusedAcrossOrdersAndRestart(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	path := filepath.Join(t.TempDir(), "seen")
	seen, _ := nano.OpenFileSeen(path)
	f := &Facilitator{Node: ns.URL, Seen: seen}
	req := x402.Requirements{Scheme: "exact", Network: Network, MaxAmountRequired: milli.String(), PayTo: seller, Resource: "/tool"}
	order, _ := nano.NewOrder("/tool")
	hash := node.put("send", seller, milli.String(), nano.Commitment(order, seller, milli.String()), true)
	pay := nano.EncodePayment(hash, order)
	ctx := context.Background()
	if r, err := f.Settle(ctx, pay, req); err != nil || !r.Valid {
		t.Fatalf("first settle: %+v %v", r, err)
	}
	if r, _ := f.Settle(ctx, pay, req); r.Valid || r.Reason != "replayed" {
		t.Fatalf("second settle: %+v", r)
	}
	other, _ := nano.NewOrder("/tool")
	if r, _ := f.Verify(ctx, nano.EncodePayment(hash, other), req); r.Valid {
		t.Fatalf("same block, another order: %+v", r)
	}
	seen.Close()
	seen2, _ := nano.OpenFileSeen(path) // restart
	defer seen2.Close()
	f2 := &Facilitator{Node: ns.URL, Seen: seen2}
	if r, _ := f2.Verify(ctx, pay, req); r.Valid || r.Reason != "replayed" {
		t.Fatalf("after restart: %+v", r)
	}
}

func TestVerifyRefusals(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	f := &Facilitator{Node: ns.URL}
	ctx := context.Background()
	price := milli.String()
	req := x402.Requirements{Scheme: "exact", Network: Network, MaxAmountRequired: price, PayTo: seller, Resource: "/tool"}
	order, _ := nano.NewOrder("/tool")
	rep := nano.Commitment(order, seller, price)
	short := new(big.Int).Sub(milli, big.NewInt(1)).String()
	otherOrder, _ := nano.NewOrder("/tool")
	elsewhere, _ := nano.NewOrder("/other")
	cases := []struct {
		name, want string
		pay        string
		req        x402.Requirements
	}{
		{"receive block", "not-send", nano.EncodePayment(node.put("receive", seller, price, rep, true), order), req},
		{"another recipient", "wrong-recipient", nano.EncodePayment(node.put("send", buyer, price, rep, true), order), req},
		{"one raw short", "short", nano.EncodePayment(node.put("send", seller, short, rep, true), order), req},
		{"unconfirmed", "unconfirmed", nano.EncodePayment(node.put("send", seller, price, rep, false), order), req},
		{"block bound to another order", "unbound", nano.EncodePayment(node.put("send", seller, price, rep, true), otherOrder), req},
		{"order for another resource", "order", nano.EncodePayment(node.put("send", seller, price, rep, true), elsewhere), req},
		{"another network", "network", nano.EncodePayment(node.put("send", seller, price, rep, true), order), withNet(req, "base")},
		{"bad payTo", "payto", nano.EncodePayment(node.put("send", seller, price, rep, true), order), withPayTo(req, seller[:64]+"1")},
		{"bad amount", "amount", nano.EncodePayment(node.put("send", seller, price, rep, true), order), withAmount(req, "1e27")},
		{"garbage header", "payment", "not-base64!", req},
	}
	for _, tc := range cases {
		r, err := f.Verify(ctx, tc.pay, tc.req)
		if err != nil || r.Valid || r.Reason != tc.want {
			t.Errorf("%s: %+v %v (want %s)", tc.name, r, err, tc.want)
		}
	}
	good := nano.EncodePayment(node.put("send", seller, price, rep, true), order)
	node.fail.Store(true)
	if r, err := f.Settle(ctx, good, req); err == nil || r.Valid {
		t.Fatalf("node 500 credited: %+v %v", r, err)
	}
	node.fail.Store(false)
	if r, err := f.Settle(ctx, good, req); err != nil || !r.Valid {
		t.Fatalf("after the node recovered: %+v %v", r, err)
	}
}

// TestSettleWithOtherRequirementsThanVerified replays the case raised on
// micro/go-micro#5065: a payment verified against one set of requirements is
// then settled with different ones. Settle must judge the requirements it is
// given, not the earlier Verify result, refuse every mismatch, and leave the
// block unclaimed so the request it really paid for can still settle once.
func TestSettleWithOtherRequirementsThanVerified(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	f := &Facilitator{Node: ns.URL}
	ctx := context.Background()
	price := milli.String()
	req := x402.Requirements{Scheme: "exact", Network: Network, MaxAmountRequired: price, PayTo: seller, Resource: "/tool"}
	order, _ := nano.NewOrder("/tool")
	hash := node.put("send", seller, price, nano.Commitment(order, seller, price), true)
	pay := nano.EncodePayment(hash, order)

	if r, err := f.Verify(ctx, pay, req); err != nil || !r.Valid {
		t.Fatalf("verify: %+v %v", r, err)
	}
	higher := new(big.Int).Add(milli, big.NewInt(1)).String()
	otherSeller := buyer // a valid address that is not the one paid
	withResource := func(r x402.Requirements, res string) x402.Requirements { r.Resource = res; return r }
	withScheme := func(r x402.Requirements, s string) x402.Requirements { r.Scheme = s; return r }
	cases := []struct {
		name, want string
		req        x402.Requirements
	}{
		{"higher price, one raw more", "short", withAmount(req, higher)},
		{"higher price, ten times", "short", withAmount(req, new(big.Int).Mul(milli, big.NewInt(10)).String())},
		{"lower price than committed", "unbound", withAmount(req, new(big.Int).Sub(milli, big.NewInt(1)).String())},
		{"another payTo", "wrong-recipient", withPayTo(req, otherSeller)},
		{"another resource", "order", withResource(req, "/other")},
		{"another network", "network", withNet(req, "base")},
		{"another scheme", "network", withScheme(req, "upto")},
	}
	for _, tc := range cases {
		r, err := f.Settle(ctx, pay, tc.req)
		if err != nil || r.Valid || r.Reason != tc.want {
			t.Errorf("%s: %+v %v (want refusal %q)", tc.name, r, err, tc.want)
		}
	}
	// None of the refused settles claimed the block.
	if r, err := f.Settle(ctx, pay, req); err != nil || !r.Valid || r.Settlement != hash {
		t.Fatalf("settle with the verified requirements after the refusals: %+v %v", r, err)
	}
	if r, _ := f.Settle(ctx, pay, req); r.Valid || r.Reason != "replayed" {
		t.Fatalf("second settle: %+v", r)
	}
}

func withNet(r x402.Requirements, n string) x402.Requirements   { r.Network = n; return r }
func withPayTo(r x402.Requirements, p string) x402.Requirements { r.PayTo = p; return r }
func withAmount(r x402.Requirements, a string) x402.Requirements {
	r.MaxAmountRequired = a
	return r
}

func TestClientRefusesBadAmountsBeforePaying(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	for _, amt := range []string{"-5", "1e27", strings.Repeat("9", 40)} {
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(402)
			json.NewEncoder(w).Encode(map[string]any{"x402Version": 1, "accepts": []x402.Requirements{{
				Scheme: "exact", Network: Network, MaxAmountRequired: amt, PayTo: seller, Resource: "/t"}}})
		}))
		w := &wallet{node: node}
		_, err := get(t, &Client{Payer: w}, srv.URL)
		srv.Close()
		if err == nil || w.calls.Load() != 0 {
			t.Errorf("amount %q: err %v, %d payments", amt, err, w.calls.Load())
		}
	}
	// "" is go-micro's "free": its middleware serves without a 402, so no payment either.
}

func TestClientNoNanoEntry(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(402)
		io.WriteString(w, `{"x402Version":1,"accepts":[{"scheme":"exact","network":"base","maxAmountRequired":"10000","payTo":"0x1","resource":"/t"}]}`)
	}))
	defer srv.Close()
	resp, err := get(t, &Client{Payer: &wallet{}}, srv.URL)
	if !errors.Is(err, ErrNoNano) || resp == nil || resp.StatusCode != 402 {
		t.Fatalf("%v", err)
	}
	if b, _ := io.ReadAll(resp.Body); !strings.Contains(string(b), "base") {
		t.Fatal("402 body was not handed back")
	}
}

func TestClientBudget(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	srv := paidServer(t, &Facilitator{Node: ns.URL}, milli.String())
	defer srv.Close()
	w := &wallet{node: node}
	c := &Client{Payer: w, Budget: new(big.Int).Mul(milli, big.NewInt(2))}
	for i := 0; i < 2; i++ {
		if resp, err := get(t, c, srv.URL+"/tool"); err != nil || resp.StatusCode != 200 {
			t.Fatalf("call %d: %v", i, err)
		}
	}
	if _, err := get(t, c, srv.URL+"/tool"); err == nil {
		t.Fatal("third call passed the budget")
	}
	if w.calls.Load() != 2 {
		t.Fatalf("%d payments", w.calls.Load())
	}
}

func TestClientConcurrentBudget(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	srv := paidServer(t, &Facilitator{Node: ns.URL}, milli.String())
	defer srv.Close()
	w := &wallet{node: node}
	c := &Client{Payer: w, Budget: new(big.Int).Mul(milli, big.NewInt(3))}
	var wg sync.WaitGroup
	var ok atomic.Int32
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if resp, err := get(t, c, srv.URL+"/tool"); err == nil && resp.StatusCode == 200 {
				ok.Add(1)
			}
		}()
	}
	wg.Wait()
	if ok.Load() != 3 || w.calls.Load() != 3 {
		t.Fatalf("%d served, %d paid", ok.Load(), w.calls.Load())
	}
}

func TestClientKeepsSpendWhenServerRefuses(t *testing.T) {
	node, ns := newNode()
	defer ns.Close()
	srv := paidServer(t, &Facilitator{Node: ns.URL}, milli.String())
	defer srv.Close()
	// The wallet publishes one raw less than asked: the server refuses it.
	w := &wallet{node: node, edit: func(s *Send) { s.Amount = new(big.Int).Sub(s.Amount, big.NewInt(1)) }}
	c := &Client{Payer: w}
	resp, err := get(t, c, srv.URL+"/tool")
	if err == nil || resp.StatusCode != 402 {
		t.Fatalf("%v", err)
	}
	if c.Spent().Cmp(milli) != 0 {
		t.Fatalf("a published block was taken off the budget: spent %s", c.Spent())
	}
}
