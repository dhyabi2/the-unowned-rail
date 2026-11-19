// Package nanox402 lets a go-micro service accept, and a go-micro caller pay,
// the x402 "exact" scheme on Nano mainnet (network "nano:mainnet"), outside
// go-micro core and through its existing interfaces:
//
//   - Facilitator implements go-micro.dev/v6/wrapper/x402.Facilitator and
//     Settler. Put it in x402.Config.Facilitator with Network "nano:mainnet"
//     and PayTo a nano_ address; Middleware and Require are unchanged.
//   - Client pays a 402 that offers nano:mainnet. It exists because
//     x402.Client.Do parses the amount as an int64, and every real Nano price
//     is above that limit (0.001 XNO is 10^27 raw).
//
// Nothing here holds a key or a seed. The seller reads blocks from a node it
// chooses; the buyer's Payer signs with its own wallet.
package nanox402

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"sync"

	"go-micro.dev/v6/wrapper/x402"

	"github.com/dhyabi2/the-unowned-rail/go/micro-x402-nano/nano"
)

// Network is the x402 network name to put in x402.Config.Network.
const Network = nano.Network

// Facilitator verifies and settles Nano payments for go-micro's x402 wrapper.
type Facilitator struct {
	// Node is the RPC URL of a Nano node the operator trusts. Required.
	Node string
	// HTTP is the client for Node (default: 10 s timeout).
	HTTP *http.Client
	// AllowUnconfirmed accepts a send the node has not yet confirmed.
	// Leave false: an unconfirmed block can still lose to a fork.
	AllowUnconfirmed bool
	// Seen credits each block once. nil means an in-memory store, which a
	// restart forgets; use nano.OpenFileSeen to keep refusals across restarts.
	Seen nano.SeenStore

	once sync.Once
	mem  nano.SeenStore
}

var (
	_ x402.Facilitator = (*Facilitator)(nil)
	_ x402.Settler     = (*Facilitator)(nil)
)

func (f *Facilitator) seen() nano.SeenStore {
	if f.Seen != nil {
		return f.Seen
	}
	f.once.Do(func() { f.mem = nano.NewMemorySeen() })
	return f.mem
}

// Verify checks that payment names a confirmed send of at least
// req.MaxAmountRequired raw to req.PayTo, made for this resource, whose
// representative commits to the order, the recipient and the price, and
// that the block was not credited before. A node failure is an error, never
// a credit.
func (f *Facilitator) Verify(ctx context.Context, payment string, req x402.Requirements) (x402.Result, error) {
	refuse := func(reason string) (x402.Result, error) { return x402.Result{Valid: false, Reason: reason}, nil }
	if req.Scheme != nano.Scheme || !nano.IsNetwork(req.Network) {
		return refuse("network")
	}
	price, err := nano.ParseRaw(req.MaxAmountRequired)
	if err != nil {
		return refuse("amount")
	}
	payToKey, err := nano.Decode(req.PayTo)
	if err != nil {
		return refuse("payto")
	}
	payTo := nano.Encode(payToKey)
	if f.Node == "" {
		return x402.Result{}, errors.New("nanox402: Facilitator.Node is not set")
	}
	p, err := nano.DecodePayment(payment)
	if err != nil {
		return refuse("payment")
	}
	if !nano.BoundTo(p.Payload.Order, req.Resource) {
		return refuse("order")
	}
	if dup, err := f.seen().Seen(p.Payload.Block); err != nil {
		return x402.Result{}, err
	} else if dup {
		return refuse("replayed")
	}
	b, err := nano.BlockInfo(ctx, f.HTTP, f.Node, p.Payload.Block)
	if err != nil {
		return x402.Result{}, err
	}
	rep := nano.Commitment(p.Payload.Order, payTo, price.String())
	if reason := nano.CheckSend(b, payToKey, price, rep, !f.AllowUnconfirmed); reason != "" {
		return refuse(reason)
	}
	return x402.Result{Valid: true, Payer: b.Account, Settlement: p.Payload.Block}, nil
}

// Settle re-runs Verify on the same payment and requirements (it never
// trusts an earlier Result) and then claims the block hash, so one block
// pays one request once.
func (f *Facilitator) Settle(ctx context.Context, payment string, req x402.Requirements) (x402.Result, error) {
	res, err := f.Verify(ctx, payment, req)
	if err != nil || !res.Valid {
		return res, err
	}
	p, _ := nano.DecodePayment(payment) // Verify decoded it already
	fresh, err := f.seen().Claim(p.Payload.Block, p.Payload.Order)
	if err != nil {
		return x402.Result{}, err
	}
	if !fresh {
		return x402.Result{Valid: false, Reason: "replayed"}, nil
	}
	return res, nil
}

// Send is what the buyer's wallet is asked to publish: one send block of
// exactly Amount raw to To, with Representative set to the order commitment.
type Send struct {
	To             string
	Amount         *big.Int
	Representative string
	Order          string
	Resource       string
}

// Payer signs and publishes one send block with the caller's own key and
// returns its hash. This package never sees the key.
type Payer interface {
	Pay(ctx context.Context, s Send) (blockHash string, err error)
}

// Client is an HTTP client that pays x402 challenges offering nano:mainnet,
// within an optional total Budget in raw (nil or 0 = no cap).
type Client struct {
	HTTP   *http.Client
	Payer  Payer
	Budget *big.Int

	once   sync.Once
	budget *nano.Budget
}

func (c *Client) cap() *nano.Budget {
	c.once.Do(func() { c.budget = &nano.Budget{Cap: c.Budget} })
	return c.budget
}

// Spent returns the raw paid so far (including payments a server then refused:
// a published block cannot be taken back).
func (c *Client) Spent() *big.Int { return c.cap().Spent() }

// ErrNoNano is returned with the original 402 when it offers no nano:mainnet entry.
var ErrNoNano = errors.New("nanox402: no nano:mainnet entry")

// Do sends req; on a 402 that offers nano:mainnet "exact" it checks the
// amount and the budget, has Payer publish one bound send, and replays req
// once with the X-PAYMENT header.
func (c *Client) Do(req *http.Request) (*http.Response, error) {
	hc := c.HTTP
	if hc == nil {
		hc = http.DefaultClient
	}
	var body []byte
	if req.Body != nil {
		b, err := io.ReadAll(req.Body)
		req.Body.Close()
		if err != nil {
			return nil, err
		}
		body = b
		req.Body = io.NopCloser(bytes.NewReader(body))
	}
	resp, err := hc.Do(req)
	if err != nil || resp.StatusCode != http.StatusPaymentRequired {
		return resp, err
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	resp.Body.Close()
	resp.Body = io.NopCloser(bytes.NewReader(raw))
	if err != nil {
		return resp, err
	}
	var ch struct {
		Accepts []x402.Requirements `json:"accepts"`
	}
	_ = json.Unmarshal(raw, &ch)
	var reqd *x402.Requirements
	for i := range ch.Accepts {
		if ch.Accepts[i].Scheme == nano.Scheme && nano.IsNetwork(ch.Accepts[i].Network) {
			reqd = &ch.Accepts[i]
			break
		}
	}
	if reqd == nil {
		return resp, ErrNoNano
	}
	amount, err := nano.ParseRaw(reqd.MaxAmountRequired)
	if err != nil {
		return resp, fmt.Errorf("nanox402: refusing to pay %s: invalid maxAmountRequired %q", reqd.Resource, reqd.MaxAmountRequired)
	}
	payTo, err := nano.Canonical(reqd.PayTo)
	if err != nil {
		return resp, fmt.Errorf("nanox402: refusing to pay %s: invalid payTo %q", reqd.Resource, reqd.PayTo)
	}
	if c.Payer == nil {
		return resp, fmt.Errorf("nanox402: payment required for %s but no Payer configured", reqd.Resource)
	}
	order, err := nano.NewOrder(reqd.Resource)
	if err != nil {
		return resp, err
	}
	if err := c.cap().Reserve(amount); err != nil {
		return nil, err
	}
	hash, err := c.Payer.Pay(req.Context(), Send{To: payTo, Amount: new(big.Int).Set(amount),
		Representative: nano.Commitment(order, payTo, amount.String()), Order: order, Resource: reqd.Resource})
	if err != nil {
		// Only here is the reservation taken back: no block was published.
		c.cap().Release(amount)
		return nil, fmt.Errorf("nanox402: pay: %w", err)
	}
	if !nano.IsBlockHash(hash) {
		return nil, fmt.Errorf("nanox402: Payer returned %q, not a block hash", hash)
	}
	var rbody io.Reader
	if body != nil {
		rbody = bytes.NewReader(body)
	}
	retry, err := http.NewRequestWithContext(req.Context(), req.Method, req.URL.String(), rbody)
	if err != nil {
		return nil, err
	}
	for k, v := range req.Header {
		retry.Header[k] = v
	}
	retry.Header.Set(x402.PaymentHeader, nano.EncodePayment(hash, order))
	resp2, err := hc.Do(retry)
	if err != nil {
		return nil, fmt.Errorf("nanox402: replay after paying block %s: %w", hash, err)
	}
	if resp2.StatusCode == http.StatusPaymentRequired {
		return resp2, fmt.Errorf("nanox402: payment block %s for %s was refused", hash, reqd.Resource)
	}
	return resp2, nil
}
