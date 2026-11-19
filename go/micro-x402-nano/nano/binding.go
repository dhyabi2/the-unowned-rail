package nano

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"
)

// Scheme and Network are the x402 identifiers this package speaks.
const (
	Scheme  = "exact"
	Network = "nano:mainnet"
)

// IsNetwork reports whether n names Nano mainnet ("nano:mainnet" or the
// dash form "nano-mainnet"), ignoring case and surrounding space.
func IsNetwork(n string) bool {
	switch strings.ToLower(strings.TrimSpace(n)) {
	case "nano:mainnet", "nano-mainnet":
		return true
	}
	return false
}

// NewOrder returns a fresh order id bound to one resource: the resource, a
// '#', and 128 random bits in hex. The buyer makes one per payment.
func NewOrder(resource string) (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	return resource + "#" + hex.EncodeToString(b[:]), nil
}

// BoundTo reports whether order was made by NewOrder for this resource.
func BoundTo(order, resource string) bool {
	if !strings.HasPrefix(order, resource+"#") {
		return false
	}
	nonce := order[len(resource)+1:]
	if len(nonce) != 32 {
		return false
	}
	_, err := hex.DecodeString(nonce)
	return err == nil && strings.ToLower(nonce) == nonce
}

// Commitment is the representative a buyer sets on its send block so that the
// block names one order, one recipient and one price (Option C of the
// xno-call-binding standard v1): SHA-256 of
// "xno-binding/v1/rep|" + order + "|" + payTo + "|" + priceRaw, encoded as a
// nano_ account. payTo must be the canonical nano_ form and priceRaw the
// decimal raw price with no leading zeros. The buyer signs it inside the
// block, so a seller can tell which order a block pays even though Nano
// blocks carry no memo.
func Commitment(order, payTo, priceRaw string) string {
	sum := sha256.Sum256([]byte("xno-binding/v1/rep|" + order + "|" + payTo + "|" + priceRaw))
	return Encode(sum)
}

// Payload is the scheme-specific part of an X-PAYMENT header.
type Payload struct {
	Block string `json:"block"` // hash of the buyer's send block, 64 hex
	Order string `json:"order"` // the order id the block's representative commits to
}

// Payment is the decoded X-PAYMENT header.
type Payment struct {
	X402Version int     `json:"x402Version"`
	Scheme      string  `json:"scheme"`
	Network     string  `json:"network"`
	Payload     Payload `json:"payload"`
}

// ErrPayment is returned for a header that does not decode to a Nano payment.
var ErrPayment = errors.New("nano: malformed payment")

// EncodePayment builds the X-PAYMENT value for a block that pays an order.
func EncodePayment(blockHash, order string) string {
	b, _ := json.Marshal(Payment{X402Version: 1, Scheme: Scheme, Network: Network,
		Payload: Payload{Block: strings.ToUpper(blockHash), Order: order}})
	return base64.StdEncoding.EncodeToString(b)
}

// DecodePayment parses and checks an X-PAYMENT value. The block hash comes
// back upper-case.
func DecodePayment(s string) (Payment, error) {
	var p Payment
	raw, err := base64.StdEncoding.DecodeString(strings.TrimSpace(s))
	if err != nil {
		return p, ErrPayment
	}
	if err := json.Unmarshal(raw, &p); err != nil {
		return p, ErrPayment
	}
	if p.Scheme != Scheme || !IsNetwork(p.Network) || !IsBlockHash(p.Payload.Block) || p.Payload.Order == "" {
		return p, ErrPayment
	}
	p.Payload.Block = strings.ToUpper(p.Payload.Block)
	return p, nil
}

// IsBlockHash reports whether h is 64 hex characters.
func IsBlockHash(h string) bool {
	if len(h) != 64 {
		return false
	}
	_, err := hex.DecodeString(h)
	return err == nil
}
